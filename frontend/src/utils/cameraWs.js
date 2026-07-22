/**
 * cameraWs.js
 *
 * 摄像头实时检测 WebSocket 工具
 *
 * 封装：
 * - WebSocket 连接管理
 * - 检测配置发送
 * - 视频帧发送
 * - 结果消息处理
 *
 * 使用方式：
 *
 * import { createCameraWs } from "@/utils/cameraWs";
 *
 * const ws = createCameraWs({
 *   mode: "cpu",
 *   conf: 0.5,
 *   onResult: (data) => {},
 *   onConfigOk: () => {},
 *   onError: (msg) => {},
 *   onClose: () => {},
 * });
 *
 * ws.connect();
 * ws.sendFrame(base64Data);
 * ws.close();
 */

class CameraWs {
  constructor(options) {
    this.ws = null;
    this.isConnected = false;
    this.closedByClient = false;

    // 检测配置
    this.mode = options.mode || "cpu";
    this.conf = options.conf || 0.5;
    this.iou = options.iou || 0.45;
    this.sceneId = options.sceneId;

    // 回调函数
    this.onResult = options.onResult || (() => {});
    this.onConfigOk = options.onConfigOk || (() => {});
    this.onError = options.onError || (() => {});
    this.onClose = options.onClose || (() => {});
  }

  /**
   * 建立 WebSocket 连接
   */
  connect() {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      console.warn("[CameraWs] 已存在活跃连接");
      return;
    }

    const token = localStorage.getItem("rsod_token");
    if (!token) {
      this.onError("登录状态已失效，请重新登录后使用实时检测");
      return false;
    }

    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";

    const host = window.location.host;

    const displayLanguage = localStorage.getItem("rsod_locale") === "en" ? "en" : "zh";
    const params = new URLSearchParams({
      token,
      display_language: displayLanguage,
    });
    const wsUrl = `${protocol}//${host}/api/detection/camera?${params.toString()}`;

    this.closedByClient = false;
    this.ws = new WebSocket(wsUrl);

    this.ws.onopen = () => {
      this.isConnected = true;

      console.log("[CameraWs] 连接已建立");

      this.ws.send(
        JSON.stringify({
          type: "config",
          mode: this.mode,
          conf: this.conf,
          iou: this.iou,
          scene_id: this.sceneId,
          display_language: displayLanguage,
        }),
      );
    };

    this.ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        this._handleMessage(data);
      } catch (err) {
        console.error("[CameraWs] 消息解析失败:", err);
      }
    };

    this.ws.onclose = (event) => {
      this.isConnected = false;

      console.log("[CameraWs] 连接已关闭", event.code, event.reason);

      if (!this.closedByClient && event.code !== 1000) {
        const reason = event.reason
          || (event.code === 1008 ? "实时检测认证失败，请重新登录" : "WebSocket 连接中断，请检查后端服务和代理配置");
        this.onError(reason);
      }

      this.onClose();
    };

    this.ws.onerror = (err) => {
      console.error("[CameraWs] 连接错误:", err);

      // 浏览器 onerror 不提供服务端关闭原因，交给 onclose 统一提示，避免重复弹窗。
    };

    return true;
  }

  /**
   * 发送单帧数据
   *
   * @param {string} base64Data
   * 不包含 data:image/... 前缀
   */
  sendFrame(base64Data) {
    if (!this.ws || this.ws.readyState !== WebSocket.OPEN) {
      console.warn("[CameraWs] 连接未建立");
      return false;
    }

    if (!base64Data) {
      return false;
    }

    this.ws.send(
      JSON.stringify({
        type: "frame",
        data: base64Data,
      }),
    );

    return true;
  }

  /**
   * 关闭连接
   */
  close() {
    this.closedByClient = true;
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(
        JSON.stringify({
          type: "close",
        }),
      );

      this.ws.close();
    } else if (this.ws?.readyState === WebSocket.CONNECTING) {
      // 组件切换或用户取消时，也要终止尚未完成的连接。
      this.ws.close();
    }

    this.ws = null;
    this.isConnected = false;
  }

  /**
   * 更新配置
   *
   * 注意：
   * 更新后需要重新 connect()
   */
  updateConfig(config) {
    this.mode = config.mode || this.mode;
    this.conf = config.conf || this.conf;
    this.iou = config.iou || this.iou;
    this.sceneId = config.sceneId;
  }

  /**
   * 处理后端消息
   */
  _handleMessage(data) {
    switch (data.type) {
      case "result":
        this.onResult({
          annotatedFrame: data.annotated_frame,
          detections: data.detections || [],
          objectCount: data.object_count || 0,
          inferenceTime: data.inference_time || 0,
          fps: data.fps || 0,
          frameCount: data.frame_count || 0,
        });
        break;

      case "config_ok":
        console.log("[CameraWs] 配置确认:", data.message);

        this.onConfigOk(data);
        break;

      case "error":
        console.error("[CameraWs] 服务端错误:", data.message);

        this.onError(data.message);
        break;

      default:
        console.warn("[CameraWs] 未知消息类型:", data.type);
    }
  }
}

/**
 * 创建摄像头 WebSocket 实例
 *
 * @param {Object} options
 * @returns {CameraWs}
 */
export function createCameraWs(options) {
  return new CameraWs(options);
}
