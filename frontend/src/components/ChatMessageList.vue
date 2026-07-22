<template>
  <div class="messages">
    <div v-if="messages.length === 0" class="welcome-panel">
      <div class="welcome-icon">🌿</div>

      <h1>{{ tr('chat.welcomeTitle') }}</h1>

      <p class="welcome-desc">
        {{ tr('chat.welcomeDesc') }}
      </p>

      <div class="suggestions-grid">
        <div
          class="suggestion-card"
          @click="$emit('use-suggestion', tr('chat.suggestion1'))"
        >
          {{ tr('chat.suggestion1') }}
        </div>

        <div
          class="suggestion-card"
          @click="$emit('use-suggestion', tr('chat.suggestion2'))"
        >
          {{ tr('chat.suggestion2') }}
        </div>

        <div
          class="suggestion-card"
          @click="$emit('use-suggestion', tr('chat.suggestion3'))"
        >
          {{ tr('chat.suggestion3') }}
        </div>

        <div
          class="suggestion-card"
          @click="$emit('use-suggestion', tr('chat.suggestion4'))"
        >
          {{ tr('chat.suggestion4') }}
        </div>
      </div>

    </div>

    <div v-else class="chat-messages">
      <div
        v-for="(item, index) in messages"
        :key="index"
        :class="['message-row', item.role]"
      >
        <div class="message-avatar">
          {{ item.role === 'assistant' ? '🌿' : tr('chat.you') }}
        </div>

        <div v-if="item.type === 'image' || item.imagePreview" class="image-message">
          <img :src="item.imageUrl || item.imagePreview" class="chat-image" alt="uploaded image" />
          <div v-if="item.content" class="media-caption">{{ item.content }}</div>
        </div>

        <div v-else-if="item.images?.length" class="image-message batch-message">
          <div class="batch-grid">
            <img
              v-for="(image, imageIndex) in item.images"
              :key="imageIndex"
              :src="image"
              class="chat-image"
              alt="batch upload preview"
            />
          </div>
          <div class="media-caption">{{ item.content }}</div>
        </div>

        <div v-else-if="item.type === 'video'" class="video-message">
          <video :src="item.videoUrl" class="chat-video" controls playsinline />
          <div v-if="item.content" class="media-caption">{{ item.content }}</div>
        </div>

        <RealtimeDetectionCard
          v-else-if="item.type === 'realtime-detection'"
          :item="item"
          @finished="$emit('realtime-finished', { item, result: $event })"
        />

        <HealthyResult
          v-else-if="isHealthyImageResult(item)"
          @redetect="$emit('redetect-single')"
        />

        <div
          v-else-if="item.type === 'agent-analysis'"
          class="result-stack"
        >
          <AgentResultCard :item="item" />
          <SeverityAssessmentPanel :result="getDetectionResult(item)" />
        </div>

        <VideoDetectionProgressCard
          v-else-if="item.type === 'video-progress'"
          :item="item"
        />

        <div v-else-if="isBatchDetection(item)" class="result-stack">
          <DetectionResultCard :result="getDetectionResult(item)" />
          <SeverityAssessmentPanel :result="getDetectionResult(item)" />
        </div>

        <div v-else-if="item.type === 'diagnosis' || item.detectionResult" class="result-stack">
          <DiagnosisCard :item="item" />
          <SeverityAssessmentPanel :result="getDetectionResult(item)" />
        </div>

        <div
          v-else
          class="message-bubble"
          :class="{ loading: item.loading && !item.content, error: item.error }"
        >
          <span v-if="item.loading && !item.content" class="loading-dot" />
          <MarkdownMessage
            v-if="item.role === 'assistant' && !item.error && item.content"
            :content="item.content"
          />
          <span v-else>{{ item.content }}</span>
          <span v-if="item.loading && item.content" class="stream-cursor" />
        </div>
      </div>
      <div ref="messageEndRef" class="message-end-anchor"></div>
    </div>
  </div>
</template>

<script setup>
import AgentResultCard from '@/components/AgentResultCard.vue'
import DetectionResultCard from '@/components/DetectionResultCard.vue'
import DiagnosisCard from '@/components/DiagnosisCard.vue'
import HealthyResult from '@/components/HealthyResult.vue'
import MarkdownMessage from '@/components/MarkdownMessage.vue'
import RealtimeDetectionCard from '@/components/RealtimeDetectionCard.vue'
import SeverityAssessmentPanel from '@/components/SeverityAssessmentPanel.vue'
import VideoDetectionProgressCard from '@/components/VideoDetectionProgressCard.vue'
import { useLocaleStore } from '@/stores/locale'
import { t } from '@/utils/i18n'
import { ref } from 'vue'

const localeStore = useLocaleStore()
const tr = (key, params) => t(key, localeStore.locale, params)

const props = defineProps({
  messages: {
    type: Array,
    default: () => [],
  },
})

defineEmits(['use-suggestion', 'realtime-finished', 'redetect-single'])

const getDetectionResult = (item) => item.detectionResult?.data || item.detectionResult || {}

const isHealthyImageResult = (item) => {
  if (item.loading || item.error || !item.detectionResult) return false

  const result = getDetectionResult(item)

  // 视频、实时摄像头不使用这个静态图片结果卡片
  if (result.type === 'video' || result.type === 'camera') return false

  // 批量检测继续使用原来的批量结果卡片
  if (
    result.source === 'zip'
    || Number(result.total_images || 0) > 1
    || Array.isArray(result.annotated_images)
  ) {
    return false
  }

  const totalObjects = Number(
    result.total_objects
      ?? result.detections?.length
      ?? -1,
  )

  return totalObjects === 0
}

