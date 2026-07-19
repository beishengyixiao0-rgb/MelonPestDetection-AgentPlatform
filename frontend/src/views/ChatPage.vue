<template>
  <div class="chat-page">
    <aside class="session-sidebar">
      <el-tooltip content="新建会话" placement="right">
        <el-button
          class="new-session-button"
          circle
          :icon="Plus"
          :disabled="agentStore.isLoading"
          @click="createNewChat"
        />
      </el-tooltip>
      <div class="session-list" aria-label="历史会话">
        <div
          v-for="session in agentStore.sessions"
          :key="session.session_uuid"
          :class="['session-row', { active: session.session_uuid === agentStore.currentSessionId }]"
        >
          <button
            class="session-button"
            type="button"
            :title="session.title || '新会话'"
            @click="openSession(session.session_uuid)"
          >
            <ChatDotRound class="session-icon" />
            <span class="session-title">{{ session.title || '新会话' }}</span>
          </button>
          <el-tooltip content="重命名会话" placement="right">
            <el-button class="rename-session-button" text circle :icon="EditPen" :disabled="agentStore.isLoading" @click="renameSession(session)" />
          </el-tooltip>
          <el-tooltip content="删除会话" placement="right">
            <el-button class="delete-session-button" text circle :icon="Delete" :disabled="agentStore.isLoading" @click="deleteSession(session.session_uuid)" />
          </el-tooltip>
        </div>
      </div>
    </aside>

    <div class="chat-main">
    <!-- ── 消息列表区域 ── -->
    <div class="message-list" ref="messageListRef">
      <div
        v-for="(msg, index) in agentStore.messages"
        :key="index"
        :class="['message-item', `message-${msg.role}`]"
      >
        <!-- 用户消息 -->
        <div v-if="msg.role === 'user'" class="message-bubble user-bubble">
          <div class="message-content">{{ msg.content }}</div>
          <!-- 单张图片附件 -->
          <div v-if="msg.image" class="message-attachment">
            <img :src="msg.imagePreview" alt="附件图片" />
          </div>
          <!-- 多图附件（批量检测） -->
          <div
            v-if="msg.images && msg.images.length"
            class="message-attachments-grid"
          >
            <img
              v-for="(src, i) in msg.images"
              :key="i"
              :src="src"
              alt="附件图片"
            />
          </div>
          <div v-if="msg.videoUrl" class="message-video">
            <video :src="msg.sourceVideoUrl || msg.videoUrl" controls preload="metadata"></video>
          </div>
        </div>

        <!-- AI 消息 -->
        <div
          v-else-if="msg.role === 'assistant'"
          class="message-bubble assistant-bubble"
        >
          <div v-if="msg.loading" class="typing-indicator">
            <span></span><span></span><span></span>
          </div>
          <div
            v-else
            class="message-content markdown-body"
            v-html="renderMarkdown(msg.content)"
          ></div>

          <!-- 检测结果卡片 -->
          <DetectionResultCard
            v-if="msg.detectionResult"
            :result="msg.detectionResult"
          />
        </div>

        <!-- 工具调用提示 -->
        <div v-if="msg.toolCall" class="tool-call-info">
          <el-tag size="small" type="info"
            >调用工具: {{ msg.toolCall.tool }}</el-tag
          >
        </div>
      </div>
    </div>

    <!-- ── 快捷操作栏 ── -->
    <div class="quick-actions">
      <el-button
        @click="handleQuickDetect('single')"
        :disabled="agentStore.isLoading"
        :icon="Camera"
        >单图检测</el-button
      >
      <el-button
        @click="handleQuickDetect('batch')"
        :disabled="agentStore.isLoading"
        :icon="FolderOpened"
        >批量/ZIP</el-button
      >
      <el-button @click="handleVideoDetect" :disabled="agentStore.isLoading">
        🎬 视频
      </el-button>
      <el-button disabled :icon="Monitor">摄像头</el-button>
    </div>

    <!-- ── 输入区域 ── -->
    <div class="input-area">
      <!-- 附件按钮 -->
      <el-button
        class="attach-btn"
        @click="triggerFileInput"
        :disabled="agentStore.isLoading"
        circle
        :icon="Paperclip"
      />
      <input
        ref="fileInputRef"
        type="file"
        accept="image/*,video/*,.zip"
        multiple
        style="display: none"
        @change="handleFileSelect"
      />

      <!-- 文本输入框 -->
      <el-input
        v-model="inputText"
        placeholder="输入消息，或拖拽图片/ZIP 到这里..."
        @keyup.enter="sendMessage"
        :disabled="agentStore.isLoading"
      />

      <!-- 发送/停止按钮 -->
      <el-button
        v-if="!agentStore.isLoading"
        type="primary"
        @click="sendMessage"
        :disabled="!inputText.trim() && !selectedFiles.length"
        :icon="Promotion"
        >发送</el-button
      >
      <el-button v-else type="danger" @click="handleStop" :icon="Close"
        >停止</el-button
      >
    </div>
    </div>
  </div>
