<template>
  <div class="detection-result-card diagnosis-style-card">
    <div class="diagnosis-header">
      <div>
        <div class="diagnosis-label">
          <el-icon><DataAnalysis /></el-icon>
          {{ isBatch ? 'YOLO 批量检测结果' : 'YOLO 检测结果' }}
        </div>
        <h3>检测结果：{{ detectedCategoryText }}</h3>
        <p>{{ resultSourceText }}</p>
      </div>
      <div class="batch-badge">{{ isBatch ? 'Batch' : 'Single' }}</div>
    </div>

    <div class="result-summary">
      <div class="summary-item">
        <strong>{{ result.total_objects ?? 0 }}</strong>
        <span>检测目标</span>
      </div>
      <div class="summary-item">
        <strong>{{ classCountsArray.length }}</strong>
        <span>类别数量</span>
      </div>
      <div class="summary-item">
        <strong>{{ result.inference_time || result.total_inference_time || 0 }} ms</strong>
        <span>推理耗时</span>
      </div>
      <div class="summary-item">
        <strong>{{ result.total_images ?? batchImages.length }}</strong>
        <span>图片数量</span>
      </div>
    </div>

    <div class="card-body">
      <!-- 单图模式：标注图 -->
      <div class="result-image" v-if="annotatedImageSrc && !isBatch">
        <img :src="annotatedImageSrc" alt="检测标注图" @click="previewSingleImage" />
      </div>

      <!-- 批量模式：多图展示 -->
      <div v-if="isBatch && batchImages.length > 0" class="batch-result-section">
        <div class="section-title">逐图检测结果（{{ batchImages.length }}）</div>
        <div class="result-images-grid">
          <div v-for="(img, index) in batchImages" :key="`${img.name}-${index}`" class="grid-image" @click="previewImage(img)">
            <img :src="img.src" :alt="img.name" @error="markImageError(img)" />
            <span v-if="img.loadError" class="image-error">标注图加载失败</span>
            <span class="image-name">{{ img.name }}</span>
          </div>
        </div>
      </div>
    </div>

    <div v-if="classCountsArray.length" class="class-summary">
      <div class="section-title">类别统计</div>
      <div class="class-tags">
        <span v-for="item in classCountsArray" :key="item.className" class="class-tag">
          {{ item.className }} <strong>{{ item.count }}</strong>
        </span>
      </div>
    </div>

    <div class="result-meta">
      <span v-if="result.task_id">检测任务：{{ result.task_id }}</span>
      <span v-if="result.source">来源：{{ result.source }}</span>
    </div>

    <!-- 全屏图片预览 -->
    <el-dialog v-model="showFullImage" title="检测标注图" width="80%">
      <img v-if="previewSrc" :src="previewSrc" style="width: 100%" alt="检测标注图" />
    </el-dialog>
  </div>
</template>

<script setup>
/**
 * DetectionResultCard — 检测结果卡片组件
 *
 * 在对话消息中展示检测结果，包含：
 *   - 标注图预览（单图/批量多图，点击可放大）
 *   - 目标总数和推理耗时
 *   - 各类别数量统计表格
 */
import { DataAnalysis } from '@element-plus/icons-vue'
import { computed, ref } from 'vue'

const props = defineProps({
  result: { type: Object, required: true },
})

const showFullImage = ref(false)
const previewSrc = ref(null)

/** 判断是否为批量检测结果 */
const isBatch = computed(() => Array.isArray(props.result.annotated_images) && props.result.annotated_images.length > 0)

const toImageSource = (url, base64) => {
  if (url) return String(url)
  if (!base64) return ''

  const source = String(base64).trim()
  return source.startsWith('data:') ? source : `data:image/jpeg;base64,${source}`
}

/** 单图模式：标注图 URL（优先使用 MinIO URL，否则用 base64） */
const annotatedImageSrc = computed(() => {
  return toImageSource(
    props.result.annotated_image_url || props.result.result_image_url,
    props.result.annotated_image_base64 || props.result.annotated_image,
  ) || null
})

/** 批量模式：标注图列表 */
const batchImages = computed(() => {
  if (!isBatch.value) return []
  return props.result.annotated_images.map((img) => ({
    name: img.original_filename || img.image_path || img.filename || 'image',
    src: toImageSource(
      img.annotated_image_url || img.result_image_url,
      img.annotated_image_base64 || img.annotated_image || img.image_base64,
    ),
    loadError: false,
  }))
})

