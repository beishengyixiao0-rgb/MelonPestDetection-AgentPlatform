<template>
  <div class="history-page">
    <header class="history-header">
      <div class="header-left">
        <router-link to="/" class="icon-button" :aria-label="copy.back">
          <el-icon><ArrowLeft /></el-icon>
        </router-link>
        <div class="brand-mark"><el-icon><Grape /></el-icon></div>
        <div>
          <h1>{{ copy.title }}</h1>
          <p>{{ copy.subtitle }}</p>
        </div>
      </div>

      <nav class="header-nav">
        <LanguageSwitcher />
        <router-link to="/ai-chat"><el-icon><ChatDotRound /></el-icon>{{ copy.aiAgent }}</router-link>
        <router-link to="/data-analysis"><el-icon><DataAnalysis /></el-icon>{{ copy.analytics }}</router-link>
      </nav>
    </header>

    <main class="history-container">
      <HistorySummaryCards :summary="summary" :loading="summaryLoading" :locale="localeStore.locale" />

      <section class="filter-section">
        <div class="filter-primary-row">
          <div class="search-box">
            <el-icon><Search /></el-icon>
            <input v-model.trim="filters.keyword" :placeholder="copy.searchPlaceholder" />
            <button v-if="filters.keyword" type="button" :aria-label="copy.clear" @click="filters.keyword = ''">
              <el-icon><Close /></el-icon>
            </button>
          </div>

          <button class="filter-toggle" :class="{ active: activeFilterCount }" type="button" @click="showFilters = !showFilters">
            <el-icon><Operation /></el-icon>
            {{ copy.filters }}
            <span v-if="activeFilterCount">{{ activeFilterCount }}</span>
          </button>

          <button class="refresh-button" type="button" :aria-label="copy.refresh" @click="refreshAll">
            <el-icon :class="{ spinning: loading }"><Refresh /></el-icon>
          </button>
        </div>

        <div v-if="showFilters" class="filter-panel">
          <label>
            <span>{{ copy.taskType }}</span>
            <el-select v-model="filters.taskType" clearable :placeholder="copy.allTypes">
              <el-option :label="copy.single" value="single" />
              <el-option :label="copy.batch" value="batch" />
              <el-option :label="copy.video" value="video" />
            </el-select>
          </label>
          <label>
            <span>{{ copy.status }}</span>
            <el-select v-model="filters.status" clearable :placeholder="copy.allStatuses">
              <el-option :label="copy.completed" value="completed" />
              <el-option :label="copy.processing" value="processing" />
              <el-option :label="copy.pending" value="pending" />
              <el-option :label="copy.failed" value="failed" />
            </el-select>
          </label>
          <label>
            <span>{{ copy.scene }}</span>
            <el-select v-model="filters.sceneId" clearable :placeholder="copy.allScenes">
              <el-option v-for="scene in scenes" :key="scene.id" :label="scene.display_name || scene.name" :value="scene.id" />
            </el-select>
          </label>
          <label class="date-field">
            <span>{{ copy.dateRange }}</span>
            <el-date-picker
              v-model="filters.dateRange"
              type="daterange"
              :range-separator="copy.to"
              :start-placeholder="copy.startDate"
              :end-placeholder="copy.endDate"
              unlink-panels
            />
          </label>
          <button v-if="activeFilterCount" class="clear-filters" type="button" @click="clearFilters">
            <el-icon><Close /></el-icon>{{ copy.clearFilters }}
          </button>
        </div>
      </section>

      <div class="result-meta">
        <p>
          {{ copy.showing }} <b>{{ visibleTasks.length }}</b>
          {{ copy.of }} {{ pagination.total }} {{ copy.records }}
          <span v-if="filters.keyword">· {{ copy.currentPageSearch }}</span>
        </p>
        <span class="api-note"><i />{{ copy.synced }}</span>
      </div>

      <HistoryTimeline
        :items="visibleTasks"
        :loading="loading"
        :locale="localeStore.locale"
        @open="openDetail"
        @ask-ai="askAi"
        @delete="confirmDelete"
        @clear="clearFilters"
      />

      <div v-if="pagination.totalPages > 1" class="pagination-row">
        <el-pagination
          v-model:current-page="pagination.page"
          v-model:page-size="pagination.pageSize"
          background
          layout="prev, pager, next"
          :total="pagination.total"
          @current-change="fetchTasks"
        />
      </div>
    </main>

    <HistoryDetailDialog
      :visible="detailVisible"
      :loading="detailLoading"
      :detail="selectedDetail"
      :locale="localeStore.locale"
      @close="closeDetail"
      @delete="confirmDelete"
      @ask-ai="askAi"
    />
  </div>
</template>

