<template>
  <aside class="sidebar">
    <router-link to="/" class="brand"> 🌿 AgriAgent </router-link>

    <button class="new-chat" @click="$emit('new-diagnosis')">
      ＋ 新建诊断
    </button>

    <div class="sidebar-section-title">最近会话</div>

    <div class="session-list">
      <div
        v-for="session in sessions"
        :key="session.id"
        class="session-item"
        :class="{
          active: String(currentSessionId) === String(session.id),
          pinned: session.is_pinned,
        }"
        :data-session-id="session.id"
        @click="$emit('select-session', session.id)"
      >
        <div class="session-content">
          <span v-if="session.is_pinned" class="pin-icon">📌</span>
          <span class="session-title">{{ session.title || "新对话" }}</span>
        </div>
        <div class="session-meta">
          <span class="session-count">{{ session.message_count ?? 0 }} 条消息</span>
          <span class="session-time">{{
            formatTime(session.last_message_at)
          }}</span>
        </div>
        <button
          class="more-btn"
          type="button"
          title="更多操作"
          aria-label="更多会话操作"
          @click.stop="toggleMenu(session.id, $event)"
        >
          ⋯
        </button>
      </div>

      <div v-if="sessions.length === 0" class="empty-sessions">
        <div class="empty-icon">💬</div>
        <div class="empty-text">暂无会话记录</div>
      </div>
    </div>

    <div class="sidebar-bottom">
      <div class="sidebar-section-title">功能导航</div>

      <router-link
        to="/ai-chat"
        class="nav-item"
        active-class="nav-item-active"
      >
        🤖 智能诊断
      </router-link>

      <router-link
        to="/data-analysis"
        class="nav-item"
        active-class="nav-item-active"
      >
        📊 数据分析
      </router-link>

      <router-link
        to="/history"
        class="nav-item"
        active-class="nav-item-active"
      >
        🕒 检测历史
      </router-link>
    </div>
  </aside>

  <Teleport to="body">
    <div
      v-if="activeMenuSessionId !== null"
      class="session-dropdown-menu"
      :style="dropdownStyle"
      @click.stop
    >
      <button type="button" class="dropdown-item" @click="handleRename">
        ✏️ 重命名
      </button>
      <button type="button" class="dropdown-item" @click="handleTogglePin">
        {{ isCurrentPinned ? "📌 取消置顶" : "📌 置顶" }}
      </button>
      <div class="dropdown-divider"></div>
      <button type="button" class="dropdown-item danger" @click="handleDelete">
        🗑️ 删除
      </button>
    </div>
  </Teleport>

  <Teleport to="body">
    <input
      v-if="editingSessionId !== null"
      ref="editInputRef"
      v-model="editTitle"
      class="session-rename-input"
      maxlength="200"
      aria-label="修改会话名称"
      @blur="saveEdit"
      @keyup.enter="saveEdit"
      @keyup.esc="cancelEdit"
    />
  </Teleport>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, ref } from 'vue'

const props = defineProps({
  sessions: {
    type: Array,
    default: () => [],
  },
  currentSessionId: {
    type: [Number, String],
    default: null,
  },
})

const emit = defineEmits([
  'new-diagnosis',
  'select-session',
  'toggle-pin',
  'delete-session',
  'rename-session',
])

const editingSessionId = ref(null)
const editTitle = ref('')
const activeMenuSessionId = ref(null)
const menuPosition = ref({ x: 0, y: 0 })
const editInputRef = ref(null)

const activeSession = computed(() => props.sessions.find(
  (session) => String(session.id) === String(activeMenuSessionId.value),
))

const isCurrentPinned = computed(() => Boolean(activeSession.value?.is_pinned))

const dropdownStyle = computed(() => ({
  left: `${menuPosition.value.x}px`,
  top: `${menuPosition.value.y}px`,
}))

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
  return date.toLocaleDateString("zh-CN");
}

const closeMenu = () => {
  activeMenuSessionId.value = null
  document.removeEventListener('click', closeMenu)
}

const toggleMenu = (sessionId, event) => {
  if (String(activeMenuSessionId.value) === String(sessionId)) {
    closeMenu()
    return
  }

  const rect = event.currentTarget.getBoundingClientRect()
  menuPosition.value = {
    x: Math.max(12, Math.min(window.innerWidth - 156, rect.right - 144)),
    y: Math.max(12, Math.min(window.innerHeight - 160, rect.top + 8)),
  }
  activeMenuSessionId.value = sessionId

  document.removeEventListener('click', closeMenu)
  window.setTimeout(() => document.addEventListener('click', closeMenu), 0)
}

const handleRename = () => {
  const sessionId = activeMenuSessionId.value
  const session = activeSession.value
  if (sessionId === null || !session) return

  editingSessionId.value = sessionId
  editTitle.value = session.title || ''
  closeMenu()

  nextTick(() => {
    const input = editInputRef.value
    const item = document.querySelector(`[data-session-id="${sessionId}"]`)
    if (!input || !item) return

    const rect = item.getBoundingClientRect()
    input.style.left = `${rect.left + 12}px`
    input.style.top = `${rect.top + 8}px`
    input.style.width = `${Math.max(140, rect.width - 24)}px`
    input.focus()
    input.select()
  })
}

const cancelEdit = () => {
  editingSessionId.value = null
  editTitle.value = ''
}

const saveEdit = () => {
  const sessionId = editingSessionId.value
  const title = editTitle.value.trim()
  if (sessionId !== null && title) emit('rename-session', sessionId, title)
  cancelEdit()
}

