<template>
  <article class="agent-result-card" :class="{ 'has-error': item.error }">
    <header class="agent-header">
      <div>
        <div class="agent-label">
          <span class="agent-icon">✦</span>
          {{ tr('agent.title') }}
        </div>

      </div>
      <span class="agent-badge">Agent</span>
    </header>

    <div v-if="item.agentPrompt" class="prompt-row">
      <span>{{ tr('agent.question') }}</span>
      <p>{{ item.agentPrompt }}</p>
    </div>

    <div v-if="item.loading && !hasResult" class="agent-progress">
      <span class="loading-dot" />
      <div>
        <strong>{{ tr('agent.analyzing') }}</strong>
        <p>{{ tr('agent.analyzingDesc') }}</p>
      </div>
    </div>

    <section v-if="hasResult" class="detection-section">
      <div class="section-heading">
        <div>
          <span class="section-kicker">{{ tr('result.yolo') }}</span>
          <h4>{{ detectedCategories }}</h4>
        </div>
        <span class="tool-badge">Detection</span>
      </div>

      <div class="result-summary">
        <div class="summary-item">
          <strong>{{ totalObjects }}</strong>
          <span>{{ tr('result.targetCount') }}</span>
        </div>
        <div class="summary-item">
          <strong>{{ classCountItems.length }}</strong>
          <span>{{ tr('agent.diseaseClasses') }}</span>
        </div>
        <div class="summary-item">
          <strong>{{ inferenceTime }}</strong>
          <span>{{ tr('result.inferenceTime') }}</span>
        </div>
      </div>

      <button
        v-if="annotatedImage"
        type="button"
        class="annotated-image-button"
        @click="openPreview(annotatedImage)"
      >
        <img :src="annotatedImage" alt="YOLO 标注结果" />
        <span>{{ tr('agent.viewImage') }}</span>
      </button>

      <div v-if="batchImages.length" class="batch-grid">
        <button
          v-for="(image, index) in batchImages"
          :key="`${image.name}-${index}`"
          type="button"
          class="batch-image-button"
          @click="openPreview(image.src)"
        >
          <img :src="image.src" :alt="image.name" />
          <span :title="image.name">{{ image.name }}</span>
        </button>
      </div>

      <div class="targets-section">
        <div class="targets-title">
          <strong>{{ tr('result.targetCount') }}</strong>
          <span>{{ tr('result.targetsWithCount', { count: totalObjects }) }}</span>
        </div>

        <div v-if="detections.length" class="target-list">
          <div v-for="(detection, index) in detections" :key="index" class="target-row">
            <div class="target-name">
              <span class="target-index">{{ index + 1 }}</span>
              <strong>{{ getDetectionName(detection) }}</strong>
            </div>
            <span v-if="getDetectionConfidence(detection) !== null" class="confidence-pill">
              {{ tr('agent.confidence', { value: getDetectionConfidence(detection) }) }}
            </span>
          </div>
        </div>

        <div v-else-if="classCountItems.length" class="class-tags">
          <span v-for="entry in classCountItems" :key="entry.name" class="class-tag">
            {{ entry.name }} <strong>{{ entry.count }}</strong>
          </span>
        </div>

        <p v-else class="empty-targets">{{ tr('agent.noTargets') }}</p>
      </div>
    </section>

    <!-- LLM 解读固定放在检测目标之后，避免与原始检测数据混在一起。 -->
    <section v-if="displayContent && !item.error" class="analysis-section">
      <div class="analysis-title">
        <span class="analysis-icon">AI</span>
        <div>
          <strong>{{ tr('agent.analysis') }}</strong>
          <p>{{ tr('agent.analysisDesc') }}</p>
        </div>
      </div>

      <div class="formatted-answer">
        <template v-for="(block, index) in contentBlocks" :key="index">
          <h5 v-if="block.type === 'heading'">{{ block.text }}</h5>
          <ul v-else-if="block.type === 'list'">
            <li v-for="(line, lineIndex) in block.items" :key="lineIndex">{{ line }}</li>
          </ul>
          <ol v-else-if="block.type === 'ordered-list'">
            <li v-for="(line, lineIndex) in block.items" :key="lineIndex">{{ line }}</li>
          </ol>
          <p v-else>{{ block.text }}</p>
        </template>
        <span v-if="item.loading" class="stream-cursor" />
      </div>
    </section>

    <div v-if="resultData.error" class="model-error">
      检测模型返回错误：{{ resultData.error }}
    </div>

    <div v-if="item.error" class="request-error">
      {{ item.content || 'Agent 分析失败，请稍后重试。' }}
    </div>

    <footer class="agent-footer">
      <span>LLM 理解</span>
      <i>→</i>
      <span>YOLO 检测</span>
      <i>→</i>
      <span>LLM 解读</span>
    </footer>

    <el-dialog v-model="showPreview" title="Agent 检测标注图" width="80%">
      <img v-if="previewSrc" :src="previewSrc" class="preview-image" alt="Agent 检测标注图" />
    </el-dialog>
  </article>
