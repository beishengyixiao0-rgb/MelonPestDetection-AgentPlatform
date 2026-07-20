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

    /** 用后端历史消息替换当前会话内容。 */
    setMessages(messages) {
      this.messages = messages
    },

    /** 设置当前持久化会话标识。 */
    setCurrentSessionId(sessionId) {
      this.currentSessionId = sessionId
    },

    /** 更新当前用户可见的会话列表。 */
    setSessions(sessions) {
      this.sessions = sessions
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
        this.sessions = Array.isArray(response?.sessions) ? response.sessions : []
        this.sortSessions()
      } catch (error) {
        console.error('加载会话列表失败:', error)
        this.sessions = []
      }
    },

    /** 加载历史消息，并把持久化的工具结果恢复成检测卡片数据 */
    async loadSessionMessages(sessionId) {
      try {
        const response = await request.get(`/chat/sessions/${sessionId}`)
        const history = Array.isArray(response?.messages) ? response.messages : []

        const restoredMessages = history.map((msg) => {
          let toolMetadata = msg.tool_result || null
          if (typeof toolMetadata === 'string') {
            try {
              toolMetadata = JSON.parse(toolMetadata)
            } catch {
              toolMetadata = null
            }
          }

          const attachments = Array.isArray(toolMetadata?.attachments)
            ? toolMetadata.attachments.filter(Boolean)
            : []
          const isDetectionResult = toolMetadata
            && typeof toolMetadata === 'object'
            && !Array.isArray(toolMetadata)
            && !Array.isArray(toolMetadata.attachments)
            && (
              'total_objects' in toolMetadata
              || 'detections' in toolMetadata
              || 'annotated_image_base64' in toolMetadata
              || 'annotated_image_url' in toolMetadata
              || 'annotated_images' in toolMetadata
              || toolMetadata.type === 'video'
            )
          const detectionResult = isDetectionResult ? toolMetadata : null
          const isAgentResult = detectionResult && Array.isArray(msg.tool_calls) && msg.tool_calls.length
          const isVideoMessage = msg.role === 'user' && (
            msg.content?.startsWith('[视频检测]')
            || msg.content?.includes('[本轮已上传视频附件]')
          )

          return {
            id: msg.id,
            role: msg.role,
            content: msg.content,
            type: isVideoMessage
              ? 'video'
              : attachments.length === 1
                ? 'image'
              : detectionResult
                ? (isAgentResult ? 'agent-analysis' : 'diagnosis')
                : undefined,
            imageUrl: !isVideoMessage && attachments.length === 1 ? attachments[0] : undefined,
            images: !isVideoMessage && attachments.length > 1 ? attachments : undefined,
            videoUrl: isVideoMessage && attachments.length ? attachments[0] : undefined,
            detectionResult,
            agent_used: msg.agent_used,
            tool_calls: msg.tool_calls,
            tool_result: msg.tool_result,
            createdAt: msg.created_at,
          }
        })

        // 兼容此前保存的 attachments: []：从下一条视频检测结果恢复用户原视频。
        restoredMessages.forEach((message, index) => {
          if (message.type !== 'video' || message.videoUrl) return

          const nextUserIndex = restoredMessages.findIndex(
            (item, itemIndex) => itemIndex > index && item.role === 'user',
          )
          const searchEnd = nextUserIndex === -1 ? restoredMessages.length : nextUserIndex
          const resultMessage = restoredMessages
            .slice(index + 1, searchEnd)
            .find((item) => item.detectionResult?.source_video_url)

          if (resultMessage) message.videoUrl = resultMessage.detectionResult.source_video_url
        })

        this.messages = restoredMessages
        this.currentSessionId = response?.session?.session_uuid || sessionId
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
          (session) => String(this.getSessionKey(session)) !== String(sessionId),
        )
        if (String(this.currentSessionId) === String(sessionId)) this.newChat()
        return true
      } catch (error) {
        console.error('删除会话失败:', error)
        return false
      }
    },

    /** 修改会话标题 */
    async renameSession(sessionId, newTitle) {
      const title = newTitle?.trim()
      if (!title) return false

      try {
        const response = await request.patch(`/chat/sessions/${sessionId}`, { title })
        const session = this.sessions.find(
          (item) => String(this.getSessionKey(item)) === String(sessionId),
        )

        if (session) session.title = response?.title || title
        return true
      } catch (error) {
        console.error('重命名会话失败:', error)
        return false
      }
    },

    /** 获取后端对外使用的会话 UUID，并兼容旧数据 */
    getSessionKey(session) {
      return session?.session_uuid ?? session?.id ?? null
    },

    /** 快捷检测前确保存在一个可持久化会话 */
    async ensureSession() {
      if (this.currentSessionId) return this.currentSessionId

      try {
        const session = await request.post('/chat/sessions')
        const sessionId = this.getSessionKey(session)
        if (!sessionId) return null

        this.currentSessionId = sessionId
        this.updateSessionList(session)
        return sessionId
      } catch (error) {
        console.error('创建会话失败:', error)
        return null
      }
    },

    /** 保存绕过 LLM 的快捷检测消息与结果 */
    async saveQuickDetection({ userContent, assistantContent, detectionResult, attachments = [] }) {
      const sessionId = await this.ensureSession()
      if (!sessionId) return false

      try {
        await request.post(
          `/chat/sessions/${sessionId}/quick-detection`,
          {
            user_content: userContent,
            assistant_content: assistantContent,
            detection_result: detectionResult,
            attachments,
          },
          { timeout: 120_000 },
        )
        await this.loadSessions()
        return true
      } catch (error) {
        console.error('保存快捷检测历史失败:', error)
        return false
      }
    },

    /** 会话按最近消息时间排列 */
    sortSessions() {
      this.sessions.sort(
        (a, b) => new Date(b.last_message_at || b.created_at || 0)
          - new Date(a.last_message_at || a.created_at || 0),
      )
    },

    updateSessionList(session) {
      const sessionId = this.getSessionKey(session)
      const index = this.sessions.findIndex(
        (item) => String(this.getSessionKey(item)) === String(sessionId),
      )
      if (index >= 0) this.sessions[index] = session
      else this.sessions.unshift(session)

      this.sortSessions()
    },
  },
})