const handleTogglePin = () => {
  const sessionId = activeMenuSessionId.value
  if (sessionId !== null) emit('toggle-pin', sessionId)
  closeMenu()
}

const handleDelete = () => {
  const sessionId = activeMenuSessionId.value
  closeMenu()
  if (sessionId !== null && window.confirm('确定要删除这个会话吗？')) {
    emit('delete-session', sessionId)
  }
}

onBeforeUnmount(() => {
  document.removeEventListener('click', closeMenu)
})
</script>

<style scoped>
.sidebar {
  width: 260px;
  background: white;
  border-right: 1px solid #e5e7eb;
  padding: 20px;
  display: flex;
  flex-direction: column;
  height: 100vh;
  box-shadow: 2px 0 12px rgba(0, 0, 0, 0.04);
}

.brand {
  font-size: 20px;
  font-weight: 700;
  color: #16a34a;
  margin-bottom: 24px;
  text-decoration: none;
  display: block;
}

.new-chat {
  background: #16a34a;
  color: white;
  border: none;
  border-radius: 10px;
  padding: 12px;
  cursor: pointer;
  margin-bottom: 24px;
  font-weight: 600;
  transition: all 0.2s ease;
}

.new-chat:hover {
  transform: translateY(-1px);
  box-shadow: 0 6px 18px rgba(22, 163, 74, 0.25);
}

.session-list {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 8px;
  overflow-y: auto;
}

.session-item {
  border: 1px solid #e5e7eb;
  border-radius: 12px;
  padding: 12px;
  cursor: pointer;
  transition: all 0.2s ease;
  background: #ffffff;
  position: relative;
}

.session-item:hover {
  background: #f9fafb;
  border-color: #16a34a;
}

.session-item.active {
  background: #ecfdf5;
  border-color: #16a34a;
}

.session-item.pinned {
  border-left: 3px solid #f59e0b;
}

.session-content {
  display: flex;
  align-items: center;
  gap: 6px;
  padding-right: 26px;
}

.pin-icon {
  flex-shrink: 0;
  font-size: 12px;
}

.session-title {
  font-size: 14px;
  font-weight: 600;
  color: #374151;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.session-meta {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 12px;
  color: #9ca3af;
  margin-top: 4px;
  padding-right: 24px;
}

.more-btn {
  position: absolute;
  top: 50%;
  right: 6px;
  padding: 3px 7px;
  transform: translateY(-50%);
  border: 0;
  border-radius: 6px;
  background: transparent;
  color: #9ca3af;
  font-size: 18px;
  line-height: 1;
  cursor: pointer;
  opacity: 0;
  transition: 0.2s ease;
}

.session-item:hover .more-btn,
.session-item.active .more-btn,
.more-btn:focus-visible {
  opacity: 1;
}

.more-btn:hover {
  background: #f3f4f6;
  color: #374151;
}

.empty-sessions {
  padding: 28px 12px;
  text-align: center;
  color: #9ca3af;
}

.empty-icon {
  margin-bottom: 8px;
  font-size: 30px;
}

.empty-text {
  font-size: 13px;
}

.session-count {
  margin-right: 8px;
}

.session-time {
  flex-shrink: 0;
}

.sidebar-bottom {
  margin-top: auto;
  padding-top: 24px;
  border-top: 1px solid #e5e7eb;
}

.sidebar-section-title {
  font-size: 12px;
  font-weight: 700;
  color: #9ca3af;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  margin-bottom: 12px;
}

.nav-item {
  display: block;
  text-decoration: none;
  padding: 12px 14px;
  border-radius: 10px;
  color: #374151;
  margin-bottom: 8px;
  transition: all 0.2s ease;
  font-weight: 500;
}

.nav-item:hover {
  background: #f3f4f6;
}

.nav-item-active {
  background: #ecfdf5;
  color: #16a34a;
  font-weight: 600;
  border: 1px solid #bbf7d0;
}

:global(.session-dropdown-menu) {
  position: fixed;
  z-index: 9999;
  min-width: 144px;
  padding: 7px 0;
  overflow: hidden;
  border: 1px solid #e5e7eb;
  border-radius: 12px;
  background: #fff;
  box-shadow: 0 12px 38px rgba(15, 23, 42, 0.16);
}

:global(.session-dropdown-menu .dropdown-item) {
  width: 100%;
  padding: 9px 15px;
  border: 0;
  background: transparent;
  color: #374151;
  font-size: 14px;
  text-align: left;
  cursor: pointer;
}

:global(.session-dropdown-menu .dropdown-item:hover) {
  background: #f3f4f6;
}

:global(.session-dropdown-menu .dropdown-item.danger) {
  color: #dc2626;
}

:global(.session-dropdown-menu .dropdown-item.danger:hover) {
  background: #fef2f2;
}

:global(.session-dropdown-menu .dropdown-divider) {
  height: 1px;
  margin: 6px 0;
  background: #e5e7eb;
}

:global(.session-rename-input) {
  position: fixed;
  z-index: 10000;
  box-sizing: border-box;
  padding: 7px 10px;
  border: 2px solid #16a34a;
  border-radius: 7px;
  outline: none;
  background: #fff;
  color: #374151;
  font-size: 14px;
  font-weight: 600;
  box-shadow: 0 4px 12px rgba(15, 23, 42, 0.12);
}

@media (hover: none) {
  .more-btn {
    opacity: 1;
  }
}
</style>
