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
  return request.post("/detection/single", formData, {
    timeout: 60_000,
  });
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