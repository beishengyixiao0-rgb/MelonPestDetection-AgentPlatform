<template>
  <div class="diagnosis-card">
    <div class="diagnosis-header">
      <div>
        <div class="diagnosis-label">{{ hasApiResult ? 'YOLO检测结果' : 'Detected Disease' }}</div>
        <h3>{{ diseaseName }}</h3>
        <p>{{ plantName }}</p>
      </div>

      <div v-if="severity" class="severity-badge">
        {{ severity }}
      </div>
    </div>

    <div v-if="hasApiResult && !isVideoResult" class="result-summary">
      <div class="summary-item">
        <strong>{{ totalObjects }}</strong>
        <span>检测目标</span>
      </div>
      <div class="summary-item">
        <strong>{{ categoryCount }}</strong>
        <span>类别数量</span>
      </div>
      <div class="summary-item">
        <strong>{{ inferenceTime }}</strong>
        <span>推理耗时</span>
      </div>
      <div v-if="isBatchResult" class="summary-item">
        <strong>{{ resultData.total_images ?? batchImages.length }}</strong>
        <span>图片数量</span>
      </div>
    </div>

    <div v-if="isCameraResult" class="camera-summary">
      <el-tag type="info">持续：{{ resultData.duration_seconds ?? 0 }}s</el-tag>
      <el-tag type="info">处理帧：{{ resultData.processed_frames ?? 0 }}</el-tag>
      <el-tag type="info">平均 FPS：{{ resultData.average_fps ?? 0 }}</el-tag>
      <el-tag type="success">
        累计检测：{{ resultData.total_detection_occurrences ?? 0 }} 次
      </el-tag>
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

    <!-- 视频检测结果：优先播放标注视频，缺失时展示关键帧 -->
    <div v-if="isVideoResult" class="video-result">
      <div class="video-info">
        <el-tag type="info">时长：{{ resultData.duration_seconds ?? 0 }}s</el-tag>
        <el-tag type="info">FPS：{{ resultData.fps ?? 0 }}</el-tag>
        <el-tag type="info">总帧：{{ resultData.total_frames ?? 0 }}</el-tag>
        <el-tag type="info">处理帧：{{ resultData.processed_frames ?? 0 }}</el-tag>
        <el-tag v-if="resultData.sampled_frames != null" type="info">
          采样帧：{{ resultData.sampled_frames }}
        </el-tag>
        <el-tag v-if="videoResolution" type="info">分辨率：{{ videoResolution }}</el-tag>
        <el-tag type="success">目标：{{ totalObjects }}</el-tag>
      </div>

      <div v-if="annotatedVideoUrl" class="video-player">
        <video
          :src="annotatedVideoUrl"
          controls
          playsinline
          preload="metadata"
        />
      </div>

      <div v-else-if="thumbnailFrames.length" class="frames-fallback">
        <p class="fallback-hint">
          标注视频生成中或上传失败，以下为关键帧预览：
        </p>

        <div class="frames-container">
          <button
            v-for="(frame, index) in thumbnailFrames"
            :key="frame.frame_index ?? index"
            type="button"
            class="frame-card"
            @click="previewVideoFrame(frame)"
          >
            <img
              :src="getVideoFrameImage(frame)"
              :alt="`帧 ${frame.frame_index ?? index + 1}`"
            />

            <span class="frame-info">
              <span>{{ frame.timestamp ?? 0 }}s</span>
              <span>{{ frame.object_count ?? frame.detections?.length ?? 0 }} 个目标</span>
            </span>
          </button>
        </div>
      </div>

      <div v-else class="video-output-missing">
        检测任务已经完成，但后端暂未返回标注视频或可预览的关键帧。
      </div>

      <div class="result-stats">
        <div class="stat-item">
          <span class="stat-label">推理耗时</span>
          <span class="stat-value">{{ inferenceTime }}</span>
        </div>
        <div class="stat-item">
          <span class="stat-label">检测目标</span>
          <span class="stat-value">{{ totalObjects }} 个</span>
        </div>

        <el-table
          v-if="classCountsArray.length"
          :data="classCountsArray"
          size="small"
          class="class-count-table"
        >
          <el-table-column prop="className" label="类别" />
          <el-table-column prop="count" label="数量" width="80" />
        </el-table>
      </div>
    </div>

    <!-- 批量检测：逐张展示后端返回的标注图片 -->
    <div v-if="isBatchResult && batchImages.length" class="batch-results-section">
      <div class="section-title">逐图检测结果（{{ batchImages.length }}）</div>
      <div class="batch-results-grid">
        <button
          v-for="(image, index) in batchImages"
          :key="`${image.name}-${index}`"
          type="button"
          class="batch-result-card"
          @click="previewBatchImage(image)"
        >
          <img :src="image.src" :alt="`${image.name} 检测结果`" />
          <span class="batch-result-info">
            <strong :title="image.name">{{ image.name }}</strong>
            <span>{{ image.objectCount }} 个目标</span>
            <span v-if="image.inferenceTime !== null">{{ image.inferenceTime }} ms</span>
          </span>
        </button>
      </div>
    </div>

    <div v-if="annotatedImage && !isBatchResult" class="diagnosis-image-section">
      <img
        :src="annotatedImage"
        class="diagnosis-image"
        alt="detection result"
      />
    </div>

    <div v-if="description" class="diagnosis-description">
      {{ description }}
    </div>

    <div v-if="classCountItems.length && !isVideoResult" class="class-summary">
      <div class="section-title">类别统计</div>
      <div class="class-tags">
        <span v-for="item in classCountItems" :key="item.name" class="class-tag">
          {{ item.name }} <strong>{{ item.count }}</strong>
        </span>
      </div>
    </div>

    <div v-if="detections.length" class="detection-list">
      <div class="section-title">检测目标（{{ totalObjects }}）</div>
      <div v-for="(detection, index) in detections" :key="index" class="detection-item">
        <div class="detection-main">
          <span class="detection-index">#{{ index + 1 }}</span>
          <span>{{ getDetectionName(detection, index) }}</span>
        </div>
        <span
          v-if="getDetectionConfidence(detection) !== null"
          class="confidence-badge"
          :class="getConfidenceLevel(detection)"
        >
          {{ getDetectionConfidence(detection) }}%
        </span>
      </div>
    </div>

    <details v-if="hasBoundingBoxes" class="technical-details">
      <summary>查看检测框坐标</summary>
      <div v-for="(detection, index) in detections" :key="index" class="bbox-row">
        <span>#{{ index + 1 }} {{ getDetectionName(detection, index) }}</span>
        <code>{{ formatBoundingBox(detection.bbox) }}</code>
      </div>
    </details>

    <div v-if="treatments.length" class="treatment-list">
      <div
        v-for="(treatment, idx) in treatments"
        :key="idx"
        class="treatment-item"
      >
        ✓ {{ treatment }}
      </div>
    </div>

    <div v-if="hasApiResult" class="result-meta">
      <span v-if="resultData.task_uuid">模型任务：{{ resultData.task_uuid }}</span>
      <span v-if="resultData.filename">输入文件：{{ resultData.filename }}</span>
    </div>

    <div
      v-if="previewFrameUrl"
      class="frame-preview-modal"
      role="dialog"
      aria-modal="true"
      :aria-label="previewImageTitle || '检测图片预览'"
      @click.self="closeVideoFramePreview"
    >
      <button type="button" class="preview-close" @click="closeVideoFramePreview">×</button>
      <div class="preview-content">
        <img :src="previewFrameUrl" :alt="previewImageTitle || '检测图片预览'" />
        <div v-if="previewImageTitle" class="preview-title">{{ previewImageTitle }}</div>
      </div>
    </div>

  </div>
