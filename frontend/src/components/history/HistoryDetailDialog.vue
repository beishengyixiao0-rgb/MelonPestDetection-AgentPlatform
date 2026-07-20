<template>
  <el-dialog
    :model-value="visible"
    :title="locale === 'en' ? `Detection #${task?.id ?? ''}` : `检测任务 #${task?.id ?? ''}`"
    width="min(860px, 92vw)"
    destroy-on-close
    class="history-detail-dialog"
    @close="$emit('close')"
  >
    <div v-loading="loading" class="detail-content">
      <template v-if="detail?.task">
        <section class="detail-overview">
          <div class="overview-main">
            <div class="overview-icon"><el-icon><DataAnalysis /></el-icon></div>
            <div>
              <span>{{ taskTypeLabel(detail.task.task_type) }}</span>
              <h3>{{ primaryClass }}</h3>
              <p>{{ detail.task.scene_name || (locale === 'en' ? 'General detection scene' : '通用检测场景') }}</p>
            </div>
          </div>
          <span class="detail-status" :class="detail.task.status">
            {{ statusLabel(detail.task.status) }}
          </span>
        </section>

        <section class="metric-grid">
          <div><span>{{ locale === 'en' ? 'Objects' : '检测目标' }}</span><strong>{{ detail.task.total_objects ?? 0 }}</strong></div>
          <div><span>{{ locale === 'en' ? 'Files' : '文件数量' }}</span><strong>{{ detail.task.total_images ?? 0 }}</strong></div>
          <div><span>{{ locale === 'en' ? 'Inference' : '推理耗时' }}</span><strong>{{ formatMs(detail.task.total_inference_time) }}</strong></div>
          <div><span>{{ locale === 'en' ? 'Confidence threshold' : '置信度阈值' }}</span><strong>{{ formatThreshold(detail.task.conf_threshold) }}</strong></div>
        </section>

        <section class="detail-section">
          <div class="section-heading">
            <div>
              <h4>{{ locale === 'en' ? 'Detected classes' : '检测类别统计' }}</h4>
              <p>{{ locale === 'en' ? 'Class totals returned by the history detail API.' : '根据历史详情接口返回的目标类别汇总。' }}</p>
            </div>
          </div>
          <div v-if="classEntries.length" class="class-list">
            <div v-for="item in classEntries" :key="item.name" class="class-pill">
              <span>{{ displayClassName(item.name) }}</span>
              <b>{{ item.count }}</b>
            </div>
          </div>
          <el-empty v-else :description="locale === 'en' ? 'No class statistics' : '暂无类别统计'" :image-size="60" />
        </section>

        <section class="status-management">
          <div class="status-copy">
            <span>{{ locale === 'en' ? 'Current follow-up' : '当前处理进度' }}</span>
            <strong>{{ treatmentLabel(detail.task.treatment_status) }}</strong>
            <small v-if="detail.task.treatment_updated_at">
              {{ locale === 'en' ? 'Updated' : '更新于' }} {{ formatDateTime(detail.task.treatment_updated_at) }}
            </small>
          </div>
          <el-select
            :model-value="detail.task.treatment_status || 'pending'"
            class="treatment-select"
            @change="updateTreatment"
          >
            <el-option v-for="option in treatmentOptions" :key="option.value" :label="option.label" :value="option.value" />
          </el-select>
        </section>

        <TaskWeatherPanel
          :task="detail.task"
          :locale="locale"
          @updated="$emit('weather-updated', $event)"
        />

        <section class="detail-section severity-section">
          <div class="section-heading">
            <div>
              <h4>{{ locale === 'en' ? 'Severity assessment' : '严重程度评估' }}</h4>
              <p>{{ locale === 'en' ? 'Assessment is saved with this detection record.' : '问卷评估结果会保存到本条检测记录。' }}</p>
            </div>
            <span v-if="detail.task.risk_level" class="risk-badge" :class="`risk-${detail.task.risk_level}`">
              {{ riskLabel(detail.task.risk_level) }}
            </span>
          </div>
          <SeverityAssessmentPanel
            v-if="assessmentSource"
            :result="assessmentSource"
            @updated="$emit('assessment-updated', $event)"
          />
          <el-empty v-else :description="locale === 'en' ? 'No disease object to assess' : '当前记录没有可评估的病害目标'" :image-size="60" />
        </section>

        <section v-if="previewImages.length" class="detail-section">
          <div class="section-heading">
            <div>
              <h4>{{ locale === 'en' ? 'Annotated results' : '检测标注图' }}</h4>
              <p>{{ locale === 'en' ? 'Click an image to preview it.' : '点击图片可查看完整标注结果。' }}</p>
            </div>
          </div>
          <div class="preview-grid">
            <button v-for="image in previewImages" :key="image.url" type="button" @click="previewUrl = image.url">
              <img :src="image.url" :alt="image.label" />
              <span>{{ image.label }}</span>
            </button>
          </div>
        </section>

        <section class="detail-section">
          <div class="section-heading">
            <div>
              <h4>{{ locale === 'en' ? 'Object details' : '目标明细' }}</h4>
              <p>{{ locale === 'en' ? `${resultRows.length} stored objects` : `数据库中共保存 ${resultRows.length} 条目标记录` }}</p>
            </div>
          </div>
          <el-table v-if="resultRows.length" :data="resultRows" size="small" max-height="260">
            <el-table-column :label="locale === 'en' ? 'Class' : '类别'" min-width="150">
              <template #default="{ row }">{{ resultClassName(row) }}</template>
            </el-table-column>
            <el-table-column :label="locale === 'en' ? 'Confidence' : '置信度'" width="110">
              <template #default="{ row }">{{ formatConfidence(row.confidence) }}</template>
            </el-table-column>
            <el-table-column prop="inference_time" :label="locale === 'en' ? 'Inference' : '推理耗时'" width="110">
              <template #default="{ row }">{{ formatMs(row.inference_time) }}</template>
            </el-table-column>
          </el-table>
          <el-empty v-else :description="locale === 'en' ? 'No object details' : '暂无目标明细'" :image-size="60" />
        </section>

        <section class="task-meta">
          <span>{{ locale === 'en' ? 'Created' : '创建时间' }}：{{ formatDateTime(detail.task.created_at) }}</span>
          <span>{{ locale === 'en' ? 'Completed' : '完成时间' }}：{{ formatDateTime(detail.task.completed_at) }}</span>
        </section>
      </template>
    </div>

    <template #footer>
      <div class="dialog-actions">
        <el-button type="danger" plain @click="$emit('delete', detail?.task)">
          <el-icon><Delete /></el-icon>{{ locale === 'en' ? 'Delete' : '删除记录' }}
        </el-button>
        <div>
          <el-button @click="$emit('close')">{{ locale === 'en' ? 'Close' : '关闭' }}</el-button>
          <el-button type="primary" @click="$emit('ask-ai', detail?.task)">
            <el-icon><ChatDotRound /></el-icon>{{ locale === 'en' ? 'Ask AI' : '询问 AI' }}
          </el-button>
        </div>
      </div>
    </template>
  </el-dialog>

  <el-dialog v-model="previewVisible" width="min(1000px, 94vw)" append-to-body>
    <img v-if="previewUrl" :src="previewUrl" class="full-preview" alt="annotated result" />
  </el-dialog>
