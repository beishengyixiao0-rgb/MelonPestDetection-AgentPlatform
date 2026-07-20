<template>
  <div class="home-page">
    <header class="navbar">
      <div class="logo">
        🌿 <span>AgriAgent</span>
      </div>

      <div class="nav-actions">
        <div class="nav-links">
          <button @click="go('/ai-chat')">{{ tr('nav.chat') }}</button>
          <button @click="go('/data-analysis')">{{ tr('nav.dashboard') }}</button>
          <button @click="go('/history')">{{ tr('nav.history') }}</button>
          <button @click="go('/knowledge')">{{ tr('nav.knowledge') }}</button>
          <button @click="go('/training')">{{ tr('nav.training') }}</button>
        </div>

        <LanguageSwitcher />
        <UserMenu />
      </div>
    </header>

    <main class="home-content">
      <section class="hero">
        <WeatherBadge />

        <h1>Agri<span>Agent</span></h1>
        <h2>{{ tr('home.hero') }}</h2>

        <p class="subtitle">
          {{ tr('home.subtitle') }}
        </p>

        <div class="home-prompt-area">
          <input
            ref="homeFileInputRef"
            type="file"
            :accept="homeFileAccept"
            :multiple="homeFileMultiple"
            class="home-file-input"
            @change="handleHomeFileSelection"
          />

          <div v-if="showAttachmentMenu" class="home-attachment-menu">
            <div class="attachment-menu-title">{{ tr('home.attachmentTitle') }}</div>
            <button type="button" class="attachment-option primary" @click="selectAttachmentMode('agent-image')">
              <span class="option-icon"><Picture /></span>
              <span class="option-copy"><strong>{{ tr('composer.agentImage') }}</strong><small>{{ tr('composer.agentImageDesc') }}</small></span>
            </button>
            <button type="button" class="attachment-option" @click="selectAttachmentMode('image')">
              <span class="option-icon"><Lightning /></span>
              <span class="option-copy"><strong>{{ tr('composer.single') }}</strong><small>{{ tr('composer.singleDesc') }}</small></span>
            </button>
            <button type="button" class="attachment-option" @click="selectAttachmentMode('batch')">
              <span class="option-icon"><Files /></span>
              <span class="option-copy"><strong>{{ tr('composer.batch') }}</strong><small>{{ tr('composer.batchDesc') }}</small></span>
            </button>
            <button type="button" class="attachment-option" @click="selectAttachmentMode('video')">
              <span class="option-icon"><VideoCamera /></span>
              <span class="option-copy"><strong>{{ tr('composer.video') }}</strong><small>{{ tr('composer.videoDesc') }}</small></span>
            </button>
            <button type="button" class="attachment-option" @click="selectAttachmentMode('realtime-camera')">
              <span class="option-icon"><Monitor /></span>
              <span class="option-copy"><strong>{{ tr('composer.realtime') }}</strong><small>{{ tr('composer.realtimeDesc') }}</small></span>
            </button>
            <button type="button" class="attachment-option" @click="selectAttachmentMode('camera')">
              <span class="option-icon"><Camera /></span>
              <span class="option-copy"><strong>{{ tr('composer.camera') }}</strong><small>{{ tr('composer.cameraDesc') }}</small></span>
            </button>
          </div>

        <form class="prompt-box" @submit.prevent="startConversation">
          <button
            type="button"
            class="prompt-add"
            :class="{ active: showAttachmentMenu }"
            :aria-expanded="showAttachmentMenu"
            aria-label="添加附件或选择检测方式"
            @click="showAttachmentMenu = !showAttachmentMenu"
          >
            <Plus />
          </button>
          <textarea
            v-model="prompt"
            rows="1"
            aria-label="Ask AgriAgent"
            :placeholder="tr('home.placeholder')"
            @keydown.enter.exact.prevent="startConversation"
          />
          <button class="prompt-submit" type="submit" :disabled="!prompt.trim()" aria-label="Send to AgriAgent">
            ➤
          </button>
        </form>

        </div>

        <p class="prompt-hint">{{ tr('home.hint') }}</p>

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

          <div class="entry-card" @click="go('/knowledge')">
            <div class="icon">📖</div>
            <h3>{{ tr('home.knowledgeTitle') }}</h3>
            <p>{{ tr('home.knowledgeDesc') }}</p>
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
import WeatherBadge from '@/components/WeatherBadge.vue'
import LanguageSwitcher from '@/components/LanguageSwitcher.vue'
import UserMenu from '@/components/UserMenu.vue'
import { useLocaleStore } from '@/stores/locale'
import { t } from '@/utils/i18n'
import { Camera, Files, Lightning, Monitor, Picture, Plus, VideoCamera } from '@element-plus/icons-vue'
import { computed, nextTick, ref } from 'vue'
import { useRouter } from 'vue-router'

