/**
 * 智能体对话状态管理
 * 管理对话会话列表、当前会话消息等
 */
import request from "@/utils/request";
import { defineStore } from "pinia";

export const useAgentStore = defineStore("agent", {
  state: () => ({
    currentSessionId: null,

    messages: [],

    pendingPrompt: null,

    sessions: [],

    isLoading: false,

    abortController: null,
  }),

  getters: {
    messageCount: (state) => state.messages.length,

    hasSession: (state) => state.sessions.length > 0,
  },

  actions: {
    addMessage(message) {
      this.messages.push(message);
    },

    queueHomePrompt(content) {
      this.newChat();
      this.pendingPrompt = {
        content,
        createdAt: Date.now(),
      };
    },

    consumePendingPrompt() {
      const prompt = this.pendingPrompt;
      this.pendingPrompt = null;
      return prompt;
    },

    updateLastAssistantMessage(content) {
      const lastMsg = this.messages[this.messages.length - 1];
      if (lastMsg && lastMsg.role === "assistant") {
        lastMsg.content = content;
      }
    },

    setLoading(loading) {
      this.isLoading = loading;
    },

    abort() {
      if (this.abortController) {
        this.abortController();
        this.abortController = null;
        this.isLoading = false;
      }
    },

    newChat() {
      this.currentSessionId = null;
      this.messages = [];
      this.pendingPrompt = null;
      this.abort();
    },

    clear() {
      this.currentSessionId = null;
      this.messages = [];
      this.sessions = [];
      this.pendingPrompt = null;
      this.abort();
    },

    async loadSessions() {
      try {
        const response = await request.get("/chat/sessions");
        if (response && response.data) {
          this.sessions = response.data;
        }
      } catch (error) {
        console.error("加载会话列表失败:", error);
        this.sessions = [];
      }
    },

    async loadSessionMessages(sessionId) {
      try {
        const response = await request.get(
          `/chat/sessions/${sessionId}/messages`,
        );
        if (response && response.data) {
          this.messages = response.data.map((msg) => ({
            id: msg.id,
            role: msg.role,
            content: msg.content,
            agent_used: msg.agent_used,
            tool_calls: msg.tool_calls,
            tool_result: msg.tool_result,
            createdAt: msg.created_at,
          }));
          this.currentSessionId = sessionId;
        }
      } catch (error) {
        console.error("加载会话消息失败:", error);
        this.messages = [];
        this.currentSessionId = null;
      }
    },

    async deleteSession(sessionId) {
      try {
        const response = await request.delete(`/chat/sessions/${sessionId}`);
        if (response && response.code === 200) {
          this.sessions = this.sessions.filter((s) => s.id !== sessionId);
          if (this.currentSessionId === sessionId) {
            this.newChat();
          }
        }
      } catch (error) {
        console.error("删除会话失败:", error);
      }
    },

    async togglePinSession(sessionId) {
      try {
        const response = await request.put(`/chat/sessions/${sessionId}/pin`);
        if (response && response.data) {
          const session = this.sessions.find((s) => s.id === sessionId);
          if (session) {
            session.is_pinned = response.data.is_pinned;
            this.sessions.sort((a, b) => {
              if (a.is_pinned !== b.is_pinned) {
                return a.is_pinned ? -1 : 1;
              }
              return new Date(b.last_message_at || 0) - new Date(a.last_message_at || 0);
            });
          }
        }
      } catch (error) {
        console.error("切换置顶失败:", error);
      }
    },

    async renameSession(sessionId, newTitle) {
      try {
        const response = await request.put(`/chat/sessions/${sessionId}/rename`, {
          title: newTitle,
        });
        if (response && response.data) {
          const session = this.sessions.find((s) => s.id === sessionId);
          if (session) {
            session.title = response.data.title;
          }
        }
      } catch (error) {
        console.error("重命名会话失败:", error);
      }
    },

    updateSessionList(session) {
      const index = this.sessions.findIndex((s) => s.id === session.id);
      if (index >= 0) {
        this.sessions[index] = session;
        this.sessions.sort((a, b) => {
          if (a.is_pinned !== b.is_pinned) {
            return a.is_pinned ? -1 : 1;
          }
          return new Date(b.last_message_at || 0) - new Date(a.last_message_at || 0);
        });
      } else {
        this.sessions.unshift(session);
      }
    },
  },
});
