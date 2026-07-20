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

/** 获取后端统一维护的严重程度问卷配置。 */
export function getSeverityQuestionsApi() {
  return request.get('/history/severity-questions')
}

/** 提交指定检测任务、指定原始类别的严重程度问卷。 */
export function submitSeverityAssessmentApi(taskId, data) {
  return request.post(`/history/tasks/${taskId}/severity-assessment`, data)
}

/** 更新用户维护的治疗进度，不改变检测任务的技术状态。 */
export function updateTreatmentStatusApi(taskId, data) {
  return request.patch(`/history/tasks/${taskId}/treatment-status`, data)
}

/** 保存检测任务位置；后端默认同步生成天气环境风险。 */
export function updateTaskLocationApi(taskId, data, refreshWeather = true) {
  return request.patch(`/history/tasks/${taskId}/location`, data, {
    params: { refresh_weather: refreshWeather },
  })
}

/** 使用任务已保存的位置重新计算天气环境风险。 */
export function refreshTaskWeatherRiskApi(taskId) {
  return request.get(`/history/tasks/${taskId}/weather-risk`)
}
