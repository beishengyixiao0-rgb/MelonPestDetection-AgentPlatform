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

/**
 * 获取当前用户完整资料（包含角色、账号状态和检测统计）
 */
export function getUserProfileApi() {
    return request.get('/auth/profile')
}

/** 保存当前用户的界面/模型回复语言偏好。 */
export function updateDisplayLanguageApi(displayLanguage) {
    return request.put('/auth/preferences', {
        display_language: displayLanguage === 'en' ? 'en' : 'zh',
    })
}

/**
 * 忘记密码 - 生成重置令牌
 * @param {Object} data - { email }
 */
export function forgotPasswordApi(data) {
    return request.post('/auth/forgot-password', data)
}

/**
 * 重置密码 - 验证令牌并更新密码
 * @param {Object} data - { token, new_password }
 */
export function resetPasswordApi(data) {
    return request.post('/auth/reset-password', data)
}
