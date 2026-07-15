/**
 * Agent 对话附件上传 API
 *
 * 后端返回：{ image_path: '/tmp/rsod_uploads/xxx.jpg' }
 */
import request from '@/utils/request'

export function uploadCommonFile(formData, onUploadProgress) {
  return request.post('/chat/upload', formData, {
    timeout: 180_000,
    onUploadProgress,
  })
}
