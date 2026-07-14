<template>
  <div class="diagnosis-card">
    <div class="diagnosis-header">
      <div>
        <div class="diagnosis-label">{{ hasApiResult ? '快捷检测结果' : 'Detected Disease' }}</div>
        <h3>{{ diseaseName }}</h3>
        <p>{{ plantName }}</p>
      </div>

      <div v-if="severity" class="severity-badge">
        {{ severity }}
      </div>
    </div>

    <div v-if="confidence !== null" class="confidence-section">
      <div class="confidence-row">
        <span>Confidence</span>
        <strong>{{ confidence }}%</strong>
      </div>

      <div class="progress-bar">
        <div
          class="progress-fill"
          :style="{ width: confidence + '%' }"
        />
      </div>
    </div>

    <div v-if="annotatedImage" class="diagnosis-image-section">
      <img
        :src="annotatedImage"
        class="diagnosis-image"
        alt="detection result"
      />
    </div>

    <div v-if="description" class="diagnosis-description">
      {{ description }}
    </div>

    <div v-if="detections.length" class="detection-list">
      <div class="section-title">检测目标（{{ totalObjects }}）</div>
      <div v-for="(detection, index) in detections" :key="index" class="detection-item">
        <span>{{ getDetectionName(detection, index) }}</span>
        <strong v-if="getDetectionConfidence(detection) !== null">
          {{ getDetectionConfidence(detection) }}%
        </strong>
      </div>
    </div>

    <div v-if="treatments.length" class="treatment-list">
      <div
        v-for="(treatment, idx) in treatments"
        :key="idx"
        class="treatment-item"
      >
        ✓ {{ treatment }}
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  item: {
    type: Object,
    required: true,
  },
})

const apiResult = computed(() => props.item.detectionResult || null)
const hasApiResult = computed(() => Boolean(apiResult.value))
const resultData = computed(() => apiResult.value?.data || apiResult.value || {})

const detections = computed(() => {
  const result = resultData.value
  const direct = result.detections || result.predictions || result.objects
  if (Array.isArray(direct)) return direct

  if (Array.isArray(result.results)) {
    return result.results.flatMap((entry) => (
      Array.isArray(entry?.detections)
        ? entry.detections.map((detection) => ({ ...detection, filename: entry.filename || entry.file_name }))
        : [entry]
    ))
  }

  return []
})

const totalObjects = computed(() => (
  resultData.value.total_objects ?? detections.value.length
))

const firstDetection = computed(() => detections.value[0] || {})
const diseaseName = computed(() => (
  props.item.disease
  || firstDetection.value.class_name
  || firstDetection.value.disease_name
  || firstDetection.value.label
  || (hasApiResult.value ? `检测完成，共 ${totalObjects.value} 个目标` : '未知病害')
))
const plantName = computed(() => (
  props.item.plant || resultData.value.plant || resultData.value.crop || props.item.content || ''
))
const severity = computed(() => props.item.severity || resultData.value.severity || '')

const toPercent = (value) => {
  const number = Number(value)
  if (!Number.isFinite(number)) return null
  return Math.round((number <= 1 ? number * 100 : number) * 10) / 10
}

const confidence = computed(() => toPercent(
  props.item.confidence
  ?? firstDetection.value.confidence
  ?? firstDetection.value.conf
  ?? resultData.value.confidence,
))

const annotatedImage = computed(() => (
  props.item.annotatedImage
  || resultData.value.annotated_image_url
  || resultData.value.result_image_url
  || resultData.value.image_url
  || ''
))
const description = computed(() => props.item.description || (hasApiResult.value ? props.item.content : ''))
const treatments = computed(() => props.item.treatments || resultData.value.treatments || resultData.value.suggestions || [])

const getDetectionName = (detection, index) => (
  detection.class_name
  || detection.disease_name
  || detection.label
  || detection.name
  || detection.filename
  || `目标 ${index + 1}`
)

const getDetectionConfidence = (detection) => toPercent(detection.confidence ?? detection.conf)
</script>

<style scoped>
/* 把 ChatPage.vue 中 diagnosis-card 相关 CSS 全部剪切到这里 */
.diagnosis-card {
  width: 100%;
  max-width: 520px;
  background: white;
  border: 1px solid #e5e7eb;
  border-radius: 20px;
  padding: 20px;
  box-shadow: 0 6px 20px rgba(0,0,0,0.06);
}

.diagnosis-header {
  display: flex;
  justify-content: space-between;
  margin-bottom: 18px;
}

.diagnosis-label {
  color: #6b7280;
  font-size: 13px;
}

.diagnosis-header h3 {
  margin: 4px 0;
  color: #111827;
}

.diagnosis-header p {
  color: #6b7280;
}

.severity-badge {
  background: #fef2f2;
  color: #dc2626;
  padding: 8px 14px;
  border-radius: 999px;
  height: fit-content;
}

.confidence-row {
  display: flex;
  justify-content: space-between;
  margin-bottom: 8px;
}

.progress-bar {
  height: 10px;
  background: #e5e7eb;
  border-radius: 999px;
  overflow: hidden;
  margin-bottom: 18px;
}

.progress-fill {
  height: 100%;
  background: #16a34a;
}

.diagnosis-description {
  line-height: 1.7;
  margin-bottom: 18px;
  color: #374151;
}

.treatment-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.detection-list {
  margin-bottom: 18px;
}

.section-title {
  margin-bottom: 8px;
  color: #374151;
  font-size: 14px;
  font-weight: 700;
}

.detection-item {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  padding: 9px 11px;
  border-bottom: 1px solid #f3f4f6;
  color: #4b5563;
  font-size: 14px;
}

.detection-item strong {
  color: #15803d;
}

.treatment-item {
  background: #f0fdf4;
  color: #166534;
  padding: 10px 12px;
  border-radius: 10px;
}

.diagnosis-image-section {
  margin-bottom: 18px;
}

.diagnosis-image {
  width: 100%;
  border-radius: 14px;
  border: 1px solid #e5e7eb;
}
</style>