</template>

<script setup>
/**
 * ChatPage.vue — 智能对话界面
 *
 * 功能：
 *   - 消息气泡（用户/AI 区分）
 *   - 文件附件上传（图片/ZIP 拖拽或选择）
 *   - SSE 流式渲染 AI 回复
 *   - 检测结果卡片展示
 *   - 快捷操作栏（单图/批量/视频/摄像头）
 *   - 中断当前对话
 */
import {
  detectBatch,
  detectSingle,
  detectVideo,
  detectZip,
  getVideoStatus,
} from "@/api/detection";
// import { detectBatch, detectSingle, detectZip } from "@/api/detection";
import DetectionResultCard from "@/components/DetectionResultCard.vue";
import { useAgentStore } from "@/stores/agent";
import { renderMarkdown } from "@/utils/markdown";
import request from "@/utils/request";
import { streamChat } from "@/utils/stream";
import {
  Camera,
  ChatDotRound,
  Close,
  Delete,
  EditPen,
  FolderOpened,
  Monitor,
  Paperclip,
  Plus,
  Promotion,
} from "@element-plus/icons-vue";
import { ElMessage, ElMessageBox } from "element-plus";
import { computed, nextTick, onMounted, ref } from "vue";

// ── Store ──
const agentStore = useAgentStore();

// ── 响应式状态 ──
const inputText = ref("");
const selectedFiles = ref([]);
const messageListRef = ref(null);
const fileInputRef = ref(null);
const VIDEO_POLL_INTERVAL = 1500;
const VIDEO_MAX_POLL_ATTEMPTS = 1200;
const LAST_SESSION_STORAGE_KEY = "rsod_agent_last_session";
const WELCOME_MESSAGE =
  "你好！我是 RSOD 目标检测智能体助手。\n\n你可以：\n- 上传一张图片，让我帮你检测目标\n- 使用下方的快捷按钮直接触发检测\n- 用自然语言描述你的需求\n\n试试发一张图片给我吧！";

// ── 计算属性 ──
const canSend = computed(
  () => inputText.value.trim() || selectedFiles.value.length,
);

// ── 方法 ──

/** 从数据库刷新当前用户的历史会话列表。 */
async function refreshSessions() {
  const response = await request.get("/chat/sessions");
  agentStore.setSessions(response.sessions || []);
  return agentStore.sessions;
}

/** 解析后端持久化在 tool_result 字段中的 JSON 元数据。 */
function parseStoredToolResult(value) {
  if (!value) return null;
  try {
    return typeof value === "string" ? JSON.parse(value) : value;
  } catch {
    return null;
  }
}

/** 判断工具结果是否能够驱动检测结果卡片。 */
function isDetectionResult(result) {
  return Boolean(
    result &&
      (result.type === "video" ||
        result.task_type === "video" ||
        result.detections ||
        result.annotated_images ||
        result.key_frames ||
        result.annotated_image_url ||
        result.class_counts ||
        result.class_counts_display),
  );
}

/** 将服务端消息转换为页面可渲染结构，并恢复附件和检测结果。 */
function mapServerMessage(message) {
  const mapped = {
    role: message.role === "assistant" ? "assistant" : "user",
    content: message.content || "",
    loading: false,
  };
  const storedResult = parseStoredToolResult(message.tool_result);

  if (mapped.role === "user") {
    const attachments = Array.isArray(storedResult?.attachments)
      ? storedResult.attachments.filter(Boolean)
      : [];
    if (attachments.length === 1) {
      if (
        mapped.content.startsWith("[视频检测]") ||
        mapped.content.includes("[本轮已上传视频附件]")
      ) {
        mapped.videoUrl = attachments[0];
        mapped.sourceVideoUrl = attachments[0];
      } else {
        mapped.image = "附件图片";
        mapped.imagePreview = attachments[0];
      }
    } else if (attachments.length > 1) {
      mapped.images = attachments;
    }
  } else if (isDetectionResult(storedResult)) {
    mapped.detectionResult = storedResult;
  }

  return mapped;
}