</template>

<script setup>
import { computed, ref } from 'vue'
import { useLocaleStore } from '@/stores/locale'
import { t } from '@/utils/i18n'

const localeStore = useLocaleStore()
const tr = (key, params) => t(key, localeStore.locale, params)

const props = defineProps({
  item: {
    type: Object,
    required: true,
  },
})

const showPreview = ref(false)
const previewSrc = ref('')

const resultData = computed(() => props.item.detectionResult?.data || props.item.detectionResult || {})
const hasResult = computed(() => Object.keys(resultData.value).length > 0 && !resultData.value.error)
const detections = computed(() => (
  Array.isArray(resultData.value.detections) ? resultData.value.detections : []
))

const getDetectionName = (detection) => (
  detection.class_name_display || detection.class_name_cn || detection.class_name || detection.disease_name || detection.label || detection.name || '未知类别'
)

const getDetectionConfidence = (detection) => {
  const number = Number(detection.confidence ?? detection.conf)
  if (!Number.isFinite(number)) return null
  return Math.round((number <= 1 ? number * 100 : number) * 10) / 10
}

const classCountItems = computed(() => {
  const counts = resultData.value.class_counts_display || resultData.value.class_counts
  if (counts && typeof counts === 'object') {
    return Object.entries(counts).map(([name, count]) => ({ name, count }))
  }

  const derived = detections.value.reduce((result, detection) => {
    const name = getDetectionName(detection)
    result[name] = (result[name] || 0) + 1
    return result
  }, {})
  return Object.entries(derived).map(([name, count]) => ({ name, count }))
})

const totalObjects = computed(() => resultData.value.total_objects ?? detections.value.length)
const detectedCategories = computed(() => (
  classCountItems.value.length
    ? classCountItems.value.map((entry) => entry.name).join('、')
    : totalObjects.value > 0 ? '目标类别待确认' : '未检测到病害目标'
))
const resultTitle = computed(() => {
  if (hasResult.value) return `检测结果：${detectedCategories.value}`
  return props.item.loading ? '正在生成分析结果' : 'Agent 分析结果'
})
const inferenceTime = computed(() => {
  const value = resultData.value.inference_time ?? resultData.value.total_inference_time
  return value == null ? '-' : `${Number(value).toFixed(1)} ms`
})

const toImageSource = (url, base64) => {
  if (url) return String(url)
  if (!base64) return ''
  const source = String(base64).trim()
  return source.startsWith('data:') ? source : `data:image/jpeg;base64,${source}`
}

const annotatedImage = computed(() => toImageSource(
  resultData.value.annotated_image_url || resultData.value.result_image_url,
  resultData.value.annotated_image_base64 || resultData.value.annotated_image,
))

const batchImages = computed(() => {
  const images = resultData.value.annotated_images
  if (!Array.isArray(images)) return []
  return images.map((image) => ({
    name: image.original_filename || image.image_path || image.filename || 'image',
    src: toImageSource(
      image.annotated_image_url || image.result_image_url,
      image.annotated_image_base64 || image.annotated_image,
    ),
  })).filter((image) => image.src)
})