</template>

<script setup>
import { computed, ref } from 'vue'

const props = defineProps({
  item: {
    type: Object,
    required: true,
  },
})

const apiResult = computed(() => props.item.detectionResult || null)
const hasApiResult = computed(() => Boolean(apiResult.value))
const resultData = computed(() => apiResult.value?.data || apiResult.value || {})
const isVideoResult = computed(() => resultData.value.type === 'video')
const isCameraResult = computed(() => resultData.value.type === 'camera')
const isBatchResult = computed(() => (
  Array.isArray(resultData.value.annotated_images)
  || resultData.value.total_images > 1
  || resultData.value.source === 'zip'
))

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

const classCountItems = computed(() => {
  const counts = resultData.value.class_counts
  if (counts && typeof counts === 'object') {
    return Object.entries(counts).map(([name, count]) => ({ name, count }))
  }

  const derivedCounts = detections.value.reduce((result, detection, index) => {
    const name = getDetectionName(detection, index)
    result[name] = (result[name] || 0) + 1
    return result
  }, {})
  return Object.entries(derivedCounts).map(([name, count]) => ({ name, count }))
})
const classCountsArray = computed(() => classCountItems.value.map((item) => ({
  className: item.name,
  count: item.count,
})))

const categoryCount = computed(() => classCountItems.value.length)
const inferenceTime = computed(() => (
  (resultData.value.inference_time ?? resultData.value.total_inference_time) != null
    ? `${Number(resultData.value.inference_time ?? resultData.value.total_inference_time).toFixed(1)} ms`
    : '-'
))
const hasBoundingBoxes = computed(() => detections.value.some((item) => Array.isArray(item.bbox)))