/** 打开指定会话并恢复已保存的文本消息。 */
async function openSession(sessionId) {
  if (!sessionId || agentStore.isLoading) return;
  try {
    const response = await request.get(`/chat/sessions/${sessionId}`);
    agentStore.setMessages((response.messages || []).map(mapServerMessage));
    agentStore.setCurrentSessionId(sessionId);
    localStorage.setItem(LAST_SESSION_STORAGE_KEY, sessionId);
  } catch (error) {
    console.error("[加载会话失败]", error);
  }
}

/** 创建空会话，使用户可在发送第一条消息前主动切换会话。 */
async function createNewChat() {
  if (agentStore.isLoading) return;
  try {
    const session = await request.post("/chat/sessions");
    agentStore.setCurrentSessionId(session.session_uuid);
    agentStore.setMessages([{ role: "assistant", content: WELCOME_MESSAGE }]);
    localStorage.setItem(LAST_SESSION_STORAGE_KEY, session.session_uuid);
    agentStore.setSessions([
      session,
      ...agentStore.sessions.filter(
        (item) => item.session_uuid !== session.session_uuid,
      ),
    ]);
  } catch (error) {
    console.error("[新建会话失败]", error);
    ElMessage.error("新建会话失败，请重试");
  }
}

/** 删除当前用户自己的会话，删除后自动切换到下一条可用会话。 */
async function deleteSession(sessionId) {
  try {
    await ElMessageBox.confirm("删除后无法恢复该会话及其消息，是否继续？", "删除会话", {
      confirmButtonText: "删除",
      cancelButtonText: "取消",
      type: "warning",
    });
    await request.delete(`/chat/sessions/${sessionId}`);
    const wasCurrent = sessionId === agentStore.currentSessionId;
    const sessions = await refreshSessions();
    if (wasCurrent) {
      if (sessions[0]) await openSession(sessions[0].session_uuid);
      else await createNewChat();
    }
    ElMessage.success("会话已删除");
  } catch (error) {
    if (error !== "cancel" && error !== "close") {
      console.error("[删除会话失败]", error);
    }
  }
}

/** 修改当前用户自己的会话标题。 */
async function renameSession(session) {
  try {
    const { value } = await ElMessageBox.prompt("", "重命名会话", {
      inputValue: session.title || "",
      inputPlaceholder: "输入会话名称",
      inputValidator: (value) => {
        if (!value?.trim()) return "会话名称不能为空";
        if (value.trim().length > 200) return "会话名称不能超过 200 个字符";
        return true;
      },
      confirmButtonText: "保存",
      cancelButtonText: "取消",
    });
    const renamed = await request.patch(`/chat/sessions/${session.session_uuid}`, {
      title: value.trim(),
    });
    agentStore.setSessions(
      agentStore.sessions.map((item) =>
        item.session_uuid === renamed.session_uuid ? renamed : item,
      ),
    );
    ElMessage.success("会话已重命名");
  } catch (error) {
    if (error !== "cancel" && error !== "close") {
      console.error("[重命名会话失败]", error);
    }
  }
}

/** 确保快捷检测也写入持久化会话，不依赖用户先发送 Agent 消息。 */
async function ensureSessionForHistory() {
  if (agentStore.currentSessionId) return agentStore.currentSessionId;
  const session = await request.post("/chat/sessions");
  agentStore.setCurrentSessionId(session.session_uuid);
  localStorage.setItem(LAST_SESSION_STORAGE_KEY, session.session_uuid);
  agentStore.setSessions([
    session,
    ...agentStore.sessions.filter(
      (item) => item.session_uuid !== session.session_uuid,
    ),
  ]);
  return session.session_uuid;
}

/** 将快捷检测的用户附件和助手结果一并写入长期会话。 */
async function persistQuickDetection({
  userContent,
  assistantContent,
  detectionResult,
  attachments = [],
}) {
  const sessionId = await ensureSessionForHistory();
  await request.post(`/chat/sessions/${sessionId}/quick-detection`, {
    user_content: userContent,
    assistant_content: assistantContent,
    detection_result: detectionResult,
    attachments: attachments.filter(Boolean),
  });
  await refreshSessions();
}

/** 上传快捷检测原始图片，取得刷新后仍可访问的 MinIO 地址。 */
async function uploadQuickAttachment(file) {
  const formData = new FormData();
  formData.append("file", file);
  const result = await request.post("/chat/upload", formData);
  return result.attachment_url || null;
}

