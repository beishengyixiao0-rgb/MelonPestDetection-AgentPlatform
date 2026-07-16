<template>
  <aside class="sidebar">
    <router-link to="/" class="brand"> 🌿 AgriAgent </router-link>

    <button class="new-chat" @click="$emit('new-diagnosis')">
      + New Diagnosis
    </button>

    <div class="sidebar-section-title">Recent Diagnoses</div>

    <div class="session-list">
      <div
        v-for="session in sessions"
        :key="session.id"
        class="session-item"
        :class="{
          active: currentSessionId === session.id,
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
          <span class="session-count">{{ session.message_count }} 条消息</span>
          <span class="session-time">{{
            formatTime(session.last_message_at)
          }}</span>
        </div>
        <button
          class="more-btn"
          @click.stop="toggleMenu(session.id)"
          title="更多操作"
        >
          ⋯
        </button>
      </div>

      <div v-if="sessions.length === 0" class="empty-sessions">
        <div class="empty-icon">📭</div>
        <div class="empty-text">暂无会话记录</div>
      </div>
    </div>

    <div class="sidebar-bottom">
      <div class="sidebar-section-title">Navigation</div>

      <router-link
        to="/ai-chat"
        class="nav-item"
        active-class="nav-item-active"
      >
        🤖 AI Diagnosis
      </router-link>

      <router-link
        to="/data-analysis"
        class="nav-item"
        active-class="nav-item-active"
      >
        📊 Data Analysis
      </router-link>

      <router-link
        to="/history"
        class="nav-item"
        active-class="nav-item-active"
      >
        🕒 History
      </router-link>
    </div>
  </aside>

  <Teleport to="body">
    <div
      v-if="activeMenuSessionId !== null"
      class="dropdown-menu"
      :style="dropdownStyle"
      @click.stop
    >
      <div class="dropdown-item" @click="handleRename">✏️ 重命名</div>
      <div class="dropdown-item" @click="handleTogglePin">
        {{ isCurrentPinned ? "📌 取消置顶" : "📌 置顶" }}
      </div>
      <div class="dropdown-divider"></div>
      <div class="dropdown-item danger" @click="handleDelete">🗑️ 删除</div>
    </div>
  </Teleport>

  <Teleport to="body">
    <input
      v-if="editingSessionId !== null"
      ref="editInputRef"
      v-model="editTitle"
      class="rename-input"
      @blur="saveEdit"
      @keyup.enter="saveEdit"
      @keyup.esc="cancelEdit"
    />
  </Teleport>
</template>

<script setup>
import { computed, nextTick, ref } from "vue";

const editingSessionId = ref(null);
const editTitle = ref("");
const activeMenuSessionId = ref(null);
const menuPosition = ref({ x: 0, y: 0 });
const editInputRef = ref(null);

const props = defineProps({
  sessions: {
    type: Array,
    default: () => [],
  },
  currentSessionId: {
    type: Number,
    default: null,
  },
});

const emit = defineEmits([
  "new-diagnosis",
  "select-session",
  "toggle-pin",
  "delete-session",
  "rename-session",
]);

const activeSession = computed(() => {
  return props.sessions.find((s) => s.id === activeMenuSessionId.value);
});

const isCurrentPinned = computed(() => {
  return activeSession.value?.is_pinned || false;
});

const dropdownStyle = computed(() => ({
  left: `${menuPosition.value.x}px`,
  top: `${menuPosition.value.y}px`,
}));

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
};

const toggleMenu = (sessionId) => {
  if (activeMenuSessionId.value === sessionId) {
    activeMenuSessionId.value = null;
    return;
  }

  const event = window.event;
  const target = event.currentTarget;
  const rect = target.getBoundingClientRect();

  menuPosition.value = {
    x: rect.left - 120,
    y: rect.top + 8,
  };

  activeMenuSessionId.value = sessionId;

  document.addEventListener("click", closeMenu);
};

const closeMenu = () => {
  activeMenuSessionId.value = null;
  document.removeEventListener("click", closeMenu);
};

const handleRename = () => {
  closeMenu();
  editingSessionId.value = activeMenuSessionId.value;
  editTitle.value = activeSession.value?.title || "";

  nextTick(() => {
    if (editInputRef.value) {
      const item = document.querySelector(
        `[data-session-id="${editingSessionId.value}"]`,
      );
      if (item) {
        const rect = item.getBoundingClientRect();
        editInputRef.value.style.left = `${rect.left + 30}px`;
        editInputRef.value.style.top = `${rect.top + 8}px`;
        editInputRef.value.style.width = `${rect.width - 60}px`;
      }
      editInputRef.value.focus();
      editInputRef.value.select();
    }
  });
};

const saveEdit = () => {
  const trimmed = editTitle.value.trim();
  if (trimmed && editingSessionId.value) {
    emit("rename-session", editingSessionId.value, trimmed);
  }
  cancelEdit();
};

const cancelEdit = () => {
  editingSessionId.value = null;
  editTitle.value = "";
};

const handleTogglePin = () => {
  if (activeMenuSessionId.value) {
    emit("toggle-pin", activeMenuSessionId.value);
  }
  closeMenu();
};

const handleDelete = () => {
  if (activeMenuSessionId.value && confirm("确定要删除这个会话吗？")) {
    emit("delete-session", activeMenuSessionId.value);
  }
  closeMenu();
};
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

.sidebar-section-title {
  font-size: 12px;
  font-weight: 700;
  color: #9ca3af;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  margin-bottom: 12px;
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
}

.pin-icon {
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
}

.session-count {
  margin-right: 8px;
}

.session-time {
  flex-shrink: 0;
}

.more-btn {
  position: absolute;
  right: 8px;
  top: 50%;
  transform: translateY(-50%);
  background: transparent;
  border: none;
  font-size: 18px;
  color: #9ca3af;
  cursor: pointer;
  padding: 4px 8px;
  border-radius: 6px;
  opacity: 0;
  transition: all 0.2s ease;
}

.session-item:hover .more-btn {
  opacity: 1;
}

.more-btn:hover {
  background: #f3f4f6;
  color: #374151;
}

.empty-sessions {
  text-align: center;
  padding: 20px;
}

.empty-icon {
  font-size: 32px;
  margin-bottom: 8px;
}

.empty-text {
  font-size: 13px;
  color: #9ca3af;
}

.sidebar-bottom {
  margin-top: auto;
  padding-top: 24px;
  border-top: 1px solid #e5e7eb;
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

.dropdown-menu {
  position: fixed;
  background: white;
  border-radius: 12px;
  box-shadow: 0 10px 40px rgba(0, 0, 0, 0.15);
  padding: 8px 0;
  min-width: 140px;
  z-index: 9999;
  border: 1px solid #e5e7eb;
}

.dropdown-item {
  padding: 10px 16px;
  font-size: 14px;
  color: #374151;
  cursor: pointer;
  transition: background 0.15s ease;
  display: flex;
  align-items: center;
  gap: 8px;
}

.dropdown-item:hover {
  background: #f3f4f6;
}

.dropdown-item.danger {
  color: #dc2626;
}

.dropdown-item.danger:hover {
  background: #fee2e2;
}

.dropdown-divider {
  height: 1px;
  background: #e5e7eb;
  margin: 8px 0;
}

.rename-input {
  position: fixed;
  font-size: 14px;
  font-weight: 600;
  color: #374151;
  border: 2px solid #16a34a;
  border-radius: 6px;
  padding: 6px 10px;
  outline: none;
  z-index: 10000;
  background: white;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
}
</style>
