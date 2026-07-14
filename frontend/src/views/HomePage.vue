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
          <button @click="go('/training')">Training</button>
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

    <main class="home-content">
      <section class="hero">
        <div class="badge">YOLOv11 + Conversational AI</div>

        <h1>Agri<span>Agent</span></h1>
        <h2>今天想分析什么农业问题？</h2>

        <p class="subtitle">
          AgriAgent 将自动完成病害诊断、知识检索与数据分析。
        </p>

        <form class="prompt-box" @submit.prevent="startConversation">
          <div class="prompt-icon">🌿</div>
          <textarea
            v-model="prompt"
            rows="1"
            aria-label="Ask AgriAgent"
            placeholder="描述作物问题、上传图片，或直接告诉我您想分析什么……"
            @keydown.enter.exact.prevent="startConversation"
          />
          <button class="prompt-submit" type="submit" :disabled="!prompt.trim()" aria-label="Send to AgriAgent">
            ➤
          </button>
        </form>

        <p class="prompt-hint">Press Enter to start a conversation · Add images after entering AI Agent</p>

        <div class="suggestion-list" aria-label="Suggested questions">
          <button
            v-for="suggestion in suggestions"
            :key="suggestion"
            type="button"
            @click="startConversation(suggestion)"
          >
            {{ suggestion }}
          </button>
        </div>
      </section>

      <section class="workspace-section" aria-labelledby="workspace-title">
        <div class="section-heading">
          <div>
            <span class="section-kicker">Workspace</span>
            <h2 id="workspace-title">Manage and review your AgriAgent system</h2>
          </div>
          <button class="history-btn" @click="go('/history')">View Detection History →</button>
        </div>

        <div class="card-grid">
          <div class="entry-card" @click="go('/ai-chat')">
            <div class="icon">🤖</div>
            <h3>AI Agent</h3>
            <p>Continue a conversation, upload plant images, or run a quick diagnosis.</p>
          </div>

          <div class="entry-card" @click="go('/data-analysis')">
            <div class="icon">📊</div>
            <h3>Data Analytics</h3>
            <p>Explore disease patterns, detection trends, and model performance metrics.</p>
          </div>

          <div class="entry-card" @click="go('/training')">
            <div class="icon">🧠</div>
            <h3>Training Records</h3>
            <p>Review imported models, training records, evaluation metrics, and test predictions.</p>
          </div>
        </div>
      </section>

      <div class="features">
        <span>⚡ Real-time Detection</span>
        <span>🛡️ Reliable Model Results</span>
        <span>💬 Natural Language Control</span>
        <span>🌱 Fruits & Vegetables</span>
      </div>
    </main>

    <footer>
      AgriAgent © 2026 — Smart Farming with Conversational AI
    </footer>
  </div>
</template>

<script setup>
import { useAgentStore } from '@/stores/agent'
import { useUserStore } from '@/stores/user'
import { ElMessage } from 'element-plus'
import { computed, ref } from 'vue'
import { useRouter } from 'vue-router'

const router = useRouter()
const userStore = useUserStore()
const agentStore = useAgentStore()

const roleLabel = computed(() => (userStore.isSuperuser ? 'Administrator' : 'User'))
const userInitial = computed(() => (userStore.username || 'U').charAt(0).toUpperCase())
const showUserMenu = ref(false)
const prompt = ref('')

const suggestions = [
  '帮我分析一张叶片图片',
  '我有哪些可用的检测模型？',
  '查看最近的检测结果',
]

const go = (path) => {
  router.push(path)
}