/** 发送消息 */
async function sendMessage() {
  if (!canSend.value) return;

  const message = inputText.value.trim() || "检测这个附件";
  // 在清空之前保存附件引用，Agent 通道支持单图、ZIP 或多张图片。
  const filesToSend = selectedFiles.value;
  const imagePreviews = filesToSend
    .filter((file) => file.type.startsWith("image/"))
    .map((file) => URL.createObjectURL(file));
  const videoPreviews = filesToSend
    .filter((file) => isVideoFile(file))
    .map((file) => URL.createObjectURL(file));

  // 添加用户消息到列表
  agentStore.addMessage({
    role: "user",
    content: message,
    image:
      filesToSend.length === 1 && imagePreviews.length
        ? filesToSend[0].name
        : null,
    imagePreview: imagePreviews[0] || null,
    images: filesToSend.length > 1 ? imagePreviews : null,
    videoUrl: filesToSend.length === 1 ? videoPreviews[0] || null : null,
  });

  // 清空输入
  inputText.value = "";
  selectedFiles.value = [];

  // 添加 AI 加载占位
  agentStore.addMessage({ role: "assistant", content: "", loading: true });
  agentStore.setLoading(true);

  // 滚动到底部
  scrollToBottom();

  // ── 如果有附件图片，先上传到服务端获取真实路径 ──
  const serverImagePaths = [];
  // 保存可长期访问的原图 URL，刷新会话时使用该地址恢复右侧附件预览。
  const attachmentUrls = [];
  const attachmentTypes = [];
  if (filesToSend.length) {
    try {
      for (const file of filesToSend) {
        const formData = new FormData();
        formData.append("file", file);
        // 不设置 Content-Type，让 axios 自动添加 boundary
        const uploadResult = await request.post("/chat/upload", formData);
        serverImagePaths.push(uploadResult.file_path || uploadResult.image_path);
        if (uploadResult.attachment_url) {
          attachmentUrls.push(uploadResult.attachment_url);
          attachmentTypes.push(uploadResult.file_type);
        }
      }
    } catch (err) {
      console.error("[附件上传失败]", err.response?.data || err.message || err);
      const lastMsg = agentStore.messages[agentStore.messages.length - 1];
      lastMsg.content = `附件上传失败：${err.response?.data?.detail || err.message || "未知错误"}，请重试`;
      lastMsg.loading = false;
      lastMsg.error = true;
      agentStore.setLoading(false);
      return;
    }
  }

  // 发起 SSE 流式请求
  const requestBody = {
    message,
    ...(serverImagePaths.length === 1
      ? { image_path: serverImagePaths[0] }
      : {}),
    ...(serverImagePaths.length > 1 ? { image_paths: serverImagePaths } : {}),
    ...(attachmentUrls.length ? { attachment_urls: attachmentUrls } : {}),
    ...(attachmentTypes.length ? { attachment_types: attachmentTypes } : {}),
    ...(agentStore.currentSessionId
      ? { session_id: agentStore.currentSessionId }
      : {}),
  };
  let fullContent = "";

  const stop = streamChat("/api/chat/stream", requestBody, {
    onMessage: (data) => {
      // 调试日志：查看收到的所有 SSE 事件
      console.log(
        "[SSE事件]",
        data.type,
        data.type === "tool_result" ? data : "",
      );
      const lastMsg = agentStore.messages[agentStore.messages.length - 1];
      if (data.type === "text_chunk") {
        fullContent += data.content;
        agentStore.updateLastAssistantMessage(fullContent);
        scrollToBottom();
      } else if (data.type === "session") {
        // 首次发送消息时后端创建会话，收到事件后同步本地会话标识。
        agentStore.setCurrentSessionId(data.session_id);
        localStorage.setItem(LAST_SESSION_STORAGE_KEY, data.session_id);
      } else if (data.type === "tool_call") {
        // 工具调用中，更新最后一条 AI 消息的工具信息
        lastMsg.toolCall = { tool: data.tool, input: data.input };
      } else if (data.type === "tool_result") {
        // 工具调用返回结果
        console.log(
          "[工具结果] tool:",
          data.tool,
          "result长度:",
          data.result?.length,
        );
        try {
          const result =
            typeof data.result === "string"
              ? JSON.parse(data.result)
              : data.result;
          console.log(
            "[工具结果解析]",
            "total_objects:",
            result.total_objects,
            "detections:",
            result.detections?.length,
          );
          if (
            result.type === "video" ||
            result.task_type === "video" ||
            result.detections ||
            result.annotated_images ||
            result.key_frames ||
            // 检测工具可能移除明细列表，只保留标注图地址和类别统计。
            result.annotated_image_url ||
            result.class_counts ||
            result.class_counts_display
          ) {
            if (result.source_video_url) {
              const userVideoMessage = [...agentStore.messages]
                .reverse()
                .find((message) => message.role === "user" && message.videoUrl);
              if (userVideoMessage) {
                // Agent 路径也使用后端转码后的源视频，避免浏览器直接播放原始编码黑屏。
                userVideoMessage.sourceVideoUrl = result.source_video_url;
              }
            }
            // 有检测结果，设置到消息中
            lastMsg.detectionResult = result;
            lastMsg.loading = false;
            console.log("[检测结果卡片已设置]", lastMsg.detectionResult);
          }
        } catch (e) {
          console.warn(
            "[工具结果解析失败]",
            e.message,
            "原始数据:",
            data.result?.substring?.(0, 200),
          );
          // 非检测结果 JSON，作为普通文本
          lastMsg.content += `\n[工具结果: ${String(data.result).substring(0, 100)}...]`;
        }
        scrollToBottom();
      } else if (data.type === "error") {
        lastMsg.content = data.content;
        lastMsg.loading = false;
        lastMsg.error = true;
      }
    },
    onDone: () => {
      const lastMsg = agentStore.messages[agentStore.messages.length - 1];
      if (lastMsg.loading) lastMsg.loading = false;
      agentStore.setLoading(false);
      agentStore.abortController = null;
      refreshSessions().catch((error) =>
        console.error("[刷新会话列表失败]", error),
      );
    },
    onError: (err) => {
      const lastMsg = agentStore.messages[agentStore.messages.length - 1];
      lastMsg.content = `抱歉，处理出错了：${err.message}`;
      lastMsg.loading = false;
      lastMsg.error = true;
      agentStore.setLoading(false);
      ElMessage.error("对话请求失败，请重试");
    },
  });

  // 保存 中断函数到 store
  agentStore.abortController = stop;
}

