<template>
  <section v-if="canAssess" class="severity-panel">
    <div class="severity-intro">
      <div>
        <span class="severity-kicker">{{ copy.kicker }}</span>
        <strong>{{ assessment ? copy.completedTitle : copy.title }}</strong>
        <p>{{ assessment ? assessment.summary : copy.description }}</p>
      </div>

      <span
        v-if="assessment"
        class="risk-badge"
        :class="`risk-${assessment.risk_level}`"
      >
        {{ riskLabel(assessment.risk_level) }}
      </span>
    </div>

    <div v-if="assessment" class="assessment-result">
      <div class="assessment-meta">
        <span>{{ assessment.class_name_display || selectedClassLabel }}</span>
        <span>{{ copy.confidence }}：{{ confidenceLabel(assessment.assessment_confidence) }}</span>
      </div>

      <div v-if="assessment.reasons?.length" class="result-block">
        <strong>{{ copy.reasons }}</strong>
        <ul>
          <li v-for="reason in assessment.reasons" :key="reason">{{ reason }}</li>
        </ul>
      </div>

      <div v-if="assessment.uncertainties?.length" class="result-block uncertainty-block">
        <strong>{{ copy.uncertainties }}</strong>
        <ul>
          <li v-for="item in assessment.uncertainties" :key="item">{{ item }}</li>
        </ul>
      </div>

      <div v-if="assessment.recommended_actions?.length" class="result-block action-block">
        <strong>{{ copy.actions }}</strong>
        <ol>
          <li v-for="action in assessment.recommended_actions" :key="action">{{ action }}</li>
        </ol>
      </div>
    </div>

    <button class="assessment-button" type="button" @click="openQuestionnaire">
      {{ assessment ? copy.reassess : copy.start }}
      <span>→</span>
    </button>

    <el-dialog
      v-model="dialogVisible"
      :title="copy.dialogTitle"
      width="min(720px, 94vw)"
      append-to-body
      destroy-on-close
      class="severity-dialog"
    >
      <div class="dialog-content">
        <div class="questionnaire-lead">
          <span class="questionnaire-icon">✦</span>
          <div>
            <strong>{{ copy.dialogLead }}</strong>
            <p>{{ copy.dialogDescription }}</p>
          </div>
        </div>

        <div v-if="classOptions.length > 1" class="class-selector">
          <label for="severity-class">{{ copy.selectClass }}</label>
          <el-select id="severity-class" v-model="selectedClass" style="width: 100%">
            <el-option
              v-for="item in classOptions"
              :key="item.value"
              :label="item.label"
              :value="item.value"
            />
          </el-select>
        </div>

        <div v-if="questionsLoading" class="questionnaire-loading">
          <span class="loading-dot" />
          {{ copy.loading }}
        </div>

        <div v-else-if="questions.length" class="questions-list">
          <section
            v-for="(question, index) in questions"
            :key="question.key"
            class="question-item"
          >
            <div class="question-title">
              <span>{{ index + 1 }}</span>
              <div>
                <strong>{{ question.label }}</strong>
                <small v-if="question.required">{{ copy.required }}</small>
              </div>
            </div>

            <div v-if="question.type === 'single'" class="option-list">
              <label v-for="option in question.options" :key="option" class="option-row">
                <input v-model="answers[question.key]" type="radio" :name="question.key" :value="option" />
                <span>{{ option }}</span>
              </label>
            </div>

            <div v-else-if="question.type === 'multiple'" class="option-list checkbox-list">
              <label v-for="option in question.options" :key="option" class="option-row">
                <input v-model="answers[question.key]" type="checkbox" :value="option" />
                <span>{{ option }}</span>
              </label>
            </div>

            <textarea
              v-else-if="question.type === 'text'"
              v-model.trim="additionalNotes"
              class="notes-input"
              :placeholder="copy.notesPlaceholder"
              maxlength="1000"
              rows="4"
            />
          </section>
        </div>

        <div v-else class="questionnaire-empty">{{ copy.loadFailed }}</div>
      </div>

      <template #footer>
        <div class="dialog-footer">
          <span>{{ copy.minimumHint(minimumKnownAnswers) }}</span>
          <div>
            <button class="cancel-button" type="button" @click="dialogVisible = false">{{ copy.cancel }}</button>
            <button
              class="submit-button"
              type="button"
              :disabled="submitting || questionsLoading || !questions.length"
              @click="submitAssessment"
            >
              {{ submitting ? copy.submitting : copy.submit }}
            </button>
          </div>
        </div>
      </template>
    </el-dialog>
  </section>
