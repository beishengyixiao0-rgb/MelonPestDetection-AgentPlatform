<template>
  <div class="conversation-page">
    <header class="page-header">
      <h1>🌿 会话列表</h1>
      <p class="subtitle">查看您的诊断会话记录</p>
    </header>

    <div class="page-content">
      <div class="session-list-container">
        <div class="list-header">
          <span class="list-title">会话列表</span>
          <span class="list-count">共 {{ sessions.length }} 个会话</span>
        </div>

        <div class="session-list">
          <div
            v-for="session in sessions"
            :key="session.id"
            class="session-item"
            :class="{
              active: selectedSessionId === session.id,
              pinned: session.is_pinned,
            }"
            @click="selectSession(session.id)"
          >
            <div class="session-content">
              <span v-if="session.is_pinned" class="pin-icon">📌</span>
              <span class="session-title">{{ session.title || "新对话" }}</span>
            </div>
            <div class="session-meta">
              <span class="session-count"
                >{{ session.message_count }} 条消息</span
              >
              <span class="session-time">{{
                formatTime(session.last_message_at)
              }}</span>
            </div>
          </div>

          <div v-if="sessions.length === 0" class="empty-state">
            <div class="empty-icon">📭</div>
            <div class="empty-text">暂无会话记录</div>
            <router-link to="/ai-chat" class="empty-action">
              开始新诊断
            </router-link>
          </div>
        </div>
      </div>

      <div class="detail-panel">
        <div v-if="selectedSession" class="detail-content">
          <div class="detail-header">
            <h2>{{ selectedSession.title || "新对话" }}</h2>
            <div class="detail-info">
              <span v-if="selectedSession.is_pinned" class="pinned-badge"
                >📌 已置顶</span
              >
              <span class="detail-time"
                >{{ formatTime(selectedSession.created_at) }} 创建</span
              >
            </div>
          </div>

          <div class="message-history">
            <div
              v-for="message in selectedMessages"
              :key="message.id"
              class="message-item"
              :class="{
                'message-user': message.role === 'user',
                'message-assistant': message.role === 'assistant',
              }"
            >
              <div class="message-avatar">
                {{ message.role === "user" ? "👤" : "🤖" }}
              </div>
              <div class="message-content">
                <div class="message-role">
                  {{ message.role === "user" ? "用户" : "AI助手" }}
                </div>
                <div class="message-text">{{ message.content }}</div>
                <div class="message-time">
                  {{ formatTime(message.created_at) }}
                </div>
              </div>
            </div>

            <div v-if="selectedMessages.length === 0" class="empty-messages">
              <div class="empty-icon">💬</div>
              <div class="empty-text">暂无消息</div>
            </div>
          </div>

          <div class="detail-actions">
            <router-link to="/ai-chat" class="continue-btn">
              继续对话 →
            </router-link>
          </div>
        </div>

        <div v-else class="detail-placeholder">
          <div class="placeholder-icon">📋</div>
          <div class="placeholder-text">选择一个会话查看详情</div>
          <div class="placeholder-hint">点击左侧会话列表中的项目</div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { agentStore } from "@/stores/agent";
import { computed, onMounted, ref } from "vue";

const sessions = ref([]);
const selectedSessionId = ref(null);
const selectedMessages = ref([]);

const selectedSession = computed(() => {
  return sessions.value.find((s) => s.id === selectedSessionId.value);
});

const formatTime = (timestamp) => {
  if (!timestamp) return "";
  const date = new Date(timestamp);
  const now = new Date();
  const diff = now - date;
  const minutes = Math.floor(diff / 60000);
  const hours = Math.floor(diff / 3600000);
  const days = Math.floor(diff / 86400000);

  if (minutes < 1) return "刚刚";
  if (minutes < 60) return `${minutes}分钟前`;
  if (hours < 24) return `${hours}小时前`;
  if (days < 7) return `${days}天前`;
  return (
    date.toLocaleDateString("zh-CN") +
    " " +
    date.toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit" })
  );
};

const loadSessions = async () => {
  await agentStore.loadSessions();
  sessions.value = agentStore.sessions;
};

const selectSession = async (sessionId) => {
  selectedSessionId.value = sessionId;
  await agentStore.loadSessionMessages(sessionId);
  selectedMessages.value = agentStore.messages;
};

onMounted(() => {
  loadSessions();
});
</script>

<style scoped>
.conversation-page {
  min-height: 100vh;
  background: #f8fafc;
}

.page-header {
  background: linear-gradient(135deg, #16a34a 0%, #15803d 100%);
  padding: 40px 60px;
  color: white;
}

.page-header h1 {
  font-size: 32px;
  font-weight: 700;
  margin: 0;
}

.subtitle {
  font-size: 16px;
  opacity: 0.9;
  margin: 8px 0 0 0;
}

.page-content {
  display: flex;
  gap: 24px;
  padding: 32px 60px;
  max-width: 1400px;
  margin: 0 auto;
}

.session-list-container {
  flex: 1;
  max-width: 400px;
  background: white;
  border-radius: 16px;
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.08);
  overflow: hidden;
}