<script setup>
import {
  ArrowLeft,
  ChatDotRound,
  Close,
  DataAnalysis,
  Grape,
  Operation,
  Refresh,
  Search,
} from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useRouter } from 'vue-router'

import {
  deleteHistoryTaskApi,
  getHistoryScenesApi,
  getHistorySummaryApi,
  getHistoryTaskDetailApi,
  getHistoryTasksApi,
} from '@/api/history'
import HistoryDetailDialog from '@/components/history/HistoryDetailDialog.vue'
import HistorySummaryCards from '@/components/history/HistorySummaryCards.vue'
import HistoryTimeline from '@/components/history/HistoryTimeline.vue'
import LanguageSwitcher from '@/components/LanguageSwitcher.vue'
import { useAgentStore } from '@/stores/agent'
import { useLocaleStore } from '@/stores/locale'

const router = useRouter()
const agentStore = useAgentStore()
const localeStore = useLocaleStore()

const loading = ref(false)
const summaryLoading = ref(false)
const detailLoading = ref(false)
const detailVisible = ref(false)
const showFilters = ref(false)
const tasks = ref([])
const scenes = ref([])
const selectedDetail = ref(null)
const summary = ref({ total_tasks: 0, today_tasks: 0, status_counts: {} })

const pagination = reactive({ page: 1, pageSize: 10, total: 0, totalPages: 0 })
const filters = reactive({ keyword: '', taskType: '', status: '', sceneId: null, dateRange: [] })

const copy = computed(() => {
  const en = localeStore.locale === 'en'
  return en ? {
    back: 'Back to home', title: 'Detection History', subtitle: 'Review your saved YOLO detection tasks', aiAgent: 'AI Agent', analytics: 'Analytics',
    searchPlaceholder: 'Search this page by task, scene or status…', clear: 'Clear search', filters: 'Filters', refresh: 'Refresh', taskType: 'Detection type', allTypes: 'All types', single: 'Single image', batch: 'Batch images', video: 'Video', status: 'Status', allStatuses: 'All statuses', completed: 'Completed', processing: 'Processing', pending: 'Pending', failed: 'Failed', scene: 'Scene', allScenes: 'All scenes', dateRange: 'Date range', to: 'to', startDate: 'Start date', endDate: 'End date', clearFilters: 'Clear all filters', showing: 'Showing', of: 'of', records: 'records', currentPageSearch: 'search applies to this page', synced: 'Synced with history API', deleteTitle: 'Delete detection record?', deleteMessage: 'This removes the task and its stored detection results. This action cannot be undone.', deleteDone: 'Detection record deleted', deleteFailed: 'Unable to delete detection record', detailFailed: 'Unable to load detection details', loadFailed: 'Unable to load history', askPrompt: 'Analyze detection task #{id}. It is a {type} task with {objects} detected objects. Please explain possible risks and recommended next steps based on my history.',
  } : {
    back: '返回首页', title: '检测历史', subtitle: '查看当前账号保存的 YOLO 检测任务', aiAgent: 'AI 智能体', analytics: '数据分析',
    searchPlaceholder: '搜索本页任务编号、场景或状态…', clear: '清除搜索', filters: '筛选', refresh: '刷新', taskType: '检测类型', allTypes: '全部类型', single: '单图检测', batch: '批量检测', video: '视频检测', status: '任务状态', allStatuses: '全部状态', completed: '已完成', processing: '处理中', pending: '待处理', failed: '失败', scene: '检测场景', allScenes: '全部场景', dateRange: '日期范围', to: '至', startDate: '开始日期', endDate: '结束日期', clearFilters: '清除全部筛选', showing: '当前显示', of: '/', records: '条检测记录', currentPageSearch: '关键词仅筛选当前页', synced: '已连接历史记录接口', deleteTitle: '确认删除检测记录？', deleteMessage: '该操作会同时删除任务及其保存的检测结果，且无法恢复。', deleteDone: '检测记录已删除', deleteFailed: '删除检测记录失败', detailFailed: '检测详情加载失败', loadFailed: '历史记录加载失败', askPrompt: '请分析检测任务 #{id}。这是一次{type}任务，共检测到 {objects} 个目标。请结合我的历史记录说明可能风险和后续建议。',
  }
})

const activeFilterCount = computed(() => [filters.taskType, filters.status, filters.sceneId, filters.dateRange?.length].filter(Boolean).length)
const visibleTasks = computed(() => {
  const keyword = filters.keyword.toLowerCase()
  if (!keyword) return tasks.value
  return tasks.value.filter((task) => [task.id, task.task_type, task.status, task.scene_name]
    .filter((value) => value !== null && value !== undefined)
    .some((value) => String(value).toLowerCase().includes(keyword)))
})

