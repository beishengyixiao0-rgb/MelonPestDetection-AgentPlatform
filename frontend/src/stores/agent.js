/**
 * 智能体对话状态管理
 * 管理对话会话列表、当前会话消息等
 */
import { defineStore } from 'pinia'
import request from '@/utils/request'

export const useAgentStore = defineStore('agent', {
  state: () => ({
    // 当前会话 ID
    currentSessionId: null,

    // 当前会话的消息列表
    messages: [],

    // 从首页带入 ChatPage 的一次性首问
    pendingPrompt: null,

    // 会话列表
    sessions: [],

    // 是否正在等待 AI 响应
    isLoading: false,

    // 中断函数（用于取消 SSE 流式请求）
    abortController: null,
  }),

  getters: {
    /** 消息数量 */
    messageCount: (state) => state.messages.length,

    /** 是否有会话 */
    hasSession: (state) => state.sessions.length > 0,
  },

  actions: {
    /** 添加一条消息 */
    addMessage(message) {
      this.messages.push(message)
    },

    /** 从首页开启一段新对话，并暂存首条自然语言消息 */
    queueHomePrompt(content, options = {}) {
      this.newChat()
      this.pendingPrompt = {
        content,
        mode: options.mode || null,
        files: Array.from(options.files || []),
        createdAt: Date.now(),
      }
    },

    /** ChatPage 只消费一次，防止返回页面或刷新时重复发送 */
    consumePendingPrompt() {
      const prompt = this.pendingPrompt
      this.pendingPrompt = null
      return prompt
    },

    /** 更新最后一条 AI 消息（用于流式追加） */
    updateLastAssistantMessage(content) {
      const lastMsg = this.messages[this.messages.length - 1]
      if (lastMsg && lastMsg.role === 'assistant') {
        lastMsg.content = content
      }
    },

    /** 设置加载状态 */
    setLoading(loading) {
      this.isLoading = loading
    },

    /** 中断当前流式请求 */
    abort() {
      if (this.abortController) {
        this.abortController()
        this.abortController = null
        this.isLoading = false
      }
    },

    /** 新建对话 */
    newChat() {
      this.currentSessionId = null
      this.messages = []
      this.pendingPrompt = null
      this.abort()
    },

    /** 清除所有状态 */
    clear() {
      this.currentSessionId = null
      this.messages = []
      this.sessions = []
      this.pendingPrompt = null
      this.abort()
    },

    /** 从后端加载当前用户的会话列表 */
    async loadSessions() {
      try {
        const response = await request.get('/chat/sessions')
        this.sessions = Array.isArray(response?.data) ? response.data : []
        this.sortSessions()
      } catch (error) {
        console.error('加载会话列表失败:', error)
        this.sessions = []
      }
    },

    /** 加载历史消息，并把持久化的工具结果恢复成检测卡片数据 */
    async loadSessionMessages(sessionId) {
      try {
        const response = await request.get(`/chat/sessions/${sessionId}/messages`)
        const history = Array.isArray(response?.data) ? response.data : []

        this.messages = history.map((msg) => {
          let detectionResult = msg.tool_result || null
          if (typeof detectionResult === 'string') {
            try {
              detectionResult = JSON.parse(detectionResult)
            } catch {
              detectionResult = null
            }
          }

          return {
            id: msg.id,
            role: msg.role,
            content: msg.content,
            type: detectionResult ? 'agent-analysis' : undefined,
            detectionResult,
            agent_used: msg.agent_used,
            tool_calls: msg.tool_calls,
            tool_result: msg.tool_result,
            createdAt: msg.created_at,
          }
        })
        this.currentSessionId = sessionId
      } catch (error) {
        console.error('加载会话消息失败:', error)
        this.messages = []
        this.currentSessionId = null
      }
    },

    async deleteSession(sessionId) {
      try {
        await request.delete(`/chat/sessions/${sessionId}`)
        this.sessions = this.sessions.filter(
          (session) => String(session.id) !== String(sessionId),
        )
        if (String(this.currentSessionId) === String(sessionId)) this.newChat()
        return true
      } catch (error) {
        console.error('删除会话失败:', error)
        return false
      }
    },

    /** 置顶或取消置顶会话；等待后端提供对应接口 */
    async togglePinSession(sessionId) {
      try {
        const response = await request.put(`/chat/sessions/${sessionId}/pin`)
        const payload = response?.data ?? response
        const session = this.sessions.find(
          (item) => String(item.id) === String(sessionId),
        )

        if (session) {
          session.is_pinned = Boolean(payload?.is_pinned)
          this.sortSessions()
        }
        return true
      } catch (error) {
        console.error('切换置顶失败:', error)
        return false
      }
    },

    /** 修改会话标题；等待后端提供对应接口 */
    async renameSession(sessionId, newTitle) {
      const title = newTitle?.trim()
      if (!title) return false

      try {
        const response = await request.put(`/chat/sessions/${sessionId}/rename`, { title })
        const payload = response?.data ?? response
        const session = this.sessions.find(
          (item) => String(item.id) === String(sessionId),
        )

        if (session) session.title = payload?.title || title
        return true
      } catch (error) {
        console.error('重命名会话失败:', error)
        return false
      }
    },

    /** 会话始终按“置顶优先、最近消息优先”排列 */
    sortSessions() {
      this.sessions.sort((a, b) => {
        if (Boolean(a.is_pinned) !== Boolean(b.is_pinned)) {
          return a.is_pinned ? -1 : 1
        }
        return new Date(b.last_message_at || 0) - new Date(a.last_message_at || 0)
      })
    },

    updateSessionList(session) {
      const index = this.sessions.findIndex((item) => item.id === session.id)
      if (index >= 0) this.sessions[index] = session
      else this.sessions.unshift(session)

      this.sortSessions()
    },
  },
})