</template>

<script setup>
import { ChatDotRound, DataAnalysis, Delete } from '@element-plus/icons-vue'
import { computed, ref, watch } from 'vue'
import SeverityAssessmentPanel from '@/components/SeverityAssessmentPanel.vue'
import TaskWeatherPanel from '@/components/history/TaskWeatherPanel.vue'

const props = defineProps({
  visible: Boolean,
  loading: Boolean,
  detail: { type: Object, default: null },
  locale: { type: String, default: 'zh' },
})

const emit = defineEmits(['close', 'delete', 'ask-ai', 'update-treatment', 'assessment-updated', 'weather-updated'])

const previewUrl = ref('')
const previewVisible = computed({
  get: () => Boolean(previewUrl.value),
  set: (value) => { if (!value) previewUrl.value = '' },
})

watch(() => props.visible, (visible) => {
  if (!visible) previewUrl.value = ''
})

const classEntries = computed(() => Object.entries(props.detail?.class_counts_display || props.detail?.class_counts || {}).map(([name, count]) => ({ name, count })))
const resultRows = computed(() => Array.isArray(props.detail?.results) ? props.detail.results : [])
const assessments = computed(() => Array.isArray(props.detail?.severity_assessments) ? props.detail.severity_assessments : [])
const assessmentSource = computed(() => {
  if (!props.detail?.task?.id || !classEntries.value.length) return null
  return {
    task_id: props.detail.task.id,
    total_objects: props.detail.task.total_objects ?? resultRows.value.length,
    class_counts: props.detail.class_counts || {},
    class_counts_display: props.detail.class_counts_display || {},
    detections: resultRows.value,
    severity_assessments: assessments.value,
  }
})
const treatmentOptions = computed(() => props.locale === 'en'
  ? [
      { value: 'pending', label: 'Pending treatment' },
      { value: 'in_progress', label: 'In progress' },
      { value: 'monitoring', label: 'Monitoring' },
      { value: 'treated', label: 'Treated' },
      { value: 'resolved', label: 'Resolved' },
    ]
  : [
      { value: 'pending', label: '待处理' },
      { value: 'in_progress', label: '处理中' },
      { value: 'monitoring', label: '观察中' },
      { value: 'treated', label: '已处理' },
      { value: 'resolved', label: '已解决' },
    ])