</template>

<script setup>
import { getHistoryTaskDetailApi, getSeverityQuestionsApi, submitSeverityAssessmentApi } from '@/api/history'
import { useLocaleStore } from '@/stores/locale'
import { ElMessage } from 'element-plus'
import { computed, reactive, ref, watch } from 'vue'

// 同一页面可能同时展示同一任务的多种结果卡片，缓存详情请求避免重复读取。
const detailRequestCache = new Map()

const props = defineProps({
  result: {
    type: Object,
    required: true,
  },
})

const emit = defineEmits(['updated'])

const COPY = {
  zh: {
    kicker: '现场风险评估', title: '需要进一步判断病害严重程度？', completedTitle: '严重程度评估已完成',
    description: '回答几项现场问题，结合本次检测结果生成状态评估。', start: '让 AI 评估严重程度', reassess: '重新评估',
    dialogTitle: '病害严重程度问卷', dialogLead: '补充现场情况', dialogDescription: 'YOLO 置信度不代表病害严重程度，评估需要结合真实受害范围与传播情况。',
    selectClass: '评估类别', loading: '正在加载问卷…', loadFailed: '问卷加载失败，请稍后重试。', required: '必答',
    notesPlaceholder: '例如：最近连续降雨，病斑在三天内明显增多……', cancel: '稍后填写', submit: '提交评估', submitting: '正在评估…',
    requiredMessage: '请先完成所有必答问题', success: '严重程度评估已生成', confidence: '评估可信度', reasons: '判断依据', uncertainties: '仍需确认', actions: '建议措施',
    minimumHint: (count) => `至少提供 ${count} 项明确信息，可获得更可靠的评估。`,
    risks: { low: '低风险', moderate: '中等风险', high: '高风险', critical: '严重风险', insufficient_information: '信息不足' },
    confidences: { low: '较低', medium: '中等', high: '较高' },
  },
  en: {
    kicker: 'Field risk assessment', title: 'Need a severity assessment?', completedTitle: 'Severity assessment complete',
    description: 'Answer a few field questions to assess the current condition alongside the detection result.', start: 'Ask AI to assess severity', reassess: 'Reassess',
    dialogTitle: 'Disease severity questionnaire', dialogLead: 'Add field observations', dialogDescription: 'YOLO confidence is not disease severity. The assessment also needs the affected area and spread information.',
    selectClass: 'Class to assess', loading: 'Loading questionnaire…', loadFailed: 'Unable to load the questionnaire. Try again later.', required: 'Required',
    notesPlaceholder: 'For example: Continuous rain recently, with lesions increasing over three days…', cancel: 'Later', submit: 'Submit assessment', submitting: 'Assessing…',
    requiredMessage: 'Complete all required questions first', success: 'Severity assessment generated', confidence: 'Assessment confidence', reasons: 'Assessment basis', uncertainties: 'Uncertainties', actions: 'Recommended actions',
    minimumHint: (count) => `Provide at least ${count} known answers for a more reliable assessment.`,
    risks: { low: 'Low risk', moderate: 'Moderate risk', high: 'High risk', critical: 'Critical risk', insufficient_information: 'Insufficient information' },
    confidences: { low: 'Low', medium: 'Medium', high: 'High' },
  },
}

const localeStore = useLocaleStore()
const copy = computed(() => COPY[localeStore.locale === 'en' ? 'en' : 'zh'])
const dialogVisible = ref(false)
const questionsLoading = ref(false)
const submitting = ref(false)
const questions = ref([])
const minimumKnownAnswers = ref(3)
const loadedLocale = ref('')
const answers = reactive({})
const additionalNotes = ref('')
const selectedClass = ref('')
const assessment = ref(null)

