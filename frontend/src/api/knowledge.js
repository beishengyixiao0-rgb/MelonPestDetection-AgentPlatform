/** 知识库相关 API。 */
import request from '@/utils/request'

/** 普通用户提交知识文档，后端仅接受 .md / .txt。 */
export function submitKnowledgeDocumentApi(file, title = '') {
  const formData = new FormData()
  formData.append('file', file)

  return request.post('/knowledge/documents', formData, {
    params: title.trim() ? { title: title.trim() } : undefined,
    timeout: 60000,
  })
}

/** 查看当前用户自己的投稿及审核状态。 */
export function getMyKnowledgeSubmissionsApi(params = {}) {
  return request.get('/knowledge/my-submissions', { params })
}

/** 查看已经审核发布的公共知识文档。 */
export function getPublishedKnowledgeDocumentsApi(params = {}) {
  return request.get('/knowledge/documents', { params })
}

export function getKnowledgeDocumentDetailApi(documentId) {
  return request.get(`/knowledge/documents/${documentId}`)
}

export function getAdminKnowledgeDocumentsApi(params = {}) {
  return request.get('/knowledge/admin/documents', { params })
}

export function approveKnowledgeDocumentApi(documentId) {
  return request.put(`/knowledge/admin/${documentId}/approve`, null, {
    timeout: 300000,
  })
}

export function rejectKnowledgeDocumentApi(documentId, reviewComment) {
  return request.put(`/knowledge/admin/${documentId}/reject`, null, {
    params: { review_comment: reviewComment },
  })
}

export function deleteKnowledgeDocumentApi(documentId) {
  return request.delete(`/knowledge/admin/${documentId}`)
}

export function reindexKnowledgeDocumentApi(documentId) {
  return request.post(`/knowledge/admin/${documentId}/reindex`, null, {
    timeout: 300000,
  })
}

/**
 * 强制重新解析知识库文件并生成向量索引。
 * 重建过程会调用 Embedding 服务，单独设置较长超时以避免默认 30 秒超时。
 */
export function rebuildKnowledgeIndexApi() {
  return request.post('/knowledge/build?force_rebuild=true', null, {
    timeout: 300000,
  })
}
