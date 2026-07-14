<template>
  <div class="home-page">
    <header class="navbar">
      <div class="logo">
        🌿 <span>AgriAgent</span>
      </div>

      <div class="nav-actions">
        <div class="nav-links">
          <button @click="go('/ai-chat')">AI Agent</button>
          <button @click="go('/data-analysis')">Analytics</button>
          <button @click="go('/history')">History</button>
        </div>

        <div class="user-menu" @mouseenter="showUserMenu = true" @mouseleave="showUserMenu = false">
          <button class="user-trigger" @click="toggleUserMenu">
            <span class="avatar">{{ userInitial }}</span>
            <span class="user-meta">
              <strong>{{ userStore.username || 'User' }}</strong>
              <small>{{ roleLabel }}</small>
            </span>
          </button>

          <div v-if="showUserMenu" class="user-dropdown">
            <div class="dropdown-header">
              <div class="avatar large">{{ userInitial }}</div>
              <div>
                <div class="dropdown-name">{{ userStore.username || 'User' }}</div>
                <div class="dropdown-role">{{ roleLabel }}</div>
              </div>
            </div>

            <div class="dropdown-body">
              <div class="info-row">
                <span>邮箱</span>
                <strong>{{ userStore.user?.email || '—' }}</strong>
              </div>
              <div class="info-row">
                <span>角色</span>
                <strong>{{ roleLabel }}</strong>
              </div>
            </div>

            <button class="logout-btn" @click="handleLogout">Logout</button>
          </div>
        </div>
      </div>
    </header>

    <main class="hero">
      <div class="badge">YOLOv11 + LLM</div>

      <h1>
        Agri<span>Agent</span>
      </h1>

      <p class="subtitle">
        AI-Powered Fruit and Vegetable Disease Diagnosis Assistant
      </p>

      <div class="card-grid">
        <div class="entry-card" @click="go('/ai-chat')">
          <div class="icon">🤖</div>
          <h2>AI Agent</h2>
          <p>
            Upload plant images for instant disease diagnosis and treatment recommendations.
          </p>
        </div>

        <div class="entry-card" @click="go('/data-analysis')">
          <div class="icon">📊</div>
          <h2>Data Analytics</h2>
          <p>
            Explore disease patterns, detection trends, and model performance metrics.
          </p>
        </div>

      </div>

      <button class="history-btn" @click="go('/history')">
        View Detection History →
      </button>

      <div class="features">
        <span>⚡ Real-time Detection</span>
        <span>🛡️ 94.2% Accuracy</span>
        <span>📈 35+ Disease Classes</span>
        <span>🌱 Fruits & Vegetables</span>
      </div>
    </main>

    <footer>
      AgriAgent © 2026 — Smart Farming with Conversational AI
    </footer>
  </div>
</template>

<script setup>
import { useUserStore } from '@/stores/user'
import { ElMessage } from 'element-plus'
import { computed, ref } from 'vue'
import { useRouter } from 'vue-router'

const router = useRouter()
const userStore = useUserStore()

const roleLabel = computed(() => (userStore.isSuperuser ? 'Administrator' : 'User'))
const userInitial = computed(() => (userStore.username || 'U').charAt(0).toUpperCase())
const showUserMenu = ref(false)

const go = (path) => {
  router.push(path)
}

const toggleUserMenu = () => {
  showUserMenu.value = !showUserMenu.value
}

const handleLogout = () => {
  userStore.logout()
  showUserMenu.value = false
  ElMessage.success('已退出登录')
  router.push('/login')
}
</script>

<style scoped>
.home-page {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
  background: #fafafa;
}

.navbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 20px 40px;
  border-bottom: 1px solid #e5e7eb;
}

.logo {
  font-size: 20px;
  font-weight: 700;
}

.nav-actions {
  display: flex;
  align-items: center;
  gap: 16px;
}

.nav-links {
  display: flex;
  gap: 12px;
}

.nav-links button,
.user-trigger,
.logout-btn {
  border: none;
  background: transparent;
  cursor: pointer;
}

.user-menu {
  position: relative;
}

.user-trigger {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 10px;
  border-radius: 999px;
  background: #f3f4f6;
}

.avatar {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  background: linear-gradient(135deg, #16a34a, #22c55e);
  color: white;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-weight: 700;
}

.avatar.large {
  width: 42px;
  height: 42px;
  font-size: 18px;
}

.user-meta {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  line-height: 1.2;
}

.user-meta small {
  color: #6b7280;
}

.user-dropdown {
  position: absolute;
  top: calc(100% + 8px);
  right: 0;
  width: 260px;
  background: white;
  border: 1px solid #e5e7eb;
  border-radius: 16px;
  box-shadow: 0 12px 30px rgba(0,0,0,0.08);
  padding: 14px;
  z-index: 20;
}

.dropdown-header {
  display: flex;
  align-items: center;
  gap: 10px;
  padding-bottom: 10px;
  border-bottom: 1px solid #f3f4f6;
}

.dropdown-name {
  font-weight: 700;
}

.dropdown-role {
  color: #6b7280;
  font-size: 13px;
}

.dropdown-body {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 10px 0;
}

.info-row {
  display: flex;
  justify-content: space-between;
  gap: 10px;
  font-size: 13px;
}

.info-row span {
  color: #6b7280;
}

.logout-btn {
  width: 100%;
  padding: 8px 10px;
  border-radius: 10px;
  background: #fef2f2;
  color: #dc2626;
  font-weight: 600;
}

.hero {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  text-align: center;
  padding: 40px 20px;
}

.badge {
  background: #ecfdf5;
  color: #15803d;
  border-radius: 999px;
  padding: 8px 16px;
  font-size: 12px;
  font-weight: 600;
}

h1 {
  font-size: 72px;
  margin: 24px 0 12px;
}

h1 span {
  color: #16a34a;
}

.subtitle {
  color: #6b7280;
  font-size: 20px;
  margin-bottom: 40px;
}

.card-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
  gap: 20px;
  width: 100%;
  max-width: 900px;
}

.entry-card {
  background: white;
  border: 1px solid #e5e7eb;
  border-radius: 20px;
  padding: 24px;
  text-align: left;
  cursor: pointer;
  transition: 0.2s;
}

.entry-card:hover {
  transform: translateY(-4px);
  box-shadow: 0 10px 25px rgba(0,0,0,0.08);
}

.icon {
  font-size: 28px;
  margin-bottom: 12px;
}

.history-btn {
  margin-top: 30px;
  border: none;
  background: transparent;
  cursor: pointer;
  color: #6b7280;
}

.features {
  display: flex;
  flex-wrap: wrap;
  justify-content: center;
  gap: 12px;
  margin-top: 40px;
}

.features span {
  background: #f3f4f6;
  padding: 8px 14px;
  border-radius: 999px;
  font-size: 13px;
}

footer {
  border-top: 1px solid #e5e7eb;
  text-align: center;
  padding: 20px;
  color: #6b7280;
  font-size: 13px;
}
</style>
