import request from '@/utils/request'

export function getAdminUsersApi() {
  return request.get('/user/list')
}

export function createAdminUserApi(data) {
  return request.post('/user/create', null, { params: data })
}

export function updateAdminUserApi(userId, data) {
  return request.put(`/user/${userId}`, null, { params: data })
}

/** 后端为软删除：禁用账号并保留检测、训练和对话历史。 */
export function disableAdminUserApi(userId) {
  return request.delete(`/user/${userId}`)
}

/** 恢复已禁用账号；后端接口为幂等操作。 */
export function enableAdminUserApi(userId) {
  return request.patch(`/user/${userId}/enable`)
}