function formatDateParam(value) {
  if (!(value instanceof Date) || Number.isNaN(value.getTime())) return undefined
  const year = value.getFullYear()
  const month = String(value.getMonth() + 1).padStart(2, '0')
  const day = String(value.getDate()).padStart(2, '0')
  return `${year}-${month}-${day}`
}

async function fetchTasks() {
  loading.value = true
  try {
    const response = await getHistoryTasksApi({
      page: pagination.page,
      page_size: pagination.pageSize,
      task_type: filters.taskType || undefined,
      status: filters.status || undefined,
      scene_id: filters.sceneId || undefined,
      start_date: formatDateParam(filters.dateRange?.[0]),
      end_date: formatDateParam(filters.dateRange?.[1]),
    })
    tasks.value = Array.isArray(response?.items) ? response.items : []
    pagination.total = response?.total ?? 0
    pagination.totalPages = response?.total_pages ?? 0
  } catch (error) {
    console.error('[History] 加载任务失败', error)
    tasks.value = []
    ElMessage.error(copy.value.loadFailed)
  } finally {
    loading.value = false
  }
}

async function fetchSummary() {
  summaryLoading.value = true
  try {
    summary.value = await getHistorySummaryApi()
  } catch (error) {
    console.error('[History] 加载摘要失败', error)
  } finally {
    summaryLoading.value = false
  }
}

async function fetchScenes() {
  try {
    const response = await getHistoryScenesApi()
    scenes.value = Array.isArray(response?.scenes) ? response.scenes : []
  } catch (error) {
    console.error('[History] 加载场景失败', error)
  }
}

async function refreshAll() {
  await Promise.all([fetchTasks(), fetchSummary(), fetchScenes()])
}

async function openDetail(task) {
  detailVisible.value = true
  detailLoading.value = true
  selectedDetail.value = { task, class_counts: {}, results: [] }
  try {
    selectedDetail.value = await getHistoryTaskDetailApi(task.id)
  } catch (error) {
    console.error('[History] 加载详情失败', error)
    ElMessage.error(copy.value.detailFailed)
  } finally {
    detailLoading.value = false
  }
}

function closeDetail() {
  detailVisible.value = false
  selectedDetail.value = null
}

async function confirmDelete(task) {
  if (!task?.id) return
  try {
    await ElMessageBox.confirm(copy.value.deleteMessage, copy.value.deleteTitle, {
      type: 'warning', confirmButtonText: localeStore.locale === 'en' ? 'Delete' : '确认删除', cancelButtonText: localeStore.locale === 'en' ? 'Cancel' : '取消',
    })
    await deleteHistoryTaskApi(task.id)
    if (selectedDetail.value?.task?.id === task.id) closeDetail()
    if (tasks.value.length === 1 && pagination.page > 1) pagination.page -= 1
    await Promise.all([fetchTasks(), fetchSummary()])
    ElMessage.success(copy.value.deleteDone)
  } catch (error) {
    if (error === 'cancel' || error === 'close') return
    console.error('[History] 删除任务失败', error)
    ElMessage.error(copy.value.deleteFailed)
  }
}

function askAi(task) {
  if (!task?.id) return
  const type = localeStore.locale === 'en'
    ? ({ single: 'single-image', batch: 'batch-image', video: 'video' }[task.task_type] || 'detection')
    : ({ single: '单图检测', batch: '批量检测', video: '视频检测' }[task.task_type] || '检测')
  const prompt = copy.value.askPrompt
    .replace('{id}', task.id)
    .replace('{type}', type)
    .replace('{objects}', task.total_objects ?? 0)
  agentStore.queueHomePrompt(prompt)
  router.push('/ai-chat')
}

function clearFilters() {
  filters.keyword = ''
  filters.taskType = ''
  filters.status = ''
  filters.sceneId = null
  filters.dateRange = []
}

watch(
  () => [filters.taskType, filters.status, filters.sceneId, filters.dateRange?.[0]?.getTime?.(), filters.dateRange?.[1]?.getTime?.()],
  () => {
    pagination.page = 1
    fetchTasks()
  },
)

onMounted(refreshAll)
</script>