const firstDetection = computed(() => detections.value[0] || {})
const diseaseName = computed(() => (
  props.item.disease
  || firstDetection.value.class_name
  || firstDetection.value.disease_name
  || firstDetection.value.label
  || (hasApiResult.value ? `检测完成，共 ${totalObjects.value} 个目标` : '未知病害')
))
const plantName = computed(() => (
  props.item.plant
  || resultData.value.plant
  || resultData.value.crop
  || (hasApiResult.value ? resultData.value.filename : props.item.content)
  || ''
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
  || (resultData.value.annotated_image
    ? `data:image/jpeg;base64,${resultData.value.annotated_image}`
    : '')
  || ''
))
const description = computed(() => props.item.description || (hasApiResult.value ? props.item.content : ''))
const treatments = computed(() => props.item.treatments || resultData.value.treatments || resultData.value.suggestions || [])
const annotatedVideoUrl = computed(() => (
  resultData.value.annotated_video_url
  || resultData.value.result_video_url
  || resultData.value.video_url
  || ''
))
const videoFrames = computed(() => (
  Array.isArray(resultData.value.key_frames)
    ? resultData.value.key_frames
    : Array.isArray(resultData.value.frames)
      ? resultData.value.frames
      : []
))
const previewFrameUrl = ref('')
const previewImageTitle = ref('')

const getBaseName = (path = '') => String(path).split(/[\\/]/).pop() || ''

const getAnnotatedImageSource = (image = {}) => {
  const source = image.annotated_image_url
    || image.result_image_url
    || image.image_url
    || image.annotated_image_base64
    || image.annotated_image
    || image.image_base64
    || ''

  if (!source || source.startsWith('data:') || source.startsWith('http') || source.startsWith('/')) {
    return source
  }

  return `data:image/jpeg;base64,${source}`
}

const batchImages = computed(() => {
  const images = Array.isArray(resultData.value.annotated_images)
    ? resultData.value.annotated_images
    : []

  return images.map((image, index) => {
    const backendName = image.image_path || image.filename || image.file_name || ''
    const name = image.original_filename || backendName || `图片 ${index + 1}`
    const imageDetections = detections.value.filter((detection) => {
      const detectionName = detection.image_path || detection.filename || detection.file_name || ''
      return getBaseName(detectionName) === getBaseName(backendName)
    })
    const perImageInference = image.inference_time
      ?? imageDetections[0]?.inference_time
      ?? null

    return {
      name: getBaseName(name) || `图片 ${index + 1}`,
      src: getAnnotatedImageSource(image),
      objectCount: image.object_count ?? image.total_objects ?? imageDetections.length,
      inferenceTime: perImageInference == null ? null : Number(perImageInference).toFixed(1),
    }
  }).filter((image) => image.src)
})