/** 停止生成 */
function handleStop() {
  agentStore.abort();
  const lastMsg = agentStore.messages[agentStore.messages.length - 1];
  if (lastMsg.loading) {
    lastMsg.loading = false;
    lastMsg.content += "\n[已停止生成]";
  }
}

/** 触发文件选择框 */
function triggerFileInput() {
  fileInputRef.value?.click();
}

/** 文件选择回调 */
function handleFileSelect(event) {
  const files = Array.from(event.target.files);
  event.target.value = "";
  if (!files.length) return;

  const containsZip = files.some((file) =>
    file.name.toLowerCase().endsWith(".zip"),
  );
  const videoFiles = files.filter((file) => isVideoFile(file));
  if (videoFiles.length && (files.length > 1 || containsZip)) {
    ElMessage.warning("视频附件请单独选择；图片可以多选");
    return;
  }
  if (containsZip && files.length > 1) {
    ElMessage.warning("ZIP 文件请单独选择；多图检测请选择多张图片");
    return;
  }

  selectedFiles.value = files;
  ElMessage.info(
    files.length === 1
      ? `${files[0].name} 已选择`
      : `已选择 ${files.length} 个图片附件`,
  );
}

function isVideoFile(file) {
  if (file.type?.startsWith("video/")) return true;
  return [".mp4", ".avi", ".mov", ".mkv", ".wmv", ".flv"].some((suffix) =>
    file.name.toLowerCase().endsWith(suffix),
  );
}

/** 滚动到底部 */
function scrollToBottom() {
  nextTick(() => {
    if (messageListRef.value)
      messageListRef.value.scrollTop = messageListRef.value.scrollHeight;
  });
}

/**
 * 快捷单图检测流程：
 * 1. 用户点击"📷 单图检测"按钮
 * 2. 弹出文件选择框
 * 3. 选择图片后，调用 detectSingle API
 * 4. 将结果以"用户消息 + AI 结果卡片"的形式插入对话
 */