const resultData = computed(() => props.result?.data || props.result || {})
const taskId = computed(() => resultData.value.task_id ?? resultData.value.task?.id ?? null)

const detections = computed(() => {
  const result = resultData.value
  const direct = result.detections || result.predictions || result.objects
  if (Array.isArray(direct)) return direct
  if (!Array.isArray(result.results)) return []
  return result.results.flatMap((entry) => Array.isArray(entry?.detections) ? entry.detections : [entry])
})

const classOptions = computed(() => {
  const rawCounts = resultData.value.class_counts || {}
  const displayCounts = resultData.value.class_counts_display || {}
  const displayNames = Object.keys(displayCounts)
  const detectionDisplayMap = new Map()

  detections.value.forEach((item) => {
    const raw = item.class_name || item.label || item.name
    const display = item.class_name_display || item.class_name_cn || item.disease_name || raw
    if (raw && !detectionDisplayMap.has(raw)) detectionDisplayMap.set(raw, display)
  })

  const options = Object.keys(rawCounts).map((raw, index) => ({
    value: raw,
    label: detectionDisplayMap.get(raw) || displayNames[index] || raw,
  }))

  if (!options.length) {
    detectionDisplayMap.forEach((label, value) => options.push({ value, label }))
  }

  const directClass = resultData.value.class_name
  if (!options.length && directClass) {
    options.push({
      value: directClass,
      label: resultData.value.class_name_display || resultData.value.class_name_cn || directClass,
    })
  }

  return options
})

const totalObjects = computed(() => Number(resultData.value.total_objects ?? detections.value.length ?? 0))
const canAssess = computed(() => Boolean(taskId.value && totalObjects.value > 0 && classOptions.value.length))
const selectedClassLabel = computed(() => classOptions.value.find((item) => item.value === selectedClass.value)?.label || selectedClass.value)

const riskLabel = (value) => copy.value.risks[value] || value || '—'
const confidenceLabel = (value) => copy.value.confidences[value] || value || '—'

const applyAssessmentAnswers = () => {
  const savedAnswers = assessment.value?.answers
  if (!savedAnswers || typeof savedAnswers !== 'object') return
  questions.value.forEach((question) => {
    if (question.type === 'text') return
    const value = savedAnswers[question.key]
    if (value !== undefined && value !== null) answers[question.key] = value
  })
  additionalNotes.value = savedAnswers.additional_notes || ''
}

const usePersistedAssessments = (items) => {
  if (!Array.isArray(items) || !items.length) return
  const matched = items.find((item) => item.class_name === selectedClass.value) || items[0]
  assessment.value = matched
  selectedClass.value = matched.class_name || selectedClass.value || classOptions.value[0]?.value || ''
}

const loadPersistedAssessment = async () => {
  if (!canAssess.value) return
  if (Array.isArray(resultData.value.severity_assessments)) {
    usePersistedAssessments(resultData.value.severity_assessments)
    return
  }

  const id = taskId.value
  if (!detailRequestCache.has(id)) {
    detailRequestCache.set(id, getHistoryTaskDetailApi(id).catch((error) => {
      detailRequestCache.delete(id)
      throw error
    }))
  }
  try {
    const detail = await detailRequestCache.get(id)
    usePersistedAssessments(detail?.severity_assessments)
  } catch (error) {
    // 评估入口本身仍然可用；详情恢复失败不应隐藏已有检测结果。
    console.warn('[严重程度评估恢复失败]', error)
  }
}

const resetAnswers = () => {
  Object.keys(answers).forEach((key) => delete answers[key])
  questions.value.forEach((question) => {
    if (question.type === 'multiple') answers[question.key] = []
    else if (question.type !== 'text') answers[question.key] = ''
  })
  additionalNotes.value = ''
}

