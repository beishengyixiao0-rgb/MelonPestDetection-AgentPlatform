/**
 * 检测历史相关 API。
 * 所有接口均由 request 自动携带登录 Token 和显示语言。
 */
import request from '@/utils/request'

export function getHistoryTasksApi(params = {}) {
  return request.get('/history/tasks', { params })
}

export function getHistorySummaryApi() {
  return request.get('/history/summary')
}

export function getHistoryScenesApi() {
  return request.get('/history/scenes')
}

export function getHistoryTaskDetailApi(taskId) {
  return request.get(`/history/tasks/${taskId}`)
}

export function deleteHistoryTaskApi(taskId) {
  return request.delete(`/history/tasks/${taskId}`)
}