.list-header {
  padding: 20px 24px;
  border-bottom: 1px solid #e5e7eb;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.list-title {
  font-size: 18px;
  font-weight: 600;
  color: #1f2937;
}

.list-count {
  font-size: 14px;
  color: #6b7280;
}

.session-list {
  padding: 16px;
  max-height: calc(100vh - 280px);
  overflow-y: auto;
}

.session-item {
  border: 1px solid #e5e7eb;
  border-radius: 12px;
  padding: 14px;
  cursor: pointer;
  transition: all 0.2s ease;
  background: #ffffff;
  margin-bottom: 10px;
}

.session-item:hover {
  background: #f9fafb;
  border-color: #16a34a;
  transform: translateX(4px);
}

.session-item.active {
  background: #ecfdf5;
  border-color: #16a34a;
  box-shadow: 0 4px 12px rgba(22, 163, 74, 0.15);
}

.session-item.pinned {
  border-left: 4px solid #f59e0b;
}

.session-content {
  display: flex;
  align-items: center;
  gap: 8px;
}

.pin-icon {
  font-size: 14px;
}

.session-title {
  font-size: 15px;
  font-weight: 600;
  color: #374151;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.session-title:hover {
  color: #16a34a;
}

.session-meta {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 13px;
  color: #9ca3af;
  margin-top: 6px;
}

.session-count {
  margin-right: 12px;
}

.session-time {
  flex-shrink: 0;
}

.empty-state {
  text-align: center;
  padding: 40px 20px;
}

.empty-icon {
  font-size: 48px;
  margin-bottom: 16px;
}

.empty-text {
  font-size: 16px;
  color: #6b7280;
  margin-bottom: 20px;
}

.empty-action {
  display: inline-block;
  background: #16a34a;
  color: white;
  padding: 10px 24px;
  border-radius: 8px;
  text-decoration: none;
  font-weight: 500;
  transition: all 0.2s ease;
}

.empty-action:hover {
  background: #15803d;
  transform: translateY(-2px);
}

.detail-panel {
  flex: 2;
  background: white;
  border-radius: 16px;
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.08);
  overflow: hidden;
}

.detail-content {
  padding: 24px;
}

.detail-header {
  padding-bottom: 20px;
  border-bottom: 1px solid #e5e7eb;
  margin-bottom: 20px;
}

.detail-header h2 {
  font-size: 22px;
  font-weight: 700;
  color: #1f2937;
  margin: 0;
}

.detail-info {
  display: flex;
  gap: 16px;
  margin-top: 8px;
}

.pinned-badge {
  font-size: 14px;
  color: #f59e0b;
  font-weight: 500;
}

.detail-time {
  font-size: 14px;
  color: #6b7280;
}

.message-history {
  max-height: calc(100vh - 420px);
  overflow-y: auto;
  padding-right: 8px;
}

.message-item {
  display: flex;
  gap: 12px;
  margin-bottom: 20px;
  padding: 14px;
  border-radius: 12px;
}

.message-user {
  background: #ecfdf5;
  border: 1px solid #dcfce7;
}

.message-assistant {
  background: #f8fafc;
  border: 1px solid #e5e7eb;
}

.message-avatar {
  font-size: 24px;
  flex-shrink: 0;
}

.message-content {
  flex: 1;
}

.message-role {
  font-size: 13px;
  font-weight: 600;
  color: #6b7280;
  margin-bottom: 6px;
}

.message-text {
  font-size: 15px;
  color: #374151;
  line-height: 1.6;
}

.message-time {
  font-size: 12px;
  color: #9ca3af;
  margin-top: 8px;
}

.empty-messages {
  text-align: center;
  padding: 40px 20px;
}

.detail-actions {
  margin-top: 20px;
  padding-top: 20px;
  border-top: 1px solid #e5e7eb;
}

.continue-btn {
  display: inline-block;
  background: #16a34a;
  color: white;
  padding: 12px 28px;
  border-radius: 10px;
  text-decoration: none;
  font-weight: 600;
  transition: all 0.2s ease;
}

.continue-btn:hover {
  background: #15803d;
  transform: translateY(-2px);
  box-shadow: 0 6px 18px rgba(22, 163, 74, 0.3);
}

.detail-placeholder {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 400px;
  color: #6b7280;
}

.placeholder-icon {
  font-size: 64px;
  margin-bottom: 20px;
}

.placeholder-text {
  font-size: 18px;
  font-weight: 500;
  margin-bottom: 8px;
}

.placeholder-hint {
  font-size: 14px;
  opacity: 0.7;
}
</style>