const loadQuestions = async () => {
  questionsLoading.value = true
  try {
    const response = await getSeverityQuestionsApi()
    questions.value = Array.isArray(response?.questions) ? response.questions : []
    minimumKnownAnswers.value = Number(response?.minimum_known_answers || 3)
    loadedLocale.value = localeStore.locale
    resetAnswers()
    applyAssessmentAnswers()
  } finally {
    questionsLoading.value = false
  }
}

const openQuestionnaire = async () => {
  selectedClass.value = assessment.value?.class_name || selectedClass.value || classOptions.value[0]?.value || ''
  dialogVisible.value = true
  if (!questions.value.length || loadedLocale.value !== localeStore.locale) {
    try {
      await loadQuestions()
    } catch {
      questions.value = []
    }
  }
}

const hasAnswer = (question) => {
  const value = answers[question.key]
  return Array.isArray(value) ? value.length > 0 : Boolean(String(value || '').trim())
}

const submitAssessment = async () => {
  const missingRequired = questions.value.some((question) => (
    question.required && question.type !== 'text' && !hasAnswer(question)
  ))
  if (missingRequired) {
    ElMessage.warning(copy.value.requiredMessage)
    return
  }

  const payloadAnswers = {}
  questions.value.forEach((question) => {
    if (question.type !== 'text' && hasAnswer(question)) payloadAnswers[question.key] = answers[question.key]
  })

  submitting.value = true
  try {
    const response = await submitSeverityAssessmentApi(taskId.value, {
      class_name: selectedClass.value,
      answers: payloadAnswers,
      additional_notes: additionalNotes.value || null,
    })
    assessment.value = {
      ...response,
      answers: {
        ...payloadAnswers,
        ...(additionalNotes.value ? { additional_notes: additionalNotes.value } : {}),
      },
    }
    detailRequestCache.delete(taskId.value)
    dialogVisible.value = false
    ElMessage.success(copy.value.success)
    emit('updated', assessment.value)
  } finally {
    submitting.value = false
  }
}

watch(
  () => [taskId.value, classOptions.value.length],
  () => {
    if (!selectedClass.value) selectedClass.value = classOptions.value[0]?.value || ''
    loadPersistedAssessment()
  },
  { immediate: true },
)
</script>