const router = useRouter()
const agentStore = useAgentStore()
const localeStore = useLocaleStore()
const tr = (key, params) => t(key, localeStore.locale, params)

const prompt = ref('')
const showAttachmentMenu = ref(false)
const homeFileInputRef = ref(null)
const homeFileMode = ref('agent-image')
const homeFileAccept = ref('image/*')
const homeFileMultiple = ref(false)

const suggestions = computed(() => [
  tr('home.suggestionAnalyze'),
  tr('home.suggestionModels'),
  tr('home.suggestionRecent'),
])

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

const routeHomeAction = (mode, files = []) => {
  const defaultPrompt = mode === 'agent-image' ? tr('home.analyzeImagePrompt') : ''
  agentStore.queueHomePrompt(prompt.value.trim() || defaultPrompt, { mode, files })
  prompt.value = ''
  showAttachmentMenu.value = false
  router.push('/ai-chat')
}

const selectAttachmentMode = async (mode) => {
  showAttachmentMenu.value = false

  if (mode === 'realtime-camera' || mode === 'camera') {
    routeHomeAction(mode)
    return
  }

  homeFileMode.value = mode
  homeFileMultiple.value = mode === 'batch'
  homeFileAccept.value = mode === 'video'
    ? '.mp4,.avi,.mov,.mkv,.wmv,.flv,video/*'
    : mode === 'batch'
      ? 'image/*,.zip'
      : 'image/*'

  await nextTick()
  homeFileInputRef.value?.click()
}

const handleHomeFileSelection = (event) => {
  const files = Array.from(event.target.files || [])
  event.target.value = ''
  if (!files.length) return
  routeHomeAction(homeFileMode.value, files)
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

.nav-links button {
  border: none;
  background: transparent;
  cursor: pointer;
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

.home-prompt-area {
  position: relative;
  width: min(780px, 100%);
}

.home-file-input {
  display: none;
}

.prompt-box {
  width: 100%;
}

.prompt-add {
  display: grid;
  width: 36px;
  height: 36px;
  flex-shrink: 0;
  place-items: center;
  border: 0;
  border-radius: 50%;
  background: #f3f4f6;
  color: #374151;
  cursor: pointer;
  font-size: 20px;
  font-weight: 300;
  line-height: 1;
  transition: background 0.2s ease, transform 0.2s ease;
}

.prompt-add :deep(svg) {
  width: 18px;
  height: 18px;
}

.prompt-add:hover,
.prompt-add.active {
  background: #dcfce7;
  color: #15803d;
  transform: rotate(90deg);
}

.home-attachment-menu {
  position: absolute;
  right: auto;
  bottom: calc(100% + 12px);
  left: 0;
  z-index: 30;
  display: flex;
  flex-direction: column;
  gap: 3px;
  width: min(380px, calc(100vw - 32px));
  max-height: min(330px, 52vh);
  padding: 10px;
  overflow-y: auto;
  border: 1px solid #d9dedb;
  border-radius: 24px;
  background: rgba(255, 255, 255, 0.98);
  box-shadow: 0 18px 48px rgba(17, 24, 39, 0.14);
  text-align: left;
  backdrop-filter: blur(18px);
}

.home-attachment-menu::-webkit-scrollbar {
  width: 6px;
}

.home-attachment-menu::-webkit-scrollbar-thumb {
  border-radius: 999px;
  background: #d1d5db;
}

.attachment-menu-title {
  padding: 8px 12px 6px;
  color: #9ca3af;
  font-size: 12px;
  font-weight: 700;
}

.attachment-option {
  display: flex;
  align-items: center;
  gap: 13px;
  width: 100%;
  padding: 11px 13px;
  border: 0;
  border-radius: 15px;
  background: transparent;
  color: #1f2937;
  cursor: pointer;
  text-align: left;
  transition: background 0.18s ease, transform 0.18s ease;
}

.attachment-option.primary {
  background: #f0fdf4;
}

.attachment-option:hover {
  background: #f3f6f4;
  transform: translateX(2px);
}

.option-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 38px;
  height: 38px;
  flex-shrink: 0;
  place-items: center;
  border-radius: 11px;
  background: #f3f4f6;
  color: #374151;
}

.option-icon :deep(svg) {
  width: 19px;
  height: 19px;
}

.option-copy {
  display: flex;
  min-width: 0;
  flex-direction: column;
  gap: 3px;
}

.option-copy strong {
  color: #1f2937;
  font-size: 14px;
}

.option-copy small {
  color: #8b938e;
  font-size: 12px;
  line-height: 1.35;
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

  .nav-links {
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
