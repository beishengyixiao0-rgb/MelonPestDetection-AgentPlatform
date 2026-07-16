/**
 * 知识库相关 API。
 * 目前仅供管理员在页面中手动重建项目内知识库索引使用。
 */
import request from '@/utils/request'

/**
 * 强制重新解析知识库文件并生成向量索引。
 * 重建过程会调用 Embedding 服务，单独设置较长超时以避免默认 30 秒超时。
 */
export function rebuildKnowledgeIndexApi() {
  return request.post('/knowledge/build?force_rebuild=true', null, {
    timeout: 300000,
  })
}
