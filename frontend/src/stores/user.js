/**
 * 用户状态管理
 * 管理用户登录信息、Token、角色等
 */
import { defineStore } from 'pinia'
import { getUserInfoApi, getUserProfileApi, loginApi } from '@/api/auth'
import { useLocaleStore } from '@/stores/locale'

const TOKEN_KEY = 'rsod_token'
const USER_KEY = 'rsod_user'

export const useUserStore = defineStore('user', {
  state: () => ({
    // JWT Token
    token: localStorage.getItem(TOKEN_KEY) || '',
    // 用户信息
    user: JSON.parse(localStorage.getItem(USER_KEY) || 'null'),
  }),

  getters: {
    /** 是否已登录 */
    isLoggedIn: (state) => !!state.token,

    /** 用户名 */
    username: (state) => state.user?.username || '',

    /** 用户头像 */
    avatar: (state) => state.user?.avatar || '',

    /** 用户角色列表 */
    roles: (state) => state.user?.roles || [],

    /** 是否为管理员 */
    isSuperuser: (state) => state.user?.is_superuser || false,

    /** 后端当前使用 roles 数组标识管理员权限。 */
    isAdmin: (state) => Array.isArray(state.user?.roles) && state.user.roles.includes('admin'),
  },

  actions: {
    /**
     * 用户登录
     * @param {Object} credentials - { username, password }
     */
    async login(credentials) {
      const res = await loginApi(credentials)

      // 保存 Token
      this.token = res.access_token
      localStorage.setItem(TOKEN_KEY, res.access_token)

      // 保存用户信息
      this.user = res.user
      localStorage.setItem(USER_KEY, JSON.stringify(res.user))
      // 登录后优先使用用户在后端保存的语言偏好。
      useLocaleStore().applyLocale(res.user?.display_language || 'zh')

      return res
    },

    /**
     * 获取最新用户信息
     */
    async fetchUserInfo() {
      try {
        const user = await getUserInfoApi()
        this.user = user
        localStorage.setItem(USER_KEY, JSON.stringify(user))
        // 刷新用户信息时同步语言，保证多设备使用相同偏好。
        useLocaleStore().applyLocale(user?.display_language || 'zh')
      } catch {
        this.logout()
      }
    },

    /**
     * 获取包含角色、账号状态和检测统计的完整用户资料。
     * 管理员入口和管理员路由守卫依赖该方法刷新角色。
     */
    async fetchUserProfile() {
      try {
        const profile = await getUserProfileApi()
        this.user = {
          ...(this.user || {}),
          ...profile,
        }
        localStorage.setItem(USER_KEY, JSON.stringify(this.user))
        useLocaleStore().applyLocale(profile?.display_language || 'zh')
        return this.user
      } catch (error) {
        this.logout()
        throw error
      }
    },

    /**
     * 退出登录
     */
    logout() {
      this.token = ''
      this.user = null
      localStorage.removeItem(TOKEN_KEY)
      localStorage.removeItem(USER_KEY)
    },
  },
})