function previewSingleImage() {
  previewSrc.value = annotatedImageSrc.value
  showFullImage.value = true
}

/** 点击预览图片 */
function previewImage(img) {
  if (!img.src) return
  previewSrc.value = img.src
  showFullImage.value = true
}

function markImageError(img) {
  img.loadError = true
}

/** 类别统计转为数组（用于 el-table） */
const classCountsArray = computed(() => Object.entries(props.result.class_counts || {}).map(([className, count]) => ({ className, count })))

/** 标题直接展示实际检测类别；class_counts 缺失时从检测明细中提取。 */
const detectedCategoryText = computed(() => {
  const categoryNames = classCountsArray.value.map((item) => item.className)

  if (!categoryNames.length && Array.isArray(props.result.detections)) {
    props.result.detections.forEach((detection) => {
      const name = detection.class_name || detection.disease_name || detection.label || detection.name
      if (name && !categoryNames.includes(name)) categoryNames.push(name)
    })
  }

  if (categoryNames.length) return categoryNames.join('、')
  return (props.result.total_objects ?? 0) > 0 ? '目标类别待确认' : '未检测到目标'
})

const resultSourceText = computed(() => {
  if (props.result.source === 'zip') return props.result.zip_filename || 'ZIP 批量检测'
  if (isBatch.value) return '多图片批量检测'
  return props.result.filename || '单图片检测'
})
</script>

<style lang="scss" scoped>
.detection-result-card {
  width: 100%;
  max-width: 620px;
  margin-top: 12px;
  padding: 20px;
  border: 1px solid #e5e7eb;
  border-radius: 20px;
  background: #fff;
  box-shadow: 0 6px 20px rgba(0, 0, 0, 0.06);
}

.diagnosis-header {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 18px;

  h3 {
    margin: 4px 0;
    color: #111827;
  }

  p {
    margin: 0;
    color: #6b7280;
  }
}

.diagnosis-label {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  color: #6b7280;
  font-size: 13px;
}

.batch-badge {
  height: fit-content;
  padding: 8px 14px;
  border-radius: 999px;
  background: #ecfdf5;
  color: #15803d;
  font-size: 13px;
  font-weight: 600;
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

  strong {
    color: #166534;
    font-size: 18px;
  }

  span {
    color: #6b7280;
    font-size: 12px;
  }
}

.card-body {
  margin-bottom: 18px;
}

/* 图片展示规则保持不变 */
.result-image {
  flex: 1;
  min-width: 0;

  img {
    width: 100%;
    max-height: 300px;
    object-fit: contain;
    border-radius: 4px;
    cursor: pointer;
    transition: opacity 0.2s;

    &:hover {
      opacity: 0.8;
    }
  }
}

.batch-result-section {
  min-width: 0;
}

.result-images-grid {
  flex: 1;
  min-width: 0;
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(140px, 1fr));
  gap: 10px;
  max-height: 520px;
  overflow-y: auto;

  .grid-image {
    position: relative;
    min-width: 0;
    text-align: center;
    cursor: pointer;

    img {
      width: 100%;
      height: 130px;
      object-fit: contain;
      background: #f9fafb;
      border: 1px solid #e0e0e0;
      border-radius: 6px;
      transition: opacity 0.2s;

      &:hover {
        opacity: 0.8;
      }
    }

    .image-name {
      display: block;
      margin-top: 4px;
      overflow: hidden;
      color: #606266;
      font-size: 11px;
      text-overflow: ellipsis;
      white-space: nowrap;
    }

    .image-error {
      position: absolute;
      inset: 0 0 20px;
      display: flex;
      align-items: center;
      justify-content: center;
      background: #fef2f2;
      color: #dc2626;
      font-size: 12px;
      pointer-events: none;
    }
  }
}

.section-title {
  margin-bottom: 8px;
  color: #374151;
  font-size: 14px;
  font-weight: 700;
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

  strong {
    margin-left: 5px;
  }
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

@media (max-width: 640px) {
  .detection-result-card {
    padding: 16px;
  }

  .diagnosis-header {
    gap: 10px;
  }
}
</style>
