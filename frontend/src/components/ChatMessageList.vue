<template>
  <div class="messages">
    <div v-if="messages.length === 0" class="welcome-panel">
      <div class="welcome-icon">🌿</div>

      <h1>Plant Disease Diagnosis</h1>

      <p class="welcome-desc">
        Upload a photo, batch images, a video or use the camera<br>
        to get instant AI diagnosis and treatment recommendations.
      </p>

      <div class="suggestions-grid">
        <div
          class="suggestion-card"
          @click="$emit('use-suggestion', 'What disease is affecting my tomato leaf?')"
        >
          What disease is affecting my tomato leaf?
        </div>

        <div
          class="suggestion-card"
          @click="$emit('use-suggestion', 'How to treat grape black rot?')"
        >
          How to treat grape black rot?
        </div>

        <div
          class="suggestion-card"
          @click="$emit('use-suggestion', 'Why are my pepper leaves turning yellow?')"
        >
          Why are my pepper leaves turning yellow?
        </div>

        <div
          class="suggestion-card"
          @click="$emit('use-suggestion', 'Identify disease in my strawberry plant.')"
        >
          Identify disease in my strawberry plant.
        </div>
      </div>

      <button class="upload-btn" @click="$emit('open-upload', 'image')">
        📷 Upload plant image
      </button>
    </div>

    <div v-else class="chat-messages">
      <div
        v-for="(item, index) in messages"
        :key="index"
        :class="['message-row', item.role]"
      >
        <div class="message-avatar">
          {{ item.role === 'assistant' ? '🌿' : 'You' }}
        </div>

        <div v-if="item.type === 'image'" class="image-message">
          <img :src="item.imageUrl" class="chat-image" alt="uploaded image" />
        </div>

        <div v-else-if="item.type === 'video'" class="video-message">
          <video :src="item.videoUrl" class="chat-video" controls playsinline />
        </div>

        <DiagnosisCard
          v-else-if="item.type === 'diagnosis'"
          :item="item"
        />

        <div v-else class="message-bubble">
          {{ item.content }}
        </div>
      </div>
      <div ref="messageEndRef" class="message-end-anchor"></div>
    </div>
  </div>
</template>

<script setup>
import DiagnosisCard from '@/components/DiagnosisCard.vue'
import { ref } from 'vue'

const props = defineProps({
  messages: {
    type: Array,
    default: () => [],
  },
})

defineEmits(['use-suggestion', 'open-upload'])

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
  padding: 40px;
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

.upload-btn {
  border: 1px solid #16a34a;
  color: #16a34a;
  background: white;
  border-radius: 14px;
  padding: 14px 24px;
  font-size: 16px;
  cursor: pointer;
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
</style>
