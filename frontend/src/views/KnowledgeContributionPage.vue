<template>
  <div class="knowledge-page">
    <header class="knowledge-header">
      <div class="header-left">
        <router-link to="/home" class="icon-button" :aria-label="tr('knowledge.backHome')">
          <el-icon><ArrowLeft /></el-icon>
        </router-link>
        <div class="brand-mark"><HeaderSeedlingIcon /></div>
        <div>
          <h1>{{ tr('nav.knowledge') }}</h1>
          <p>{{ tr('knowledge.subtitle') }}</p>
        </div>
      </div>

      <nav class="header-nav">
        <LanguageSwitcher />
        <router-link to="/ai-chat"><el-icon><ChatDotRound /></el-icon>{{ tr('knowledge.chat') }}</router-link>
        <router-link to="/history"><el-icon><Clock /></el-icon>{{ tr('nav.history') }}</router-link>
      </nav>
    </header>

    <main class="knowledge-container">
      <section class="hero-panel">
        <div class="hero-copy">
          <span class="eyebrow">📖 {{ tr('knowledge.badge') }}</span>
          <h1>{{ tr('knowledge.title') }}</h1>
          <p>{{ tr('knowledge.subtitle') }}</p>
        </div>
        <div class="hero-visual" aria-hidden="true">
          <span class="leaf leaf-one">🌿</span>
          <span class="leaf leaf-two">🌱</span>
          <div class="book">📖</div>
        </div>
      </section>

      <section class="contribution-grid">
        <form class="surface-card upload-card" @submit.prevent="submitDocument">
          <div class="section-heading">
            <div>
              <span class="section-kicker">SUBMIT</span>
              <h2>{{ tr('knowledge.formTitle') }}</h2>
              <p>{{ tr('knowledge.formDesc') }}</p>
            </div>
          </div>

          <label class="form-field">
            <span>{{ tr('knowledge.documentTitle') }}</span>
            <input
              v-model.trim="documentTitle"
              type="text"
              maxlength="200"
              :placeholder="tr('knowledge.titlePlaceholder')"
            />
          </label>

          <div class="form-field">
            <span>{{ tr('knowledge.file') }}</span>
            <input
              ref="fileInputRef"
              class="file-input"
              type="file"
              accept=".md,.txt,text/markdown,text/plain"
              @change="handleFileInput"
            />

            <button
              v-if="!selectedFile"
              type="button"
              class="drop-zone"
              :class="{ dragging: isDragging }"
              @click="openFilePicker"
              @dragenter.prevent="isDragging = true"
              @dragover.prevent="isDragging = true"
              @dragleave.prevent="isDragging = false"
              @drop.prevent="handleDrop"
            >
              <span class="upload-icon">↑</span>
              <strong>{{ tr('knowledge.dropTitle') }}</strong>
              <small>{{ tr('knowledge.dropHint') }}</small>
              <span class="format-list"><b>MD</b><b>TXT</b></span>
            </button>

            <div v-else class="selected-file">
              <div class="file-type">{{ selectedExtension }}</div>
              <div class="file-copy">
                <strong>{{ selectedFile.name }}</strong>
                <span>{{ formatFileSize(selectedFile.size) }}</span>
              </div>
              <div class="file-actions">
                <button type="button" @click="openFilePicker">{{ tr('knowledge.replace') }}</button>
                <button type="button" class="danger" :aria-label="tr('knowledge.remove')" @click="clearFile">×</button>
              </div>
            </div>
          </div>

          <button class="submit-button" type="submit" :disabled="!selectedFile || submitting">
            <span v-if="submitting" class="button-spinner" />
            {{ submitting ? tr('knowledge.submitting') : tr('knowledge.submit') }}
          </button>
        </form>

        <section class="surface-card submissions-card">
          <div class="submissions-header">
            <div>
              <span class="section-kicker">STATUS</span>
              <h2>{{ tr('knowledge.myTitle') }}</h2>
              <p>{{ tr('knowledge.myDesc') }}</p>
            </div>
            <div class="submissions-actions">
              <span class="total-label">{{ tr('knowledge.total', { count: pagination.total }) }}</span>
              <button type="button" class="refresh-button" :disabled="loading" @click="fetchSubmissions">
                <span :class="{ spinning: loading }">↻</span> {{ tr('knowledge.refresh') }}
              </button>
            </div>
          </div>

          <div v-if="loading && submissions.length === 0" class="loading-state">
            <span class="large-spinner" />
          </div>

          <div v-else-if="submissions.length === 0" class="empty-state">
            <div>📄</div>
            <h3>{{ tr('knowledge.empty') }}</h3>
            <p>{{ tr('knowledge.emptyDesc') }}</p>
          </div>

          <div v-else class="submission-list">
            <article v-for="item in submissions" :key="item.id" class="submission-item">
              <div class="document-mark">📄</div>
              <div class="submission-main">
                <div class="submission-title-row">
                  <h3>{{ item.title }}</h3>
                  <span class="status-tag" :class="statusClass(item.status)">
                    <i />{{ statusLabel(item.status) }}
                  </span>
                </div>
                <p class="file-name">{{ item.filename || fileName(item.file_path) }}</p>
                <div class="submission-meta">
                  <span>{{ tr('knowledge.createdAt') }} · {{ formatDate(item.created_at) }}</span>
                  <span v-if="item.reviewed_at">{{ formatDate(item.reviewed_at) }}</span>
                </div>
                <div v-if="item.review_comment" class="review-comment">
                  <strong>{{ tr('knowledge.reviewComment') }}</strong>
                  <p>{{ item.review_comment }}</p>
                </div>
              </div>
            </article>
          </div>

          <div v-if="pagination.totalPages > 1" class="pagination-row">
            <el-pagination
              v-model:current-page="pagination.page"
              background
              layout="prev, pager, next"
              :page-size="pagination.pageSize"
              :total="pagination.total"
              @current-change="fetchSubmissions"
            />
          </div>
        </section>
      </section>
    </main>
  </div>
