/**
 * 公共文件上传 API
 */
import request from "@/utils/request";

export function uploadCommonFile(formData, onUploadProgress) {
  return request.post("/chat/upload", formData, {
    timeout: 180_000,
    onUploadProgress,
  });
}