async function handleQuickDetect(type) {
  if (type === "single") {
    // 创建隐藏的文件选择器
    const input = document.createElement("input");
    input.type = "file";
    input.accept = "image/*";
    input.onchange = async (e) => {
      const file = e.target.files[0];
      if (!file) return;
      const userContent = `[快捷检测] ${file.name}`;
      let attachmentUrl = null;
      try {
        attachmentUrl = await uploadQuickAttachment(file);
      } catch (error) {
        // 原图持久化失败不阻断本轮临时检测，结果仍可正常返回。
        console.warn("[快捷检测原图持久化失败]", error);
      }

      // 添加用户消息（显示文件名）
      agentStore.addMessage({
        role: "user",
        content: userContent,
        image: file.name,
        imagePreview: URL.createObjectURL(file),
      });

      // 添加加载占位
      agentStore.addMessage({
        role: "assistant",
        content: "正在检测中...",
        loading: true,
      });
      agentStore.setLoading(true);

      // 构造 FormData 并调用 API
      const formData = new FormData();
      formData.append("file", file);

      try {
        const result = await detectSingle(formData);
        const lastMsg = agentStore.messages[agentStore.messages.length - 1];
        lastMsg.content = `检测完成！发现 ${result.total_objects} 个目标。`;
        lastMsg.loading = false;
        lastMsg.detectionResult = result;
        persistQuickDetection({
          userContent,
          assistantContent: lastMsg.content,
          detectionResult: result,
          attachments: [attachmentUrl],
        }).catch((error) => console.warn("[保存快捷检测历史失败]", error));
      } catch (err) {
        const lastMsg = agentStore.messages[agentStore.messages.length - 1];
        lastMsg.content = "检测失败，请重试";
        lastMsg.loading = false;
      } finally {
        agentStore.setLoading(false);
      }
    };
    input.click();
  } else if (type === "batch") {
    // 批量检测（支持多选 + ZIP）
    const input = document.createElement("input");
    input.type = "file";
    input.accept = "image/*,.zip";
    input.multiple = true;
    input.onchange = async (e) => {
      const files = Array.from(e.target.files);
      if (!files.length) return;

      const isZip = files.some((f) => f.name.toLowerCase().endsWith(".zip"));
      const formData = new FormData();
      let userContent = "";
      let attachments = [];
      if (isZip && files.length !== 1) {
        ElMessage.warning("ZIP 文件请单独选择");
        return;
      }

      if (isZip && files.length === 1) {
        // 单个 ZIP 文件
        formData.append("file", files[0]);
        agentStore.addMessage({
          role: "user",
          content: `[快捷检测] ZIP: ${files[0].name}`,
        });
        userContent = `[快捷检测] ZIP: ${files[0].name}`;
      } else {
        // 多张图片
        files.forEach((f) => formData.append("files", f));
        const imagePreviews = files.map((f) => URL.createObjectURL(f));
        agentStore.addMessage({
          role: "user",
          content: `[快捷检测] ${files.length} 张图片`,
          images: imagePreviews,
        });
        userContent = `[快捷检测] ${files.length} 张图片`;
        // 多图原图逐个持久化，失败的文件不影响批量检测本身。
        attachments = await Promise.all(
          files.map((file) => uploadQuickAttachment(file).catch(() => null)),
        );
      }

      agentStore.addMessage({
        role: "assistant",
        content: "正在批量检测中...",
        loading: true,
      });
      agentStore.setLoading(true);
      try {
        const apiCall = isZip ? detectZip(formData) : detectBatch(formData);
        const result = await apiCall;
        const lastMsg = agentStore.messages[agentStore.messages.length - 1];

        // 检查是否有错误
        if (result.error) {
          lastMsg.content = `批量检测失败：${result.error}`;
          lastMsg.loading = false;
          lastMsg.error = true;
          return;
        }
        const totalObjects = result.total_objects ?? 0;
        lastMsg.content = `批量检测完成！共 ${totalObjects} 个目标。`;
        lastMsg.loading = false;
        lastMsg.detectionResult = result;
        console.log("[批量检测结果]", result);
        persistQuickDetection({
          userContent,
          assistantContent: lastMsg.content,
          detectionResult: result,
          attachments,
        }).catch((error) => console.warn("[保存快捷检测历史失败]", error));
      } catch (err) {
        console.error("[批量检测异常]", err);
        const lastMsg = agentStore.messages[agentStore.messages.length - 1];
        lastMsg.content = `批量检测失败：${err.message || err}`;
        lastMsg.loading = false;
        lastMsg.error = true;
      } finally {
        agentStore.setLoading(false);
      }
    };
    input.click();
  }
}

/**
 * 视频检测流程：
 * 1. 用户点击 "🎬 视频" 按钮
 * 2. 弹出文件选择框（限制视频格式）
 * 3. 选择视频后，上传到后端
 * 4. 后端返回 task_id，前端开始轮询进度
 * 5. 处理完成后，展示关键帧结果卡片
 */