const getVideoFrameImage = (frame) => {
  const source = frame.annotated_image_base64
    || frame.image_base64
    || frame.annotated_image_url
    || frame.image_url
    || ''

  if (!source || source.startsWith('data:') || source.startsWith('http') || source.startsWith('/')) {
    return source
  }

  return `data:image/jpeg;base64,${source}`
}

const thumbnailFrames = computed(() => (
  videoFrames.value.filter((frame) => Boolean(getVideoFrameImage(frame))).slice(0, 12)
))
const videoResolution = computed(() => {
  const resolution = resultData.value.video_resolution
  if (!resolution || resolution.width == null || resolution.height == null) return ''
  return `${resolution.width} × ${resolution.height}`
})

const previewVideoFrame = (frame) => {
  previewFrameUrl.value = getVideoFrameImage(frame)
  previewImageTitle.value = `关键帧 ${frame.frame_index ?? ''}`.trim()
}

const previewBatchImage = (image) => {
  previewFrameUrl.value = image.src
  previewImageTitle.value = image.name
}

const closeVideoFramePreview = () => {
  previewFrameUrl.value = ''
  previewImageTitle.value = ''
}

const getDetectionName = (detection, index) => (
  detection.class_name
  || detection.disease_name
  || detection.label
  || detection.name
  || detection.filename
  || `目标 ${index + 1}`
)

const getDetectionConfidence = (detection) => toPercent(detection.confidence ?? detection.conf)

const getConfidenceLevel = (detection) => {
  const value = getDetectionConfidence(detection)
  if (value >= 90) return 'high'
  if (value >= 70) return 'medium'
  return 'low'
}

const formatBoundingBox = (bbox) => (
  Array.isArray(bbox)
    ? `[${bbox.map((value) => Number(value).toFixed(0)).join(', ')}]`
    : '-'
)
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

.result-summary {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(90px, 1fr));
  gap: 10px;
  margin-bottom: 18px;
}

.summary-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
  padding: 12px 8px;
  border: 1px solid #dcfce7;
  border-radius: 12px;
  background: #f0fdf4;
}

.summary-item strong {
  color: #166534;
  font-size: 18px;
}