const primaryClass = computed(() => {
  if (!classEntries.value.length) return props.locale === 'en' ? 'No disease class recorded' : '暂无病害类别记录'
  return classEntries.value.map((item) => `${displayClassName(item.name)} × ${item.count}`).join(' · ')
})

const previewImages = computed(() => {
  const seen = new Set()
  return resultRows.value.reduce((images, row, index) => {
    const url = row.annotated_image_url
    if (!url || seen.has(url)) return images
    seen.add(url)
    images.push({ url, label: row.image_path?.split(/[\\/]/).pop() || `${props.locale === 'en' ? 'Result' : '结果'} ${index + 1}` })
    return images
  }, [])
})

function displayClassName(name) {
  const matched = resultRows.value.find((row) => row.class_name === name || row.class_name_display === name)
  return matched?.class_name_display || (props.locale === 'en' ? (matched?.class_name || name) : (matched?.class_name_cn || matched?.class_name || name))
}

function resultClassName(row) {
  return row.class_name_display || (props.locale === 'en' ? (row.class_name || '-') : (row.class_name_cn || row.class_name || '-'))
}

function riskLabel(risk) {
  const labels = props.locale === 'en'
    ? { low: 'Low risk', moderate: 'Moderate', high: 'High risk', critical: 'Critical', insufficient_information: 'More info needed' }
    : { low: '低风险', moderate: '中等风险', high: '高风险', critical: '严重风险', insufficient_information: '信息不足' }
  return labels[risk] || (props.locale === 'en' ? 'Not assessed' : '未评估')
}

function treatmentLabel(status) {
  return treatmentOptions.value.find((item) => item.value === (status || 'pending'))?.label || status || '-'
}

function updateTreatment(status) {
  emit('update-treatment', { task: props.detail?.task, status })
}

function taskTypeLabel(type) {
  const labels = props.locale === 'en'
    ? { single: 'Single image', batch: 'Batch images', video: 'Video detection' }
    : { single: '单图检测', batch: '批量图片检测', video: '视频检测' }
  return labels[type] || (props.locale === 'en' ? 'Detection task' : '检测任务')
}

function statusLabel(status) {
  const labels = props.locale === 'en'
    ? { completed: 'Completed', processing: 'Processing', pending: 'Pending', failed: 'Failed' }
    : { completed: '已完成', processing: '处理中', pending: '待处理', failed: '失败' }
  return labels[status] || status || '-'
}

function formatMs(value) {
  const number = Number(value)
  return Number.isFinite(number) ? `${number.toFixed(number >= 100 ? 0 : 1)} ms` : '0 ms'
}

function formatThreshold(value) {
  const number = Number(value)
  return Number.isFinite(number) ? `${Math.round(number * 100)}%` : '--'
}

function formatConfidence(value) {
  const number = Number(value)
  return Number.isFinite(number) ? `${(number * 100).toFixed(1)}%` : '--'
}

function formatDateTime(value) {
  if (!value) return '--'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return '--'
  return new Intl.DateTimeFormat(props.locale === 'en' ? 'en-US' : 'zh-CN', {
    year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit',
  }).format(date)
}
</script>