async function handleVideoDetect() {
  const input = document.createElement("input");
  input.type = "file";
  input.accept = ".mp4,.avi,.mov,.mkv,.wmv,.flv,video/*";
  input.onchange = async (e) => {
    const file = e.target.files[0];
    if (!file) return;

    // 校验文件大小（50MB）
    const maxSize = 50 * 1024 * 1024;
    if (file.size > maxSize) {
      ElMessage.warning("视频文件不能超过 50MB");
      return;
    }

    // 创建视频的 Blob URL 用于预览
    const videoUrl = URL.createObjectURL(file);
    const userContent = `[视频检测] ${file.name} (${(file.size / (1024 * 1024)).toFixed(1)}MB)`;

    // 添加用户消息
    agentStore.addMessage({
      role: "user",
      content: userContent,
      videoUrl,
    });
    const userVideoMessage = agentStore.messages[agentStore.messages.length - 1];

    // 添加加载占位
    agentStore.addMessage({
      role: "assistant",
      content: "正在上传视频...",
      loading: true,
    });
    agentStore.setLoading(true);
    scrollToBottom();

    // 上传视频
    const formData = new FormData();
    formData.append("file", file);

    let cancelled = false;
    const cancelPolling = () => {
      cancelled = true;
    };

    try {
      const uploadResult = await detectVideo(formData);
      const taskId = uploadResult.task_id;

      // 更新加载消息
      const lastMsg = agentStore.messages[agentStore.messages.length - 1];
      lastMsg.content = "视频已上传，正在处理中...";
      // 上传完成后展示轮询文本；loading 状态只用于上传阶段的占位动画。
      lastMsg.loading = false;

      // 开始轮询进度
      agentStore.abortController = cancelPolling;
      const videoResult = await pollVideoProgress(taskId, userVideoMessage, () => cancelled);
      if (videoResult) {
        const assistantMessage = agentStore.messages[agentStore.messages.length - 1];
        persistQuickDetection({
          userContent,
          assistantContent: assistantMessage.content,
          detectionResult: videoResult,
          attachments: [videoResult.source_video_url || userVideoMessage.sourceVideoUrl],
        }).catch((error) => console.warn("[保存视频检测历史失败]", error));
      }
    } catch (err) {
      console.error("[视频检测失败]", err);
      const lastMsg = agentStore.messages[agentStore.messages.length - 1];
      lastMsg.content = `视频检测失败：${err.message || err}`;
      lastMsg.loading = false;
      lastMsg.error = true;
    } finally {
      if (agentStore.abortController === cancelPolling) {
        agentStore.abortController = null;
        agentStore.setLoading(false);
      }
    }
  };
  input.click();
}

async function pollVideoProgress(taskId, userVideoMessage, isCancelled) {
  for (let attempt = 0; attempt < VIDEO_MAX_POLL_ATTEMPTS; attempt += 1) {
    if (isCancelled()) return;

    const status = await getVideoStatus(taskId);
    const lastMsg = agentStore.messages[agentStore.messages.length - 1];
    if (!lastMsg || lastMsg.role !== "assistant") return;

    if (status.source_video_url) {
      userVideoMessage.sourceVideoUrl = status.source_video_url;
    }

    if (status.status === "completed") {
      const videoResult = { ...(status.result || status), type: "video" };
      if (videoResult.source_video_url) {
        userVideoMessage.sourceVideoUrl = videoResult.source_video_url;
      }
      lastMsg.content = `视频检测完成！共处理 ${videoResult.processed_frames ?? 0} 帧，发现 ${videoResult.total_objects ?? 0} 个目标。`;
      lastMsg.loading = false;
      lastMsg.detectionResult = videoResult;
      scrollToBottom();
      return videoResult;
    }

    if (status.status === "failed") {
      lastMsg.content = `视频检测失败：${status.message || "处理失败"}`;
      lastMsg.loading = false;
      lastMsg.error = true;
      scrollToBottom();
      return;
    }

    const progress = Number.isFinite(status.progress) ? status.progress : 0;
    lastMsg.content = `视频处理中... ${progress}%`;
    scrollToBottom();
    await new Promise((resolve) => setTimeout(resolve, VIDEO_POLL_INTERVAL));
  }

  const lastMsg = agentStore.messages[agentStore.messages.length - 1];
  if (lastMsg?.role === "assistant") {
    lastMsg.content = "视频检测超时，请稍后通过历史任务查询结果。";
    lastMsg.loading = false;
    lastMsg.error = true;
  }
}

onMounted(() => {
  // 刷新后优先恢复用户上次打开的会话，找不到时回退到最新会话。
  refreshSessions()
    .then((sessions) => {
      const lastSessionId = localStorage.getItem(LAST_SESSION_STORAGE_KEY);
      const sessionToRestore = sessions.find(
        (session) => session.session_uuid === lastSessionId,
      );
      if (sessionToRestore) return openSession(sessionToRestore.session_uuid);
      if (sessions[0]) return openSession(sessions[0].session_uuid);
      return createNewChat();
    })
    .catch((error) => console.error("[初始化会话失败]", error));
});
</script>