<style scoped>
.history-page { min-height: 100vh; background: #f8faf8; color: #1f2d24; }
.history-header { position: sticky; top: 0; z-index: 20; min-height: 72px; padding: 12px 28px; display: flex; align-items: center; justify-content: space-between; gap: 20px; box-sizing: border-box; border-bottom: 1px solid rgba(222, 229, 224, .9); background: rgba(250, 252, 250, .9); backdrop-filter: blur(16px); }
.header-left, .header-nav { display: flex; align-items: center; }
.header-left { gap: 10px; min-width: 0; }
.icon-button { width: 34px; height: 34px; display: grid; place-items: center; border-radius: 10px; color: #68766d; text-decoration: none; }
.icon-button:hover { background: #edf2ee; color: #25372c; }
.brand-mark { width: 34px; height: 34px; margin-left: 2px; display: grid; place-items: center; border-radius: 10px; background: #1c8b51; color: #fff; font-size: 18px; }
.header-left h1 { margin: 0; color: #17251c; font-size: 16px; font-weight: 800; }
.header-left p { margin: 2px 0 0; color: #879189; font-size: 10px; }
.header-nav { gap: 7px; }
.header-nav > a { display: inline-flex; align-items: center; gap: 6px; padding: 8px 10px; border-radius: 9px; color: #637068; text-decoration: none; font-size: 12px; }
.header-nav > a:hover { background: #edf3ef; color: #18834a; }
.history-container { width: min(1040px, calc(100% - 36px)); margin: 0 auto; padding: 28px 0 46px; }
.filter-section { margin-top: 22px; }
.filter-primary-row { display: flex; gap: 9px; }
.search-box { position: relative; flex: 1; min-width: 0; display: flex; align-items: center; }
.search-box > .el-icon { position: absolute; left: 13px; z-index: 1; color: #8d9790; }
.search-box input { width: 100%; height: 42px; box-sizing: border-box; padding: 0 38px; border: 1px solid #dfe5e1; border-radius: 12px; outline: none; background: #fff; color: #28382e; font-size: 12px; transition: .2s; }
.search-box input:focus { border-color: #87c39c; box-shadow: 0 0 0 3px rgba(28, 139, 81, .08); }
.search-box button { position: absolute; right: 10px; border: 0; background: transparent; color: #8b958e; cursor: pointer; }
.filter-toggle, .refresh-button { height: 42px; border: 1px solid #dfe5e1; border-radius: 12px; background: #fff; color: #647168; display: inline-flex; align-items: center; justify-content: center; gap: 6px; cursor: pointer; }
.filter-toggle { padding: 0 14px; font-size: 12px; font-weight: 700; }
.filter-toggle.active { border-color: #a6d3b5; background: #eaf7ee; color: #18834a; }
.filter-toggle span { min-width: 17px; height: 17px; display: grid; place-items: center; border-radius: 50%; background: #1b8a50; color: #fff; font-size: 9px; }
.refresh-button { width: 42px; }
.spinning { animation: spin .8s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }
.filter-panel { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 13px; margin-top: 10px; padding: 16px; border: 1px solid #e1e7e3; border-radius: 15px; background: #fff; box-shadow: 0 10px 28px rgba(44, 80, 56, .05); }
.filter-panel label { min-width: 0; }
.filter-panel label > span { display: block; margin-bottom: 6px; color: #7a867e; font-size: 10px; font-weight: 700; }
.filter-panel :deep(.el-select), .filter-panel :deep(.el-date-editor) { width: 100%; }
.date-field { grid-column: span 2; }
.clear-filters { align-self: end; justify-self: start; height: 32px; border: 0; background: transparent; color: #718078; display: inline-flex; align-items: center; gap: 4px; font-size: 10px; cursor: pointer; }
.clear-filters:hover { color: #18834a; }
.result-meta { min-height: 38px; display: flex; align-items: center; justify-content: space-between; gap: 12px; color: #818c85; font-size: 10px; }
.result-meta p { margin: 0; }
.result-meta b { color: #33453a; }
.api-note { display: inline-flex; align-items: center; gap: 5px; }
.api-note i { width: 6px; height: 6px; border-radius: 50%; background: #2aad64; box-shadow: 0 0 0 3px #dff4e7; }
.pagination-row { display: flex; justify-content: center; margin-top: 22px; }

@media (max-width: 760px) {
  .history-header { align-items: flex-start; padding: 12px 16px; }
  .header-left p { display: none; }
  .header-nav > a { width: 34px; height: 34px; padding: 0; justify-content: center; }
  .header-nav > a :deep(+ *) { display: none; }
  .header-nav > a { font-size: 0; }
  .header-nav > a .el-icon { font-size: 15px; }
  .history-container { width: min(100% - 24px, 1040px); padding-top: 18px; }
  .filter-panel { grid-template-columns: 1fr 1fr; }
  .date-field { grid-column: span 2; }
}

@media (max-width: 520px) {
  .history-header { gap: 8px; }
  .brand-mark { display: none; }
  .header-nav { gap: 2px; }
  .filter-primary-row { flex-wrap: wrap; }
  .search-box { flex-basis: 100%; }
  .filter-toggle { flex: 1; }
  .filter-panel { grid-template-columns: 1fr; }
  .date-field { grid-column: auto; }
  .result-meta { align-items: flex-start; flex-direction: column; padding: 10px 0; }
}
</style>