const cleanInlineMarkdown = (text) => text
  .replace(/\*\*(.*?)\*\*/g, '$1')
  .replace(/__(.*?)__/g, '$1')
  .replace(/`([^`]+)`/g, '$1')
  .trim()

/**
 * YOLO 结果已由上方检测卡片展示。过滤大模型重复生成的检测统计表格和标注图链接，
 * 仅保留病害解读、风险说明与处理建议；历史会话中的旧回复同样适用。
 */
const displayContent = computed(() => String(props.item.content || '')
  .replace(/\r/g, '')
  .replace(
    /(?:^|\n)\s*(?:#{1,6}\s*)?📋\s*检测结果\s*\n[\s\S]*?(?:\n\s*---+\s*(?=\n|$)|$)/g,
    '\n',
  )
  .replace(
    /(?:^|\n)\s*(?:#{1,6}\s*)?📋\s*Detection Results?\s*\n[\s\S]*?(?:\n\s*---+\s*(?=\n|$)|$)/gi,
    '\n',
  )
  .trim())

/** 将常见 Markdown 风格回复整理为标题、段落和列表，不使用 v-html。 */
const contentBlocks = computed(() => {
  const lines = displayContent.value.split('\n')
  const blocks = []
  let paragraph = []
  let list = null

  const flushParagraph = () => {
    if (!paragraph.length) return
    blocks.push({ type: 'paragraph', text: cleanInlineMarkdown(paragraph.join(' ')) })
    paragraph = []
  }
  const flushList = () => {
    if (!list) return
    blocks.push(list)
    list = null
  }

  lines.forEach((rawLine) => {
    const line = rawLine.trim()
    if (!line) {
      flushParagraph()
      flushList()
      return
    }

    const heading = line.match(/^#{1,6}\s+(.+)$/)
    const unordered = line.match(/^[-*•]\s+(.+)$/)
    const ordered = line.match(/^\d+[.)、]\s*(.+)$/)

    if (heading) {
      flushParagraph()
      flushList()
      blocks.push({ type: 'heading', text: cleanInlineMarkdown(heading[1]) })
    } else if (unordered || ordered) {
      flushParagraph()
      const type = unordered ? 'list' : 'ordered-list'
      if (!list || list.type !== type) {
        flushList()
        list = { type, items: [] }
      }
      list.items.push(cleanInlineMarkdown((unordered || ordered)[1]))
    } else {
      flushList()
      paragraph.push(line)
    }
  })

  flushParagraph()
  flushList()
  return blocks
})

const openPreview = (src) => {
  previewSrc.value = src
  showPreview.value = true
}
</script>

<style scoped>
.agent-result-card {
  width: 100%;
  max-width: 640px;
  padding: 20px;
  border: 1px solid #ddd6fe;
  border-radius: 20px;
  background: linear-gradient(145deg, #fff 0%, #faf8ff 100%);
  box-shadow: 0 8px 24px rgba(91, 33, 182, 0.08);
}

.agent-result-card.has-error { border-color: #fecaca; }
.agent-header, .section-heading, .targets-title { display: flex; justify-content: space-between; gap: 16px; }
.agent-header { margin-bottom: 16px; }
.agent-label { display: flex; align-items: center; gap: 6px; color: #6d28d9; font-size: 13px; font-weight: 700; }
.agent-icon { font-size: 17px; }
.agent-header h3 { margin: 5px 0; color: #1f2937; font-size: 19px; }
.agent-header p, .agent-progress p { margin: 0; color: #6b7280; font-size: 13px; }
.agent-badge, .tool-badge { height: fit-content; padding: 7px 12px; border-radius: 999px; font-size: 12px; font-weight: 700; }
.agent-badge { background: #ede9fe; color: #6d28d9; }
.tool-badge { background: #dcfce7; color: #166534; }

.prompt-row { padding: 11px 13px; border: 1px solid #ede9fe; border-radius: 12px; background: #f5f3ff; }
.prompt-row span, .section-kicker { color: #7c3aed; font-size: 12px; font-weight: 700; }
.prompt-row p { margin: 5px 0 0; color: #374151; line-height: 1.6; }

.agent-progress { display: flex; align-items: center; gap: 12px; margin-top: 14px; padding: 14px; border-radius: 14px; background: #f5f3ff; }
.loading-dot { width: 12px; height: 12px; flex-shrink: 0; border-radius: 50%; background: #8b5cf6; animation: pulse 1.2s infinite ease-in-out; }

.detection-section { margin-top: 14px; padding: 15px; border: 1px solid #d1fae5; border-radius: 15px; background: #fcfffd; }
.section-heading h4 { margin: 5px 0 0; color: #166534; font-size: 17px; }
.result-summary { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 9px; margin-top: 14px; }
.summary-item { display: flex; flex-direction: column; align-items: center; gap: 4px; padding: 10px 6px; border: 1px solid #dcfce7; border-radius: 11px; background: #f0fdf4; }
.summary-item strong { color: #166534; font-size: 16px; }
.summary-item span { color: #6b7280; font-size: 11px; }

.annotated-image-button, .batch-image-button { border: 0; background: transparent; cursor: pointer; }
.annotated-image-button { width: 100%; margin-top: 14px; padding: 0; }
.annotated-image-button img { display: block; width: 100%; max-height: 340px; object-fit: contain; border: 1px solid #e5e7eb; border-radius: 12px; background: #f9fafb; }
.annotated-image-button span { display: block; margin-top: 5px; color: #9ca3af; font-size: 11px; }
.batch-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(130px, 1fr)); gap: 9px; max-height: 480px; margin-top: 14px; overflow-y: auto; }
.batch-image-button { min-width: 0; padding: 0; }
.batch-image-button img { width: 100%; height: 120px; object-fit: contain; border: 1px solid #e5e7eb; border-radius: 9px; background: #f9fafb; }
.batch-image-button span { display: block; margin-top: 4px; overflow: hidden; color: #6b7280; font-size: 11px; text-overflow: ellipsis; white-space: nowrap; }

.targets-section { margin-top: 16px; }
.targets-title { align-items: center; padding-bottom: 8px; border-bottom: 1px solid #e5e7eb; color: #374151; }
.targets-title span { color: #6b7280; font-size: 12px; }
.target-list { display: flex; flex-direction: column; }
.target-row { display: flex; align-items: center; justify-content: space-between; gap: 12px; padding: 10px 2px; border-bottom: 1px solid #f3f4f6; }
.target-name { display: flex; align-items: center; gap: 9px; min-width: 0; color: #374151; }
.target-index { display: inline-flex; align-items: center; justify-content: center; width: 24px; height: 24px; flex-shrink: 0; border-radius: 50%; background: #ecfdf5; color: #15803d; font-size: 11px; }
.confidence-pill { flex-shrink: 0; padding: 5px 8px; border-radius: 999px; background: #f0fdf4; color: #15803d; font-size: 11px; }
.class-tags { display: flex; flex-wrap: wrap; gap: 7px; padding-top: 11px; }
.class-tag { padding: 6px 9px; border: 1px solid #d1fae5; border-radius: 999px; background: #ecfdf5; color: #166534; font-size: 12px; }
.class-tag strong { margin-left: 4px; }
.empty-targets { margin: 10px 0 0; color: #6b7280; font-size: 13px; }

.analysis-section { margin-top: 14px; padding: 16px; border: 1px solid #ddd6fe; border-radius: 15px; background: #fff; }
.analysis-title { display: flex; align-items: center; gap: 10px; margin-bottom: 12px; }
.analysis-title p { margin: 2px 0 0; color: #9ca3af; font-size: 11px; }
.analysis-icon { display: inline-flex; align-items: center; justify-content: center; width: 32px; height: 32px; border-radius: 10px; background: #ede9fe; color: #6d28d9; font-size: 11px; font-weight: 800; }
.formatted-answer { color: #374151; line-height: 1.75; }
.formatted-answer h5 { margin: 14px 0 5px; color: #4c1d95; font-size: 14px; }
.formatted-answer h5:first-child { margin-top: 0; }
.formatted-answer p { margin: 8px 0; }
.formatted-answer ul, .formatted-answer ol { margin: 8px 0; padding-left: 22px; }
.formatted-answer li { margin: 5px 0; }
.stream-cursor { display: inline-block; width: 7px; height: 15px; margin-left: 4px; vertical-align: -2px; border-radius: 2px; background: #8b5cf6; animation: blink 0.8s infinite; }

.model-error, .request-error { margin-top: 14px; padding: 12px; border-radius: 12px; background: #fef2f2; color: #b91c1c; }
.agent-footer { display: flex; align-items: center; flex-wrap: wrap; gap: 7px; margin-top: 16px; padding-top: 12px; border-top: 1px solid #ede9fe; color: #8b5cf6; font-size: 11px; }
.agent-footer i { color: #c4b5fd; font-style: normal; }
.preview-image { width: 100%; max-height: 75vh; object-fit: contain; }

@keyframes pulse { 0%, 100% { opacity: .35; transform: scale(.85); } 50% { opacity: 1; transform: scale(1); } }
@keyframes blink { 0%, 45% { opacity: 1; } 50%, 100% { opacity: 0; } }

@media (max-width: 640px) {
  .agent-result-card { padding: 16px; }
  .result-summary { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .target-row { align-items: flex-start; flex-direction: column; gap: 6px; }
}
</style>