</template>

<script setup>
import { getMyKnowledgeSubmissionsApi, submitKnowledgeDocumentApi } from '@/api/knowledge'
import LanguageSwitcher from '@/components/LanguageSwitcher.vue'
import HeaderSeedlingIcon from '@/components/HeaderSeedlingIcon.vue'
import { useLocaleStore } from '@/stores/locale'
import { t } from '@/utils/i18n'
import { ElMessage } from 'element-plus'
import { ArrowLeft, ChatDotRound, Clock } from '@element-plus/icons-vue'
import { computed, onMounted, reactive, ref } from 'vue'

const localeStore = useLocaleStore()
const tr = (key, params) => t(key, localeStore.locale, params)

const fileInputRef = ref(null)
const selectedFile = ref(null)
const documentTitle = ref('')
const isDragging = ref(false)
const submitting = ref(false)
const loading = ref(false)
const submissions = ref([])
const pagination = reactive({ page: 1, pageSize: 8, total: 0, totalPages: 0 })

const selectedExtension = computed(() => {
  const extension = selectedFile.value?.name.split('.').pop()
  return extension ? extension.toUpperCase() : 'FILE'
})

const isSupportedFile = (file) => /\.(md|txt)$/i.test(file?.name || '')

const setSelectedFile = (file) => {
  if (!isSupportedFile(file)) {
    ElMessage.warning(tr('knowledge.invalidFile'))
    return
  }
  selectedFile.value = file
}

const openFilePicker = () => fileInputRef.value?.click()

const handleFileInput = (event) => {
  const file = event.target.files?.[0]
  event.target.value = ''
  if (file) setSelectedFile(file)
}

const handleDrop = (event) => {
  isDragging.value = false
  const file = event.dataTransfer?.files?.[0]
  if (file) setSelectedFile(file)
}

const clearFile = () => {
  selectedFile.value = null
}

const submitDocument = async () => {
  if (!selectedFile.value || submitting.value) return
  submitting.value = true

  try {
    const result = await submitKnowledgeDocumentApi(selectedFile.value, documentTitle.value)
    const submittedRecord = result?.document_id
      ? {
          id: result.document_id,
          title: result.title || documentTitle.value || selectedFile.value.name.replace(/\.(md|txt)$/i, ''),
          filename: result.filename || selectedFile.value.name,
          file_path: result.file_path || '',
          status: result.status || 'pending',
          created_at: new Date().toISOString(),
        }
      : null
    ElMessage.success(tr('knowledge.submitSuccess'))
    selectedFile.value = null
    documentTitle.value = ''
    pagination.page = 1
    await fetchSubmissions()
    if (submittedRecord && !submissions.value.some((item) => item.id === submittedRecord.id)) {
      submissions.value = [submittedRecord, ...submissions.value]
      pagination.total += 1
    }
  } finally {
    submitting.value = false
  }
}