<style lang="scss" scoped>
.chat-page {
  display: flex;
  height: 100%;
  background: #f5f5f5;
}
.session-sidebar {
  width: 220px;
  flex: 0 0 220px;
  display: flex;
  flex-direction: column;
  padding: 10px 8px;
  border-right: 1px solid #e0e0e0;
  background: #fff;
}
.new-session-button {
  align-self: flex-start;
  margin: 0 0 10px 4px;
}
.session-list {
  min-height: 0;
  overflow-y: auto;
}
.session-row {
  display: flex;
  align-items: center;
  min-width: 0;
  margin-bottom: 4px;
  border-radius: 6px;
  &:hover,
  &.active {
    background: #ecf5ff;
  }
}
.session-button {
  display: flex;
  flex: 1;
  min-width: 0;
  align-items: center;
  gap: 8px;
  padding: 9px 8px;
  border: 0;
  background: transparent;
  color: #303133;
  cursor: pointer;
  text-align: left;
}
.session-icon {
  width: 16px;
  flex: 0 0 16px;
}
.session-title {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.rename-session-button,
.delete-session-button {
  margin-right: 2px;
  color: #909399;
}
.chat-main {
  display: flex;
  min-width: 0;
  flex: 1;
  flex-direction: column;
}
/* ── 消息列表 ── */
.message-list {
  flex: 1;
  overflow-y: auto;
  padding: 20px;
}
.message-item {
  display: flex;
  margin-bottom: 16px;
  &.message-user {
    justify-content: flex-end;
  }
  &.message-assistant {
    justify-content: flex-start;
  }
}
.message-bubble {
  max-width: 70%;
  padding: 12px 16px;
  border-radius: 12px;
  line-height: 1.5;
  word-break: break-word;
}
.message-video {
  margin-top: 8px;
  video {
    display: block;
    width: min(360px, 100%);
    max-height: 240px;
    background: #000;
  }
}
.user-bubble {
  background: #409eff;
  color: white;
  border-bottom-right-radius: 4px;
}
.assistant-bubble {
  background: white;
  border: 1px solid #e0e0e0;
  border-bottom-left-radius: 4px;
}
.message-content {
  white-space: pre-wrap;
}
.markdown-body {
  /* markdown 渲染后的 HTML 样式 */
  h1,
  h2,
  h3 {
    margin-top: 8px;
    margin-bottom: 4px;
  }
  table {
    border-collapse: collapse;
    width: 100%;
    margin: 8px 0;
  }
  th,
  td {
    border: 1px solid #e0e0e0;
    padding: 4px 8px;
  }
  code {
    background: #f0f0f0;
    padding: 2px 4px;
    border-radius: 3px;
  }
}
.typing-indicator {
  display: flex;
  gap: 4px;
  span {
    width: 6px;
    height: 6px;
    background: #999;
    border-radius: 50%;
    animation: typing 1.2s infinite;
  }
  span:nth-child(2) {
    animation-delay: 0.2s;
  }
  span:nth-child(3) {
    animation-delay: 0.4s;
  }
}
/* ── 快捷操作栏 ── */
.quick-actions {
  display: flex;
  gap: 8px;
  padding: 12px 20px;
  border-top: 1px solid #e0e0e0;
  background: white;
}
/* ── 输入区域 ── */
.input-area {
  display: flex;
  gap: 8px;
  padding: 12px 20px;
  border-top: 1px solid #e0e0e0;
  background: white;
  .el-input {
    flex: 1;
  }
}
/* ── 附件预览 ── */
.message-attachment {
  margin-top: 8px;
  img {
    max-width: 200px;
    border-radius: 8px;
    border: 1px solid #e0e0e0;
  }
}
/* ── 多图附件网格 ── */
.message-attachments-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(80px, 1fr));
  gap: 8px;
  margin-top: 8px;
  img {
    width: 100%;
    height: 80px;
    object-fit: cover;
    border-radius: 6px;
    border: 1px solid #e0e0e0;
  }
}
/* ── 工具调用信息 ── */
.tool-call-info {
  margin-top: 8px;
  padding: 4px 8px;
  background: #f5f5f5;
  border-radius: 4px;
  font-size: 12px;
  color: #666;
}
@keyframes typing {
  0%,
  60%,
  100% {
    opacity: 0.3;
    transform: translateY(0);
  }
  30% {
    opacity: 1;
    transform: translateY(-4px);
  }
}
@media (max-width: 640px) {
  .session-sidebar {
    width: 48px;
    flex-basis: 48px;
    padding: 10px 4px;
  }
  .session-button {
    justify-content: center;
  }
  .session-title,
  .rename-session-button,
  .delete-session-button {
    display: none;
  }
  .message-bubble {
    max-width: 88%;
  }
  .quick-actions {
    padding: 12px;
    overflow-x: auto;
  }
  .input-area {
    padding: 12px;
  }
}
</style>
