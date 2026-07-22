/**
 * Axios 请求封装
 * - 统一 baseURL 配置
 * - 请求拦截器：自动注入 JWT Token
 * - 响应拦截器：统一错误处理、Token 过期处理
 */
import axios from 'axios'
import { ElMessage } from 'element-plus'
import { useUserStore } from '@/stores/user'
import { useLocaleStore } from '@/stores/locale'
import router from '@/router'

// ── 创建 Axios 实例 ──────────────────────────────────
const request = axios.create({
  baseURL: '/api',               // 配合 Vite proxy，实际请求转发到后端
  timeout: 30000,                // 请求超时 30 秒
  headers: {
    'Content-Type': 'application/json',
  },
})

// ── 请求拦截器 ──────────────────────────────────────
request.interceptors.request.use(
  (config) => {
    // FormData 必须由浏览器自动设置 multipart/form-data boundary。
    // 全局 JSON Content-Type 会导致 FastAPI 收不到 file/files 字段并返回 422。
    if (typeof FormData !== 'undefined' && config.data instanceof FormData) {
      config.headers.delete?.('Content-Type')
      delete config.headers['Content-Type']
    }

    // 从 Pinia store 获取 Token，自动注入请求头
    const userStore = useUserStore()
    const localeStore = useLocaleStore()
    // 语言随每次请求传递，后端无需共享全局状态。
    config.headers['X-Display-Language'] = localeStore.locale
    if (userStore.token) {
      config.headers.Authorization = `Bearer ${userStore.token}`
    }
    return config
  },
  (error) => {
    return Promise.reject(error)
  },
)

// ── 响应拦截器 ──────────────────────────────────────
request.interceptors.response.use(
  (response) => {
    // 请求成功，直接返回响应数据
    return response.data
  },
  (error) => {
    const { response } = error

    if (response) {
      switch (response.status) {
        case 401:
          // 登录接口的 401 表示凭据错误，应由 LoginPage 展示后端 detail，
          // 不能误提示为“登录已过期”或重复跳转登录页。
          if (error.config?.url === '/auth/login') break
          // Token 过期或无效，清除用户信息并跳转登录页
          ElMessage.error('登录已过期，请重新登录')
          const userStore = useUserStore()
          userStore.logout()
          router.push('/login')
          break

        case 403:
          ElMessage.error('没有权限执行此操作')
          break
        case 404:
          ElMessage.error('请求的资源不存在')
          break

        case 422:
          // Pydantic 验证错误
          const detail = response.data?.detail
          if (Array.isArray(detail)) {
            ElMessage.error(detail[0]?.msg || '参数验证失败')
          } else {
            ElMessage.error(detail || '参数验证失败')
          }
          break

        case 500:
          ElMessage.error('服务器内部错误')
          break

        default:
          ElMessage.error(response.data?.detail || `请求失败 (${response.status})`)
      }
    } else {
      // 网络错误或请求超时
      ElMessage.error('网络连接异常，请检查后端服务是否启动')
    }

    return Promise.reject(error)
  },
)

export default request