const fetchSubmissions = async () => {
  loading.value = true
  try {
    const result = await getMyKnowledgeSubmissionsApi({
      page: pagination.page,
      page_size: pagination.pageSize,
    })
    submissions.value = Array.isArray(result?.items) ? result.items : []
    pagination.total = Number(result?.total || 0)
    pagination.totalPages = Number(result?.total_pages || 0)
  } finally {
    loading.value = false
  }
}

const statusLabel = (status) => tr(`knowledge.${status || 'pending'}`)

const statusClass = (status) => ({
  pending: 'status-pending',
  processing: 'status-processing',
  approved: 'status-approved',
  rejected: 'status-rejected',
  failed: 'status-failed',
}[status] || 'status-pending')

const fileName = (path = '') => path.split(/[\\/]/).pop() || '—'

const formatFileSize = (bytes = 0) => {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`
}

const formatDate = (value) => {
  if (!value) return '—'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return '—'
  return date.toLocaleString(localeStore.locale === 'en' ? 'en-US' : 'zh-CN', {
    year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit',
  })
}

onMounted(fetchSubmissions)
</script>

<style scoped>
.knowledge-page {
  min-height: 100vh;
  background: #f7faf8;
  color: #17211b;
}

.knowledge-header {
  position: sticky;
  top: 0;
  z-index: 20;
  display: flex;
  align-items: center;
  justify-content: space-between;
  min-height: 72px;
  padding: 12px 28px;
  box-sizing: border-box;
  gap: 20px;
  border-bottom: 1px solid rgba(222, 229, 224, 0.9);
  background: rgba(250, 252, 250, 0.9);
  backdrop-filter: blur(16px);
}

.header-left,
.header-nav {
  display: flex;
  align-items: center;
}

.header-left { gap: 10px; min-width: 0; }
.header-nav { gap: 7px; }
.icon-button { width: 34px; height: 34px; display: grid; place-items: center; border-radius: 10px; color: #68766d; text-decoration: none; }
.icon-button:hover { background: #edf2ee; color: #25372c; }
.brand-mark { width: 34px; height: 34px; margin-left: 2px; display: grid; place-items: center; flex: 0 0 auto; border-radius: 10px; background: #1c8b51; color: #fff; font-size: 18px; }
.header-left h1 { margin: 0; color: #17251c; font-size: 18px; font-weight: 800; }
.header-left p { margin: 2px 0 0; color: #879189; font-size: 12px; }
.header-nav > a { display: inline-flex; align-items: center; gap: 6px; padding: 8px 10px; border-radius: 9px; color: #637068; text-decoration: none; font-size: 13px; }
.header-nav > a:hover { background: #edf3ef; color: #18834a; }

.knowledge-container {
  width: min(1120px, calc(100% - 40px));
  margin: 0 auto;
  padding: 36px 0 64px;
}

.hero-panel {
  position: relative;
  display: flex;
  min-height: 220px;
  align-items: center;
  justify-content: space-between;
  overflow: hidden;
  padding: 38px 46px;
  border: 1px solid #d9e8de;
  border-radius: 28px;
  background: linear-gradient(130deg, #effaf2 0%, #f9fcf9 58%, #e7f7eb 100%);
}

.hero-copy {
  position: relative;
  z-index: 2;
  max-width: 690px;
}

.eyebrow,
.section-kicker {
  color: #16803e;
  font-size: 12px;
  font-weight: 800;
  letter-spacing: 0.1em;
}

.hero-copy h1 {
  max-width: 680px;
  margin: 15px 0 17px;
  color: #17251c;
  font-size: clamp(32px, 4vw, 46px);
  line-height: 1.08;
  letter-spacing: -0.04em;
}

.hero-copy p {
  max-width: 650px;
  margin: 0;
  color: #58675e;
  font-size: 15px;
  line-height: 1.65;
}

.hero-visual {
  position: relative;
  width: 230px;
  height: 190px;
  flex: 0 0 230px;
}

.book {
  position: absolute;
  right: 34px;
  bottom: 18px;
  display: grid;
  width: 132px;
  height: 132px;
  place-items: center;
  border: 1px solid rgba(255, 255, 255, 0.8);
  border-radius: 36px;
  background: rgba(255, 255, 255, 0.72);
  box-shadow: 0 22px 45px rgba(21, 128, 61, 0.15);
  font-size: 64px;
  transform: rotate(-5deg);
}

.leaf { position: absolute; font-size: 38px; }
.leaf-one { top: 8px; right: 10px; transform: rotate(20deg); }
.leaf-two { bottom: 0; left: 18px; transform: rotate(-18deg); }

.contribution-grid {
  display: grid;
  grid-template-columns: minmax(0, 1fr);
  gap: 24px;
  margin-top: 24px;
}

.surface-card {
  border: 1px solid #e0e7e2;
  border-radius: 22px;
  background: #fff;
  box-shadow: 0 12px 32px rgba(30, 58, 40, 0.055);
}

.upload-card,
.submissions-card { padding: 30px; }

.section-heading h2,
.submissions-header h2 {
  margin: 7px 0 6px;
  font-size: 24px;
  letter-spacing: -0.02em;
}

.section-heading p,
.submissions-header p {
  margin: 0;
  color: #718078;
  line-height: 1.65;
}

.form-field {
  display: flex;
  flex-direction: column;
  gap: 9px;
  margin-top: 24px;
  color: #34443a;
  font-size: 14px;
  font-weight: 700;
}

.form-field > input {
  height: 46px;
  padding: 0 14px;
  border: 1px solid #d9e2dc;
  border-radius: 12px;
  outline: none;
  color: #243129;
  font: inherit;
  font-weight: 500;
}

.form-field > input:focus {
  border-color: #22a455;
  box-shadow: 0 0 0 3px rgba(34, 164, 85, 0.1);
}

.file-input { display: none; }

.drop-zone {
  display: flex;
  min-height: 190px;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 8px;
  border: 1.5px dashed #a9c3b0;
  border-radius: 18px;
  background: #f8fcf9;
  color: #2f4135;
  cursor: pointer;
  transition: 0.2s ease;
}

.drop-zone:hover,
.drop-zone.dragging {
  border-color: #16a34a;
  background: #effaf2;
  transform: translateY(-1px);
}

.drop-zone small { color: #7a8980; }
.upload-icon {
  display: grid;
  width: 48px;
  height: 48px;
  place-items: center;
  border-radius: 15px;
  background: #dcfce7;
  color: #15803d;
  font-size: 27px;
}

.format-list { display: flex; gap: 6px; margin-top: 6px; }
.format-list b {
  padding: 4px 8px;
  border-radius: 6px;
  background: #e8f3eb;
  color: #357148;
  font-size: 10px;
}

.selected-file {
  display: flex;
  align-items: center;
  gap: 14px;
  min-height: 84px;
  padding: 15px;
  border: 1px solid #bfe2c9;
  border-radius: 16px;
  background: #f2fbf4;
}

.file-type {
  display: grid;
  width: 48px;
  height: 52px;
  flex: 0 0 48px;
  place-items: center;
  border-radius: 12px;
  background: #16803e;
  color: white;
  font-size: 11px;
  font-weight: 800;
}

.file-copy { display: flex; min-width: 0; flex: 1; flex-direction: column; gap: 5px; }
.file-copy strong { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.file-copy span { color: #748178; font-size: 12px; font-weight: 500; }
.file-actions { display: flex; align-items: center; gap: 7px; }
.file-actions button {
  padding: 7px 9px;
  border: 0;
  border-radius: 8px;
  background: #fff;
  color: #23703a;
  cursor: pointer;
}
.file-actions button.danger { color: #b91c1c; font-size: 18px; }

.submit-button {
  display: flex;
  width: 100%;
  height: 48px;
  align-items: center;
  justify-content: center;
  gap: 9px;
  margin-top: 25px;
  border: 0;
  border-radius: 13px;
  background: #16803e;
  color: white;
  cursor: pointer;
  font-size: 15px;
  font-weight: 750;
}

.submit-button:hover:not(:disabled) { background: #116d34; }
.submit-button:disabled { background: #bdc8c0; cursor: not-allowed; }

.button-spinner,
.large-spinner {
  display: inline-block;
  width: 16px;
  height: 16px;
  border: 2px solid rgba(255,255,255,.45);
  border-top-color: currentColor;
  border-radius: 50%;
  animation: spin .8s linear infinite;
}

.submissions-card {
  display: flex;
  min-width: 0;
  flex-direction: column;
}
.submissions-header,
.submissions-actions {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
}
.submissions-actions { justify-content: flex-end; }
.total-label { color: #748178; font-size: 13px; }
.refresh-button {
  padding: 9px 12px;
  border: 1px solid #dce4de;
  border-radius: 10px;
  background: #fff;
  color: #385241;
  cursor: pointer;
}
.refresh-button:disabled { opacity: .6; }

.submission-list {
  margin-top: 24px;
  border-top: 1px solid #edf1ee;
}
.submission-item {
  display: flex;
  gap: 15px;
  padding: 20px 2px;
  border-bottom: 1px solid #edf1ee;
}
.document-mark {
  display: grid;
  width: 46px;
  height: 46px;
  flex: 0 0 46px;
  place-items: center;
  border-radius: 13px;
  background: #edf8f0;
  font-size: 22px;
}
.submission-main { min-width: 0; flex: 1; }
.submission-title-row { display: flex; align-items: flex-start; justify-content: space-between; gap: 14px; }
.submission-title-row h3 { margin: 2px 0 5px; font-size: 16px; overflow-wrap: anywhere; }
.file-name { margin: 0; color: #829087; font-size: 12px; overflow-wrap: anywhere; }
.submission-meta { display: flex; flex-wrap: wrap; gap: 16px; margin-top: 10px; color: #78857d; font-size: 12px; }
.status-tag {
  display: inline-flex;
  flex: 0 0 auto;
  align-items: center;
  gap: 6px;
  padding: 6px 9px;
  border-radius: 999px;
  font-size: 11px;
  font-weight: 750;
}
.status-tag i { width: 6px; height: 6px; border-radius: 50%; background: currentColor; }
.status-pending { background: #fff7df; color: #a16207; }
.status-processing { background: #eaf3ff; color: #2563eb; }
.status-approved { background: #e8f8ed; color: #15803d; }
.status-rejected,
.status-failed { background: #fef0f0; color: #c43131; }
.review-comment { margin-top: 12px; padding: 10px 12px; border-radius: 10px; background: #fff8f0; color: #7d5834; font-size: 12px; }
.review-comment strong { display: block; margin-bottom: 4px; }
.review-comment p { margin: 0; line-height: 1.55; }

.empty-state,
.loading-state { display: grid; min-height: 230px; place-items: center; align-content: center; text-align: center; }
.empty-state > div { font-size: 36px; }
.empty-state h3 { margin: 10px 0 5px; }
.empty-state p { max-width: 420px; margin: 0; color: #7b8980; }
.large-spinner { width: 28px; height: 28px; border-color: #cde4d4; border-top-color: #16803e; }
.pagination-row { display: flex; justify-content: center; margin-top: 22px; }
.spinning { display: inline-block; animation: spin .8s linear infinite; }

@keyframes spin { to { transform: rotate(360deg); } }

@media (max-width: 860px) {
  .knowledge-header { align-items: flex-start; padding: 12px 16px; }
  .header-left p { display: none; }
  .header-nav > a { width: 34px; height: 34px; padding: 0; justify-content: center; font-size: 0; }
  .header-nav > a .el-icon { font-size: 15px; }
  .hero-panel { padding: 38px 32px; }
  .hero-visual { display: none; }
  .contribution-grid { grid-template-columns: 1fr; }
}

@media (max-width: 600px) {
  .knowledge-container { width: min(100% - 24px, 1120px); padding-top: 18px; }
  .knowledge-header { gap: 8px; }
  .brand-mark { display: none; }
  .header-nav { gap: 2px; }
  .hero-panel { min-height: 0; padding: 30px 22px; border-radius: 21px; }
  .hero-copy h1 { font-size: 32px; }
  .hero-copy p { font-size: 14px; }
  .upload-card,
  .submissions-card { padding: 21px; border-radius: 18px; }
  .submissions-header { align-items: flex-start; flex-direction: column; }
  .submissions-actions { width: 100%; justify-content: space-between; }
  .submission-title-row { flex-direction: column-reverse; gap: 8px; }
  .selected-file { align-items: flex-start; flex-wrap: wrap; }
  .file-actions { width: 100%; justify-content: flex-end; }
}
</style>
