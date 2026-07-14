/**
 * Detection API
 * 快捷检测接口（绕过 LLM）
 */

import request from "@/utils/request";

/**
 * 单图检测
 *
 * @param {FormData} formData
 * @returns {Promise}
 */
export function detectSingle(formData) {
  return request.post("/training/predict", formData, {
    headers: { "Content-Type": "multipart/form-data" },
    timeout: 300_000,
  });
}

/**
 * 获取当前登录用户的训练任务，用于选择已完成模型。
 */
export function getTrainingTasks() {
  return request.get("/training/tasks");
}

/**
 * 批量图片检测
 *
 * @param {FormData} formData
 * @returns {Promise}
 */
export function detectBatch(formData) {
  return request.post("/detection/batch", formData, {
    timeout: 120_000,
  });
}

/**
 * ZIP 压缩包检测
 *
 * @param {FormData} formData
 * @returns {Promise}
 */
export function detectZip(formData) {
  return request.post("/detection/zip", formData, {
    timeout: 180_000,
  });
}

/**
 * 获取检测任务状态
 *
 * @param {number|string} taskId
 * @returns {Promise}
 */
export function getDetectionStatus(taskId) {
  return request.get(`/detection/status/${taskId}`);
}


/**
 * 视频检测
 * @param {FormData} formData - 包含视频文件的 FormData
 * @returns {Promise} { task_id, status, message }
 */
export function detectVideo(formData) {
  return request.post("/detection/video", formData, {
    timeout: 120000, // 视频上传与处理耗时较长
  });
}

/**
 * 查询视频检测任务状态
 * @param {number|string} taskId - 视频检测任务 ID
 * @returns {Promise} { status, progress, result, ... }
 */
export function getVideoStatus(taskId) {
  return request.get(`/detection/video/status/${taskId}`);
}