.summary-item span {
  color: #6b7280;
  font-size: 12px;
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

.class-summary {
  margin-bottom: 18px;
}

.class-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.class-tag {
  padding: 7px 10px;
  border: 1px solid #d1fae5;
  border-radius: 999px;
  background: #ecfdf5;
  color: #166534;
  font-size: 13px;
}

.class-tag strong {
  margin-left: 5px;
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

.detection-main {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
}

.detection-index {
  color: #9ca3af;
  font-size: 12px;
}

.confidence-badge {
  flex-shrink: 0;
  padding: 4px 8px;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 700;
}

.confidence-badge.high {
  background: #dcfce7;
  color: #15803d;
}

.confidence-badge.medium {
  background: #fef3c7;
  color: #b45309;
}

.confidence-badge.low {
  background: #fee2e2;
  color: #b91c1c;
}

.technical-details {
  margin-bottom: 18px;
  border: 1px solid #e5e7eb;
  border-radius: 12px;
  overflow: hidden;
}

.technical-details summary {
  padding: 11px 12px;
  background: #f9fafb;
  color: #4b5563;
  cursor: pointer;
  font-size: 13px;
  font-weight: 600;
}

.bbox-row {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  padding: 9px 12px;
  border-top: 1px solid #f3f4f6;
  color: #6b7280;
  font-size: 12px;
}

.bbox-row code {
  color: #374151;
  white-space: nowrap;
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

.batch-results-section {
  margin-bottom: 18px;
}

.batch-results-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
  max-height: 520px;
  overflow-y: auto;
  padding-right: 3px;
}

.batch-result-card {
  overflow: hidden;
  padding: 0;
  border: 1px solid #e5e7eb;
  border-radius: 12px;
  background: white;
  cursor: pointer;
  text-align: left;
  transition: border-color 0.2s ease, transform 0.2s ease;
}

.batch-result-card:hover {
  border-color: #86efac;
  transform: translateY(-1px);
}

.batch-result-card img {
  display: block;
  width: 100%;
  height: 150px;
  object-fit: contain;
  background: #f9fafb;
}

.batch-result-info {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 3px 8px;
  padding: 9px 10px;
  color: #6b7280;
  font-size: 11px;
}

.batch-result-info strong {
  grid-column: 1 / -1;
  overflow: hidden;
  color: #374151;
  font-size: 12px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.video-result {
  margin-bottom: 18px;
}

.camera-summary {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin: -4px 0 18px;
}

.video-info {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 14px;
}

.video-player {
  overflow: hidden;
  margin-bottom: 16px;
  border: 1px solid #e5e7eb;
  border-radius: 14px;
  background: #111827;
}

.video-player video {
  display: block;
  width: 100%;
  max-height: 420px;
}

.fallback-hint {
  margin: 0 0 10px;
  color: #92400e;
  font-size: 13px;
  line-height: 1.5;
}

.video-output-missing {
  margin-bottom: 16px;
  padding: 12px 14px;
  border: 1px solid #fde68a;
  border-radius: 10px;
  background: #fffbeb;
  color: #92400e;
  font-size: 13px;
  line-height: 1.6;
}

.frames-container {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 8px;
  margin-bottom: 16px;
}

.frame-card {
  overflow: hidden;
  padding: 0;
  border: 1px solid #e5e7eb;
  border-radius: 10px;
  background: white;
  cursor: pointer;
  text-align: left;
}

.frame-card img {
  display: block;
  width: 100%;
  height: 92px;
  object-fit: cover;
}

.frame-info {
  display: flex;
  justify-content: space-between;
  gap: 4px;
  padding: 6px;
  color: #6b7280;
  font-size: 10px;
}

.result-stats {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
}

.stat-item {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 11px 12px;
  border: 1px solid #dcfce7;
  border-radius: 10px;
  background: #f0fdf4;
}

.stat-label {
  color: #6b7280;
  font-size: 12px;
}

.stat-value {
  color: #166534;
  font-weight: 700;
}

.class-count-table {
  grid-column: 1 / -1;
  margin-top: 2px;
}

.frame-preview-modal {
  position: fixed;
  inset: 0;
  z-index: 1000;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 28px;
  background: rgba(17, 24, 39, 0.82);
}

.preview-content {
  max-width: min(100%, 1100px);
  max-height: 94vh;
}

.frame-preview-modal img {
  display: block;
  max-width: min(100%, 1100px);
  max-height: 86vh;
  border-radius: 12px;
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.35);
}

.preview-title {
  margin-top: 10px;
  color: white;
  text-align: center;
  word-break: break-all;
}

.preview-close {
  position: fixed;
  top: 20px;
  right: 24px;
  width: 42px;
  height: 42px;
  border: none;
  border-radius: 50%;
  background: white;
  color: #111827;
  cursor: pointer;
  font-size: 26px;
}

.result-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 6px 16px;
  margin-top: 18px;
  padding-top: 14px;
  border-top: 1px solid #e5e7eb;
  color: #9ca3af;
  font-size: 12px;
}

@media (max-width: 520px) {
  .diagnosis-card {
    padding: 16px;
  }

  .bbox-row {
    flex-direction: column;
    gap: 4px;
  }

  .frames-container {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .batch-results-grid {
    grid-template-columns: 1fr;
    max-height: 560px;
  }

  .batch-result-card img {
    height: 190px;
  }

  .frame-card img {
    height: 82px;
  }
}
</style>