const isBatchDetection = (item) => (
  Array.isArray(getDetectionResult(item).annotated_images)
  && getDetectionResult(item).annotated_images.length > 0
)

const messageEndRef = ref(null)

const scrollToBottom = () => {
  messageEndRef.value?.scrollIntoView({
    behavior: 'smooth',
    block: 'end',
  })
}

defineExpose({ scrollToBottom })
</script>

<style scoped>
.messages {
  flex: 1;
  overflow-y: auto;
  overflow-x: hidden;
  padding: 40px 40px 170px;
}

.welcome-panel {
  width: 100%;
  max-width: 820px;
  min-height: 100%;
  margin: auto;
  text-align: center;
  display: flex;
  flex-direction: column;
  justify-content: center;
}

.welcome-icon {
  font-size: 72px;
  margin-bottom: 20px;
}

.welcome-panel h1 {
  font-size: 42px;
  margin-bottom: 16px;
  color: #1f2937;
}

.welcome-desc {
  color: #6b7280;
  font-size: 18px;
  line-height: 1.7;
  margin-bottom: 36px;
}

.suggestions-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 16px;
  margin-bottom: 32px;
}

.suggestion-card {
  background: white;
  border: 1px solid #e5e7eb;
  border-radius: 16px;
  padding: 18px;
  text-align: left;
  cursor: pointer;
  transition: all 0.2s ease;
}

.suggestion-card:hover {
  transform: translateY(-2px);
  border-color: #16a34a;
}

.chat-messages {
  width: 100%;
  max-width: 900px;
  margin: 0 auto;
  display: flex;
  flex-direction: column;
  gap: 24px;
  padding-bottom: 40px;
}

.message-end-anchor {
  width: 100%;
  height: 1px;
  flex-shrink: 0;
}

.message-row {
  display: flex;
  align-items: flex-start;
  gap: 12px;
}

.message-row.user {
  flex-direction: row-reverse;
}

.result-stack {
  display: flex;
  width: min(100%, 700px);
  min-width: 0;
  flex-direction: column;
  align-items: flex-start;
  gap: 12px;
}

.message-avatar {
  width: 42px;
  height: 42px;
  flex-shrink: 0;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #ecfdf5;
  color: #15803d;
  font-size: 13px;
  font-weight: 700;
}

.message-row.user .message-avatar {
  background: #f3f4f6;
  color: #374151;
}

.message-bubble {
  max-width: 70%;
  padding: 14px 18px;
  border: 1px solid #e5e7eb;
  border-radius: 18px;
  background: white;
  color: #374151;
  line-height: 1.6;
  box-shadow: 0 2px 10px rgba(0, 0, 0, 0.04);
}

.message-row.user .message-bubble {
  background: #16a34a;
  border-color: #16a34a;
  color: white;
}

.message-row.assistant .message-bubble {
  max-width: min(82%, 760px);
}

.message-bubble.loading {
  display: flex;
  align-items: center;
  gap: 9px;
}

.message-bubble.error {
  border-color: #fecaca;
  background: #fef2f2;
  color: #b91c1c;
}

.loading-dot {
  width: 9px;
  height: 9px;
  border-radius: 50%;
  background: #16a34a;
  animation: pulse 1s infinite alternate;
}

.stream-cursor {
  display: inline-block;
  width: 7px;
  height: 15px;
  margin-left: 4px;
  vertical-align: -2px;
  border-radius: 2px;
  background: #16a34a;
  animation: pulse 0.8s infinite alternate;
}

@keyframes pulse {
  to { opacity: 0.25; transform: scale(0.75); }
}

.image-message,
.video-message {
  max-width: 420px;
  padding: 8px;
  background: white;
  border-radius: 18px;
  border: 1px solid #e5e7eb;
  box-shadow: 0 2px 10px rgba(0, 0, 0, 0.04);
}

.chat-image,
.chat-video {
  width: 100%;
  border-radius: 16px;
  border: 1px solid #e5e7eb;
}

.chat-video {
  max-height: 280px;
  object-fit: cover;
}

.media-caption {
  padding: 8px 6px 2px;
  color: #4b5563;
  font-size: 13px;
}

.batch-message {
  max-width: 500px;
}

.batch-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 6px;
}

.batch-grid .chat-image {
  height: 110px;
  object-fit: cover;
}

@media (max-width: 640px) {
  .messages {
    padding: 18px 12px 126px;
  }

  .welcome-panel {
    justify-content: flex-start;
    padding-top: 9vh;
  }

  .welcome-icon {
    margin-bottom: 12px;
    font-size: 50px;
  }

  .welcome-panel h1 {
    margin-bottom: 10px;
    font-size: 27px;
  }

  .welcome-desc {
    margin-bottom: 22px;
    font-size: 14px;
    line-height: 1.6;
  }

  .suggestions-grid {
    grid-template-columns: 1fr;
    gap: 9px;
  }

  .suggestion-card {
    padding: 13px 14px;
    border-radius: 13px;
  }

  .chat-messages {
    gap: 18px;
  }

  .message-row {
    gap: 8px;
  }

  .message-avatar {
    width: 34px;
    height: 34px;
    font-size: 11px;
  }

  .message-bubble {
    max-width: calc(100% - 44px);
    padding: 11px 13px;
    border-radius: 15px;
    font-size: 14px;
  }

  .result-stack,
  .image-message,
  .video-message,
  .batch-message {
    max-width: calc(100% - 42px);
  }

  .batch-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .batch-grid .chat-image {
    height: 96px;
  }
}
</style>