<style scoped>
.severity-panel {
  box-sizing: border-box;
  width: 100%;
  max-width: 680px;
  padding: 18px;
  border: 1px solid #d8eadc;
  border-radius: 18px;
  background: linear-gradient(145deg, #f7fcf8, #fff);
  box-shadow: 0 5px 18px rgba(22, 101, 52, .06);
}
.severity-intro { display: flex; align-items: flex-start; justify-content: space-between; gap: 14px; }
.severity-intro > div { min-width: 0; }
.severity-kicker { display: block; margin-bottom: 5px; color: #15803d; font-size: 11px; font-weight: 800; letter-spacing: .08em; text-transform: uppercase; }
.severity-intro strong { color: #1f2937; font-size: 15px; }
.severity-intro p { margin: 6px 0 0; color: #69766d; font-size: 13px; line-height: 1.6; }
.risk-badge { flex-shrink: 0; padding: 6px 10px; border-radius: 999px; font-size: 12px; font-weight: 800; }
.risk-low { background: #eaf8ed; color: #15803d; }
.risk-moderate { background: #fff7dd; color: #a16207; }
.risk-high { background: #fff0e6; color: #c2410c; }
.risk-critical { background: #fef0f0; color: #c81e1e; }
.risk-insufficient_information { background: #f1f3f2; color: #66706a; }
.assessment-result { margin-top: 14px; padding: 14px; border: 1px solid #e0ebe3; border-radius: 13px; background: #fff; }
.assessment-meta { display: flex; flex-wrap: wrap; gap: 7px 14px; margin-bottom: 11px; color: #657168; font-size: 12px; }
.result-block + .result-block { margin-top: 11px; }
.result-block strong { color: #334139; font-size: 12px; }
.result-block ul, .result-block ol { margin: 6px 0 0; padding-left: 20px; color: #536158; font-size: 12px; line-height: 1.65; }
.uncertainty-block { color: #9a6700; }
.action-block { padding-top: 10px; border-top: 1px solid #edf1ee; }
.assessment-button { display: flex; width: 100%; align-items: center; justify-content: space-between; margin-top: 14px; padding: 11px 14px; border: 0; border-radius: 11px; background: #15803d; color: #fff; cursor: pointer; font-weight: 750; }
.assessment-button:hover { background: #166534; }
.dialog-content { max-height: 62vh; overflow-y: auto; padding-right: 5px; }
.questionnaire-lead { display: flex; gap: 11px; margin-bottom: 18px; padding: 14px; border-radius: 13px; background: #eef9f1; }
.questionnaire-icon { display: grid; width: 32px; height: 32px; flex-shrink: 0; place-items: center; border-radius: 10px; background: #15803d; color: #fff; }
.questionnaire-lead strong { color: #1f3d2a; }
.questionnaire-lead p { margin: 4px 0 0; color: #647269; font-size: 12px; line-height: 1.55; }
.class-selector { margin-bottom: 18px; }
.class-selector label { display: block; margin-bottom: 7px; color: #374151; font-size: 13px; font-weight: 700; }
.questionnaire-loading, .questionnaire-empty { display: flex; min-height: 180px; align-items: center; justify-content: center; gap: 9px; color: #718078; }
.loading-dot { width: 9px; height: 9px; border-radius: 50%; background: #16a34a; animation: severity-pulse .8s infinite alternate; }
@keyframes severity-pulse { to { opacity: .25; transform: scale(.7); } }
.questions-list { display: flex; flex-direction: column; gap: 13px; }
.question-item { padding: 15px; border: 1px solid #e3e9e5; border-radius: 13px; background: #fff; }
.question-title { display: flex; align-items: flex-start; gap: 9px; margin-bottom: 11px; }
.question-title > span { display: grid; width: 24px; height: 24px; flex-shrink: 0; place-items: center; border-radius: 8px; background: #eaf7ed; color: #15803d; font-size: 11px; font-weight: 800; }
.question-title div { display: flex; align-items: center; gap: 7px; }
.question-title strong { color: #27352c; font-size: 13px; line-height: 1.5; }
.question-title small { flex-shrink: 0; color: #dc2626; font-size: 10px; }
.option-list { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 8px; }
.option-row { display: flex; align-items: flex-start; gap: 8px; padding: 9px 10px; border: 1px solid #e4e9e6; border-radius: 9px; color: #4b5850; cursor: pointer; font-size: 12px; line-height: 1.45; }
.option-row:has(input:checked) { border-color: #86c99a; background: #f0faf3; color: #166534; }
.option-row input { margin-top: 2px; accent-color: #15803d; }
.notes-input { box-sizing: border-box; width: 100%; resize: vertical; padding: 11px 12px; border: 1px solid #dfe5e1; border-radius: 10px; color: #374151; font: inherit; font-size: 12px; line-height: 1.6; outline: none; }
.notes-input:focus { border-color: #4aaa69; box-shadow: 0 0 0 3px rgba(22, 163, 74, .1); }
.dialog-footer { display: flex; align-items: center; justify-content: space-between; gap: 12px; }
.dialog-footer > span { color: #7a857e; font-size: 11px; text-align: left; }
.dialog-footer > div { display: flex; flex-shrink: 0; gap: 9px; }
.cancel-button, .submit-button { padding: 9px 14px; border-radius: 9px; cursor: pointer; font-weight: 700; }
.cancel-button { border: 1px solid #dfe5e1; background: #fff; color: #4b5563; }
.submit-button { border: 1px solid #15803d; background: #15803d; color: #fff; }
.submit-button:disabled { opacity: .55; cursor: not-allowed; }
@media (max-width: 640px) {
  .severity-panel { padding: 15px; }
  .option-list { grid-template-columns: 1fr; }
  .dialog-footer { align-items: stretch; flex-direction: column; }
  .dialog-footer > div { justify-content: flex-end; }
}
</style>