<style scoped>
.detail-content { min-height: 180px; }
.detail-overview { display: flex; justify-content: space-between; align-items: flex-start; gap: 16px; padding: 18px; border-radius: 18px; background: linear-gradient(135deg, #f2faf5, #fbfdfb); border: 1px solid #dceae1; }
.overview-main { display: flex; align-items: center; gap: 13px; min-width: 0; }
.overview-icon { width: 46px; height: 46px; flex: 0 0 46px; display: grid; place-items: center; border-radius: 14px; background: #dff4e6; color: #19834a; font-size: 21px; }
.overview-main span { color: #18834a; font-size: 11px; font-weight: 700; }
.overview-main h3 { margin: 3px 0; color: #19281f; font-size: 16px; }
.overview-main p { margin: 0; color: #7a867e; font-size: 12px; }
.detail-status { padding: 5px 10px; border-radius: 999px; background: #f2f4f3; color: #667269; font-size: 11px; font-weight: 700; white-space: nowrap; }
.detail-status.completed { background: #e7f7ed; color: #18854b; }
.detail-status.processing { background: #eaf4ff; color: #337ecc; }
.detail-status.pending { background: #fff4de; color: #b8790b; }
.detail-status.failed { background: #fff0f0; color: #c94444; }
.metric-grid { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 10px; margin-top: 14px; }
.metric-grid div { padding: 13px; border: 1px solid #e6ebe8; border-radius: 13px; background: #fff; }
.metric-grid span { display: block; color: #859088; font-size: 10px; }
.metric-grid strong { display: block; margin-top: 5px; color: #26372d; font-size: 15px; }
.detail-section { margin-top: 18px; }
.section-heading { display: flex; align-items: flex-start; justify-content: space-between; margin-bottom: 10px; }
.section-heading h4 { margin: 0; color: #26372d; font-size: 13px; }
.section-heading p { margin: 3px 0 0; color: #879189; font-size: 11px; line-height: 1.5; }
.class-list { display: flex; flex-wrap: wrap; gap: 8px; }
.class-pill { min-width: 120px; display: flex; align-items: center; justify-content: space-between; gap: 12px; padding: 8px 10px; border-radius: 10px; background: #f3f7f4; color: #46564c; font-size: 11px; }
.class-pill b { min-width: 22px; height: 22px; display: grid; place-items: center; border-radius: 999px; background: #dff3e6; color: #18854b; }
.status-management { display: flex; align-items: center; justify-content: space-between; gap: 16px; margin-top: 16px; padding: 13px 15px; border: 1px solid #e2e9e4; border-radius: 13px; background: #f8faf8; }
.status-copy span, .status-copy small { display: block; color: #839087; font-size: 10px; }
.status-copy strong { display: block; margin: 3px 0; color: #26372d; font-size: 14px; }
.treatment-select { width: 170px; }
.severity-section :deep(.severity-panel) { max-width: none; box-shadow: none; }
.risk-badge { flex-shrink: 0; padding: 5px 9px; border-radius: 999px; font-size: 10px; font-weight: 800; }
.risk-low { background: #e9f8ef; color: #18854b; }
.risk-moderate { background: #fff6e3; color: #ad730d; }
.risk-high { background: #fff0e7; color: #c45118; }
.risk-critical { background: #fff0f0; color: #c93636; }
.risk-insufficient_information { background: #f1f3f2; color: #737d77; }
.preview-grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 10px; }
.preview-grid button { padding: 0; overflow: hidden; text-align: left; border: 1px solid #e4e9e6; border-radius: 12px; background: #fff; cursor: pointer; }
.preview-grid img { width: 100%; height: 130px; display: block; object-fit: cover; background: #f3f5f4; }
.preview-grid span { display: block; padding: 7px 9px; color: #68756d; font-size: 10px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.task-meta { display: flex; flex-wrap: wrap; gap: 14px; margin-top: 16px; padding-top: 13px; border-top: 1px solid #edf0ee; color: #89938c; font-size: 10px; }
.dialog-actions { display: flex; justify-content: space-between; align-items: center; }
.full-preview { display: block; width: 100%; max-height: 78vh; object-fit: contain; }

@media (max-width: 680px) {
  .metric-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .preview-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .status-management { align-items: flex-start; flex-direction: column; }
  .treatment-select { width: 100%; }
}
</style>