const startConversation = (suggestion = '') => {
  const content = (typeof suggestion === 'string' && suggestion ? suggestion : prompt.value).trim()
  if (!content) return

  agentStore.queueHomePrompt(content)
  prompt.value = ''
  router.push('/ai-chat')
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

/* Chat-first home page */
.home-content {
  flex: 1;
  width: 100%;
  max-width: 1120px;
  margin: 0 auto;
  padding: 0 32px 44px;
}

.hero {
  min-height: 540px;
  padding: 72px 20px 54px;
}

.hero h1 {
  max-width: 850px;
  color: #111827;
  font-size: clamp(42px, 6vw, 68px);
  line-height: 1.08;
  letter-spacing: -0.04em;
  margin: 24px 0 18px;
}

.hero .subtitle {
  max-width: 720px;
  font-size: 18px;
  line-height: 1.7;
  margin: 0 0 30px;
}

.prompt-box {
  width: min(780px, 100%);
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 12px 14px 12px 18px;
  border: 1px solid #d1d5db;
  border-radius: 22px;
  background: white;
  box-shadow: 0 18px 45px rgba(22, 101, 52, 0.1);
  transition: border-color 0.2s ease, box-shadow 0.2s ease;
}

.prompt-box:focus-within {
  border-color: #22c55e;
  box-shadow: 0 20px 50px rgba(22, 163, 74, 0.16);
}

.prompt-icon {
  flex-shrink: 0;
  font-size: 24px;
}

.prompt-box textarea {
  flex: 1;
  min-width: 0;
  min-height: 28px;
  max-height: 120px;
  padding: 8px 0;
  border: none;
  outline: none;
  resize: none;
  background: transparent;
  color: #111827;
  font: inherit;
  line-height: 1.5;
}

.prompt-box textarea::placeholder {
  color: #9ca3af;
}

.prompt-submit {
  width: 46px;
  height: 46px;
  flex-shrink: 0;
  border: none;
  border-radius: 50%;
  background: #16a34a;
  color: white;
  cursor: pointer;
  font-size: 18px;
  transition: transform 0.2s ease, opacity 0.2s ease;
}

.prompt-submit:hover:not(:disabled) {
  transform: translateY(-1px);
}

.prompt-submit:disabled {
  opacity: 0.38;
  cursor: not-allowed;
}

.prompt-hint {
  margin: 12px 0 18px;
  color: #9ca3af;
  font-size: 12px;
}

.suggestion-list {
  display: flex;
  flex-wrap: wrap;
  justify-content: center;
  gap: 10px;
}

.suggestion-list button {
  padding: 9px 14px;
  border: 1px solid #e5e7eb;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.88);
  color: #4b5563;
  cursor: pointer;
  transition: all 0.2s ease;
}

.suggestion-list button:hover {
  border-color: #86efac;
  color: #15803d;
  background: #f0fdf4;
}

.workspace-section {
  padding: 34px;
  border: 1px solid #e5e7eb;
  border-radius: 28px;
  background: rgba(255, 255, 255, 0.82);
}

.section-heading {
  display: flex;
  justify-content: space-between;
  align-items: flex-end;
  gap: 24px;
  margin-bottom: 24px;
  text-align: left;
}

.section-kicker {
  color: #16a34a;
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.12em;
  text-transform: uppercase;
}

.section-heading h2 {
  margin: 7px 0 0;
  color: #111827;
  font-size: 25px;
}

.workspace-section .card-grid {
  max-width: none;
}

.entry-card h3 {
  margin: 0 0 8px;
  color: #111827;
  font-size: 18px;
}

.entry-card p {
  margin: 0;
  color: #6b7280;
  line-height: 1.6;
}

.section-heading .history-btn {
  margin-top: 0;
  color: #15803d;
  font-weight: 600;
  white-space: nowrap;
}

@media (max-width: 760px) {
  .navbar {
    padding: 14px 18px;
  }

  .nav-links,
  .user-meta {
    display: none;
  }

  .home-content {
    padding: 0 16px 32px;
  }

  .hero {
    min-height: 500px;
    padding: 54px 0 40px;
  }

  .hero h1 {
    font-size: 42px;
  }

  .hero .subtitle {
    font-size: 16px;
  }

  .prompt-box {
    border-radius: 18px;
  }

  .prompt-icon {
    display: none;
  }

  .prompt-hint {
    line-height: 1.5;
  }

  .workspace-section {
    padding: 22px;
  }

  .section-heading {
    align-items: flex-start;
    flex-direction: column;
  }

  .card-grid {
    grid-template-columns: 1fr;
  }
}
</style>
