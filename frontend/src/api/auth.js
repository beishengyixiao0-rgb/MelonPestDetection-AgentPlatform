/**
 * 认证相关 API 接口
 */
import request from '@/utils/request'

/**
 * 用户注册
 * @param {Object} data - { username, email, password }
 */
export function registerApi(data) {
    return request.post('/auth/register', data)
}

/**
 * 用户登录
 * @param {Object} data - { username, password }
 * @returns {Promise} - { access_token, token_type, user }
 */
export function loginApi(data) {
    return request.post('/auth/login', data)
}

/**
 * 获取当前用户信息（需要 Token）
 */
export function getUserInfoApi() {
    return request.get('/auth/me')
}

/** 获取包含角色、账号状态和检测统计的完整用户资料。 */
export function getUserProfileApi() {
    return request.get('/auth/profile')
}

/** 修改当前用户个人信息。 */
export function updateUserProfileApi(data) {
    return request.put('/auth/profile', data)
}

/** 保存当前用户的中英文显示偏好。 */
export function updateDisplayLanguageApi(display_language) {
    return request.put('/auth/preferences', { display_language })
}

/**
 * 忘记密码 - 向注册邮箱发送 6 位验证码
 * @param {Object} data - { email }
 */
export function forgotPasswordApi(data) {
    return request.post('/auth/forgot-password', data)
}

/**
 * 重置密码 - 验证邮箱和验证码并更新密码
 * @param {Object} data - { email, code, new_password }
 */
export function resetPasswordApi(data) {
    return request.post('/auth/reset-password', data)
}
