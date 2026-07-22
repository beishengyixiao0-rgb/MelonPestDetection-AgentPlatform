<template>
  <div class="chat-footer">
    <input
      ref="fileInputRef"
      type="file"
      :accept="inputAccept"
      :multiple="inputMultiple"
      :capture="inputCapture"
      style="display:none"
      @change="handleFileSelection"
    />

    <div class="composer-stack">
    <div v-if="uploadQueue.length" class="upload-panel">
      <div
        v-for="item in uploadQueue"
        :key="item.id"
        class="upload-item"
      >
        <div class="upload-item-main">
          <div class="upload-preview" v-if="item.type === 'image' && item.previewUrl">
            <img :src="item.previewUrl" alt="preview" />
          </div>
          <div class="upload-preview video-preview" v-else>
            <span>{{ item.type === 'video' ? '🎬' : '📷' }}</span>
          </div>

          <div class="upload-info">
            <div class="upload-name">{{ item.name }}</div>
            <div class="upload-meta">
              {{ item.type === 'video' ? tr('composer.video') : tr('composer.image') }} · {{ getModeLabel(item.mode) }}
            </div>
            <div class="upload-progress-track">
              <div class="upload-progress-bar" :style="{ width: item.progress + '%' }" />
            </div>
            <div class="upload-status">
              <span v-if="item.status === 'uploading'">{{ tr('composer.uploading', { progress: item.progress }) }}</span>
              <span
                v-else-if="item.status === 'success' && (item.mode === 'agent-image' || item.mode === 'camera')"
                class="success-text"
              >{{ tr('composer.uploadReady') }}</span>
              <span v-else-if="item.status === 'success'" class="success-text">{{ tr('composer.uploadDone') }}</span>
              <span v-else class="error-text">{{ item.errorMessage || tr('composer.uploadFailed') }}</span>
            </div>
          </div>
        </div>

        <div class="upload-item-actions">
          <button v-if="item.status === 'error'" class="retry-upload" @click="$emit('retry-upload', item.id)">{{ tr('composer.retry') }}</button>
          <button class="upload-remove" @click="$emit('remove-upload-item', item.id)" :aria-label="tr('composer.remove')">×</button>
        </div>
      </div>
    </div>

    <div v-if="showUploadMenu" class="upload-menu">
      <div class="upload-menu-title">{{ tr('composer.addContent') }}</div>
      <button class="upload-option primary" @click="$emit('select-upload-mode', 'agent-image')">
        <span class="option-icon"><Picture /></span>
        <span class="option-copy"><strong>{{ tr('composer.agentImage') }}</strong><small>{{ tr('composer.agentImageDesc') }}</small></span>
      </button>
      <button class="upload-option" @click="$emit('select-upload-mode', 'knowledge')">
        <span class="option-icon"><DocumentAdd /></span>
        <span class="option-copy"><strong>{{ tr('composer.knowledge') }}</strong><small>{{ tr('composer.knowledgeDesc') }}</small></span>
      </button>
      <button class="upload-option" @click="$emit('select-upload-mode', 'image')">
        <span class="option-icon"><Lightning /></span>
        <span class="option-copy"><strong>{{ tr('composer.single') }}</strong><small>{{ tr('composer.singleDesc') }}</small></span>
      </button>
      <button class="upload-option" @click="$emit('select-upload-mode', 'batch')">
        <span class="option-icon"><Files /></span>
        <span class="option-copy"><strong>{{ tr('composer.batch') }}</strong><small>{{ tr('composer.batchDesc') }}</small></span>
      </button>
      <button class="upload-option" @click="$emit('select-upload-mode', 'video')">
        <span class="option-icon"><VideoCamera /></span>
        <span class="option-copy"><strong>{{ tr('composer.video') }}</strong><small>{{ tr('composer.videoDesc') }}</small></span>
      </button>
      <button class="upload-option" @click="$emit('select-upload-mode', 'realtime-camera')">
        <span class="option-icon"><Monitor /></span>
        <span class="option-copy"><strong>{{ tr('composer.realtime') }}</strong><small>{{ tr('composer.realtimeDesc') }}</small></span>
      </button>
      <button class="upload-option" @click="$emit('select-upload-mode', 'camera')">
        <span class="option-icon"><Camera /></span>
        <span class="option-copy"><strong>{{ tr('composer.camera') }}</strong><small>{{ tr('composer.cameraDesc') }}</small></span>
      </button>
    </div>

    <div v-if="showCameraModal" class="camera-modal">
      <div class="camera-panel">
        <div class="camera-header">
          <strong>{{ tr('composer.camera') }}</strong>
          <button class="upload-remove" @click="$emit('close-camera')" :aria-label="tr('composer.closeCamera')">×</button>
        </div>
        <video ref="cameraVideoRef" autoplay playsinline muted class="camera-video" />
        <canvas ref="cameraCanvasRef" class="camera-canvas" />
        <div class="camera-actions">
          <button class="camera-action secondary" @click="$emit('close-camera')">{{ tr('composer.cancel') }}</button>
          <button class="camera-action primary" @click="captureCameraPhoto">{{ tr('composer.capture') }}</button>
        </div>
        <div v-if="cameraError" class="camera-error">{{ cameraError }}</div>
      </div>
    </div>

    <div class="input-wrapper" :class="{ 'is-listening': isListening }">
      <button
        type="button"
        class="add-btn"
        :class="{ active: showUploadMenu }"
        :aria-expanded="showUploadMenu"
        :aria-label="tr('composer.addAria')"
        @click="$emit('toggle-upload-menu')"
      >
        <Plus />
      </button>

      <textarea
        ref="textareaRef"
        :value="modelValue"
        rows="1"
        :placeholder="tr('composer.placeholder')"
        :aria-label="tr('composer.inputAria')"
        @input="handleTextInput"
        @keydown.enter.exact.prevent="$emit('send-message')"
      />

      <div class="input-actions">
        <button
          type="button"
          class="voice-btn"
          :class="{ active: isListening }"
          :title="voiceButtonTitle"
          :aria-label="voiceButtonTitle"
          @click="toggleVoiceInput"
        >
          <Microphone />
          <span v-if="isListening" class="voice-ring" />
        </button>

        <button
          type="button"
          class="send-btn"
          :disabled="!canSend"
          :aria-label="tr('composer.send')"
          @click="$emit('send-message')"
        >
          <Promotion />
        </button>
      </div>
    </div>

    <div v-if="isListening" class="voice-status listening-status">
      <span class="listening-bars"><i /><i /><i /><i /></span>
      {{ tr('composer.listening') }}
      <button type="button" @click="stopVoiceInput">{{ tr('composer.stop') }}</button>
    </div>
    <div v-else-if="speechError" class="voice-status voice-error">{{ speechError }}</div>

    <div class="input-tip">
      {{ tr('composer.tip') }}
    </div>
    </div>
  </div>
</template>

<script setup>
import { Camera, DocumentAdd, Files, Lightning, Microphone, Monitor, Picture, Plus, Promotion, VideoCamera } from '@element-plus/icons-vue'
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useLocaleStore } from '@/stores/locale'
import { t } from '@/utils/i18n'

const localeStore = useLocaleStore()
const tr = (key, params) => t(key, localeStore.locale, params)

const props = defineProps({
  modelValue: {
    type: String,
    default: '',
  },
  uploadQueue: {
    type: Array,
    default: () => [],
  },
  showUploadMenu: {
    type: Boolean,
    default: false,
  },
  showCameraModal: {
    type: Boolean,
    default: false,
  },
  inputAccept: {
    type: String,
    default: 'image/*',
  },
  inputMultiple: {
    type: Boolean,
    default: false,
  },
  inputCapture: {
    type: [String, Boolean, null],
    default: null,
  },
  cameraError: {
    type: String,
    default: '',
  },
  allowEmptySubmit: {
    type: Boolean,
    default: false,
  },
})

const emit = defineEmits([
  'update:modelValue',
  'toggle-upload-menu',
  'select-upload-mode',
  'remove-upload-item',
  'retry-upload',
  'file-selected',
  'close-camera',
  'capture-camera',
  'send-message',
  'camera-error',
])

const fileInputRef = ref(null)
const textareaRef = ref(null)
const cameraVideoRef = ref(null)
const cameraCanvasRef = ref(null)
const cameraStreamRef = ref(null)
const isListening = ref(false)
const speechError = ref('')
const speechSupported = ref(false)
let speechRecognition = null
let speechBaseText = ''

const canSend = computed(() => {
  const hasContent = Boolean(props.modelValue.trim())
  if (!props.uploadQueue.length) return hasContent
  const uploadsFinished = props.uploadQueue.every((item) => item.status === 'success')
  return uploadsFinished && (hasContent || props.allowEmptySubmit)
})
const voiceButtonTitle = computed(() => {
  if (!speechSupported.value) return tr('composer.voiceUnsupported')
  return isListening.value ? tr('composer.voiceStop') : tr('composer.voiceStart')
})

const getModeLabel = (mode) => ({
  'agent-image': tr('composer.agentImage'),
  image: tr('composer.single'),
  batch: tr('composer.batch'),
  video: tr('composer.video'),
  camera: tr('composer.camera'),
  knowledge: tr('composer.knowledge'),
}[mode] || tr('composer.file'))

const resizeTextarea = () => {
  const textarea = textareaRef.value
  if (!textarea) return
  textarea.style.height = 'auto'
  textarea.style.height = `${Math.min(textarea.scrollHeight, 132)}px`
}

const handleTextInput = (event) => {
  emit('update:modelValue', event.target.value)
  resizeTextarea()
}

const handleFileSelection = (event) => {
  const files = Array.from(event.target.files || [])
  emit('file-selected', files)
  event.target.value = ''
}

const stopCameraStream = () => {
  if (cameraStreamRef.value) {
    cameraStreamRef.value.getTracks().forEach((track) => track.stop())
    cameraStreamRef.value = null
  }
}

const startCameraStream = async () => {
  if (!props.showCameraModal) {
    stopCameraStream()
    return
  }

  if (!navigator.mediaDevices?.getUserMedia) {
    emit('camera-error', '当前浏览器不支持相机拍摄，将改为选择本地文件。')
    return
  }

  try {
    stopCameraStream()
    const stream = await navigator.mediaDevices.getUserMedia({
      video: { facingMode: 'environment' },
      audio: false,
    })

    cameraStreamRef.value = stream
    await nextTick()

    if (cameraVideoRef.value) {
      cameraVideoRef.value.srcObject = stream
      await cameraVideoRef.value.play()
    }
  } catch (error) {
    emit('camera-error', '无法访问相机，请检查权限或改为选择本地文件。')
  }
}

watch(() => props.showCameraModal, async (visible) => {
  if (visible) {
    await startCameraStream()
  } else {
    stopCameraStream()
  }
})

const captureCameraPhoto = () => {
  const video = cameraVideoRef.value
  const canvas = cameraCanvasRef.value

  if (!video || !canvas) return

  const width = video.videoWidth || 1280
  const height = video.videoHeight || 720

  canvas.width = width
  canvas.height = height
  const context = canvas.getContext('2d')
  context?.drawImage(video, 0, 0, width, height)

  canvas.toBlob((blob) => {
    if (!blob) return

    const file = new File([blob], `camera-capture-${Date.now()}.jpg`, {
      type: 'image/jpeg',
    })

    emit('capture-camera', file)
    emit('close-camera')
    stopCameraStream()
  }, 'image/jpeg', 0.92)
}

const openFilePicker = () => {
  fileInputRef.value?.click()
}

const getSpeechErrorMessage = (error) => ({
  'not-allowed': '麦克风权限被拒绝，请在浏览器设置中允许访问麦克风。',
  'service-not-allowed': '当前浏览器禁止使用语音识别服务。',
  'audio-capture': '未检测到可用麦克风，请检查设备连接。',
  network: '语音识别网络异常，请稍后重试。',
  'no-speech': '没有识别到语音，请靠近麦克风后重试。',
  aborted: '',
}[error] ?? '语音识别失败，请稍后重试。')

const setupSpeechRecognition = () => {
  const Recognition = window.SpeechRecognition || window.webkitSpeechRecognition
  speechSupported.value = Boolean(Recognition)
  if (!Recognition) return

  speechRecognition = new Recognition()
  speechRecognition.lang = localeStore.locale === 'en' ? 'en-US' : 'zh-CN'
  speechRecognition.continuous = false
  speechRecognition.interimResults = true
  speechRecognition.maxAlternatives = 1

  speechRecognition.onstart = () => {
    isListening.value = true
    speechError.value = ''
  }

  speechRecognition.onresult = (event) => {
    let transcript = ''
    for (let index = 0; index < event.results.length; index += 1) {
      transcript += event.results[index][0]?.transcript || ''
    }

    const separator = speechBaseText && transcript ? ' ' : ''
    emit('update:modelValue', `${speechBaseText}${separator}${transcript}`)
    nextTick(resizeTextarea)
  }

  speechRecognition.onerror = (event) => {
    speechError.value = getSpeechErrorMessage(event.error)
    isListening.value = false
  }

  speechRecognition.onend = () => {
    isListening.value = false
  }
}

const startVoiceInput = () => {
  if (!speechRecognition) {
    speechError.value = '当前浏览器不支持语音输入，请使用最新版 Chrome、Edge 或 Safari。'
    return
  }

  speechBaseText = props.modelValue.trim()
  speechError.value = ''
  try {
    speechRecognition.start()
  } catch (error) {
    speechError.value = '语音识别正在启动，请稍后再试。'
  }
}

const stopVoiceInput = () => {
  if (speechRecognition && isListening.value) {
    speechRecognition.stop()
  }
  isListening.value = false
}

const toggleVoiceInput = () => {
  if (isListening.value) stopVoiceInput()
  else startVoiceInput()
}

onMounted(() => {
  setupSpeechRecognition()
  resizeTextarea()
})

onBeforeUnmount(() => {
  stopVoiceInput()
  stopCameraStream()
})

watch(() => props.modelValue, () => nextTick(resizeTextarea))

watch(() => localeStore.locale, (locale) => {
  if (speechRecognition) speechRecognition.lang = locale === 'en' ? 'en-US' : 'zh-CN'
})

defineExpose({ openFilePicker })
</script>

<style scoped>
.chat-footer {
  padding: 18px 24px;
  border-top: 1px solid #e5e7eb;
  background: white;
}

.input-wrapper {
  display: flex;
  align-items: center;
  gap: 12px;
  border: 1px solid #e5e7eb;
  border-radius: 22px;
  padding: 12px 16px;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.05);
}

.image-btn {
  border: none;
  background: transparent;
  cursor: pointer;
  font-size: 22px;
}

.input-wrapper textarea {
  flex: 1;
  border: none;
  resize: none;
  outline: none;
  min-height: 30px;
  font-size: 15px;
  max-height: 120px;
  overflow-y: auto;
}

.input-wrapper .send-btn {
  width: 46px;
  height: 46px;
  border-radius: 50%;
  border: none;
  background: #16a34a;
  color: white;
  cursor: pointer;
}

.input-tip {
  text-align: center;
  margin-top: 10px;
  font-size: 13px;
  color: #9ca3af;
}

.upload-panel {
  display: flex;
  flex-direction: column;
  gap: 10px;
  margin-bottom: 12px;
}

.upload-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 10px 12px;
  border: 1px solid #e5e7eb;
  border-radius: 12px;
  background: #f9fafb;
}

.upload-item-main {
  display: flex;
  align-items: center;
  gap: 12px;
  flex: 1;
  min-width: 0;
}

.upload-preview {
  width: 48px;
  height: 48px;
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #ecfdf5;
  color: #16a34a;
  font-size: 20px;
  flex-shrink: 0;
  overflow: hidden;
}

.upload-preview img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.upload-info {
  flex: 1;
  min-width: 0;
}

.upload-name {
  font-size: 13px;
  font-weight: 600;
  color: #111827;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.upload-meta {
  margin-top: 2px;
  font-size: 12px;
  color: #6b7280;
}

.upload-progress-track {
  margin-top: 8px;
  width: 100%;
  height: 6px;
  border-radius: 999px;
  background: #e5e7eb;
  overflow: hidden;
}

.upload-progress-bar {
  height: 100%;
  border-radius: 999px;
  background: linear-gradient(90deg, #16a34a, #4ade80);
  transition: width 0.2s ease;
}

.upload-status {
  margin-top: 6px;
  font-size: 12px;
  color: #6b7280;
}

.success-text {
  color: #16a34a;
  font-weight: 600;
}

.error-text {
  color: #dc2626;
  font-weight: 600;
}

.upload-item-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

.retry-upload {
  border: 1px solid #fecaca;
  border-radius: 8px;
  padding: 5px 9px;
  background: #fff;
  color: #dc2626;
  cursor: pointer;
  font-size: 12px;
}

.upload-remove {
  border: none;
  background: transparent;
  color: #6b7280;
  cursor: pointer;
  font-size: 18px;
  line-height: 1;
}

.upload-menu {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 12px;
}

.upload-option {
  border: 1px solid #d1fae5;
  background: #f0fdf4;
  color: #166534;
  padding: 8px 12px;
  border-radius: 999px;
  cursor: pointer;
  font-size: 13px;
}

.upload-option.primary {
  background: #16a34a;
  color: white;
  border-color: #16a34a;
}

.camera-modal {
  position: fixed;
  inset: 0;
  background: rgba(17, 24, 39, 0.65);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 50;
  padding: 20px;
}

.camera-panel {
  width: min(560px, 100%);
  background: white;
  border-radius: 18px;
  padding: 16px;
  box-shadow: 0 20px 50px rgba(0, 0, 0, 0.2);
}

.camera-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 12px;
}

.camera-video {
  width: 100%;
  border-radius: 14px;
  background: #111827;
  min-height: 260px;
  object-fit: cover;
}

.camera-canvas {
  display: none;
}

.camera-actions {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
  margin-top: 12px;
}

.camera-error {
  margin-top: 10px;
  color: #dc2626;
  font-size: 13px;
}

/* 新版浮动输入区：参考主流对话产品，并保持农业系统绿色主题。 */
.chat-footer {
  position: absolute;
  right: 0;
  bottom: 0;
  left: 0;
  z-index: 20;
  padding: 42px 24px 16px;
  border-top: 0;
  background: linear-gradient(
    to top,
    #fafafa 0,
    rgba(250, 250, 250, 0.96) 64%,
    rgba(250, 250, 250, 0) 100%
  );
  pointer-events: none;
}

.composer-stack {
  position: relative;
  width: 100%;
  max-width: 900px;
  margin: 0 auto;
  pointer-events: auto;
}

.upload-panel {
  max-height: 230px;
  margin-bottom: 10px;
  padding: 8px;
  overflow-y: auto;
  border: 1px solid #e5e7eb;
  border-radius: 18px;
  background: rgba(255, 255, 255, 0.98);
  box-shadow: 0 10px 30px rgba(17, 24, 39, 0.08);
}

.upload-item {
  border-color: #eef2ef;
  border-radius: 14px;
  background: #fafcfb;
}

.upload-menu {
  position: absolute;
  right: 0;
  bottom: 74px;
  left: 0;
  z-index: 30;
  display: flex;
  flex-direction: column;
  flex-wrap: nowrap;
  gap: 3px;
  max-height: min(510px, 62vh);
  margin: 0;
  padding: 10px;
  overflow-y: auto;
  border: 1px solid #d9dedb;
  border-radius: 24px;
  background: rgba(255, 255, 255, 0.98);
  box-shadow: 0 18px 48px rgba(17, 24, 39, 0.14);
  backdrop-filter: blur(18px);
}

.upload-menu-title {
  padding: 8px 12px 6px;
  color: #9ca3af;
  font-size: 12px;
  font-weight: 700;
  letter-spacing: .04em;
}

.upload-option,
.upload-option.primary {
  display: flex;
  align-items: center;
  gap: 13px;
  width: 100%;
  padding: 11px 13px;
  border: 0;
  border-radius: 15px;
  background: transparent;
  color: #1f2937;
  text-align: left;
  transition: background .18s ease, transform .18s ease;
}

.upload-option:hover,
.upload-option.primary:hover {
  background: #f3f6f4;
  transform: translateX(2px);
}

.upload-option.primary {
  background: #f0fdf4;
}

.option-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 38px;
  height: 38px;
  flex-shrink: 0;
  border-radius: 11px;
  background: #f3f4f6;
  color: #374151;
}

.upload-option.primary .option-icon {
  background: #dcfce7;
  color: #15803d;
}

.option-icon :deep(svg) {
  width: 20px;
  height: 20px;
}

.option-copy {
  display: flex;
  flex: 1;
  min-width: 0;
  flex-direction: column;
  gap: 2px;
}

.option-copy strong {
  color: #1f2937;
  font-size: 14px;
  font-weight: 650;
}

.option-copy small {
  overflow: hidden;
  color: #9ca3af;
  font-size: 12px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.input-wrapper {
  min-height: 66px;
  gap: 9px;
  padding: 8px 9px 8px 11px;
  border: 1px solid #d8ddda;
  border-radius: 34px;
  background: #fff;
  box-shadow: 0 8px 28px rgba(17, 24, 39, 0.08);
  transition: border-color .2s ease, box-shadow .2s ease;
}

.input-wrapper:focus-within {
  border-color: #86b998;
  box-shadow: 0 10px 32px rgba(22, 163, 74, 0.12);
}

.input-wrapper.is-listening {
  border-color: #ef9a9a;
  box-shadow: 0 10px 32px rgba(220, 38, 38, 0.12);
}

.add-btn,
.voice-btn,
.send-btn {
  position: relative;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  border: 0;
  cursor: pointer;
  transition: transform .18s ease, background .18s ease, color .18s ease;
}

.add-btn {
  width: 42px;
  height: 42px;
  border-radius: 50%;
  background: transparent;
  color: #374151;
}

.add-btn:hover,
.add-btn.active,
.voice-btn:hover {
  background: #f1f5f2;
  color: #15803d;
}

.add-btn.active {
  transform: rotate(45deg);
}

.add-btn :deep(svg),
.voice-btn :deep(svg),
.send-btn :deep(svg) {
  width: 22px;
  height: 22px;
}

.input-wrapper textarea {
  min-width: 0;
  min-height: 28px;
  max-height: 132px;
  padding: 7px 4px;
  color: #1f2937;
  font-family: inherit;
  font-size: 16px;
  line-height: 1.55;
}

.input-wrapper textarea::placeholder {
  color: #9ca3af;
}

.input-actions {
  display: flex;
  align-items: center;
  gap: 5px;
}

.voice-btn {
  width: 42px;
  height: 42px;
  border-radius: 50%;
  background: transparent;
  color: #374151;
}

.voice-btn.active {
  background: #fef2f2;
  color: #dc2626;
}

.voice-ring {
  position: absolute;
  inset: 2px;
  border: 2px solid rgba(220, 38, 38, .35);
  border-radius: 50%;
  animation: voice-pulse 1.25s infinite ease-out;
}

.input-wrapper .send-btn {
  width: 46px;
  height: 46px;
  border-radius: 50%;
  background: #15803d;
  color: #fff;
}

.send-btn:hover:not(:disabled) {
  background: #166534;
  transform: scale(1.04);
}

.send-btn:disabled {
  background: #e5e7eb;
  color: #9ca3af;
  cursor: not-allowed;
}

.voice-status {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  min-height: 28px;
  margin-top: 7px;
  font-size: 12px;
}

.listening-status {
  color: #b91c1c;
}

.listening-status button {
  padding: 2px 7px;
  border: 0;
  border-radius: 999px;
  background: #fee2e2;
  color: #b91c1c;
  cursor: pointer;
}

.listening-bars {
  display: inline-flex;
  align-items: center;
  gap: 2px;
  height: 16px;
}

.listening-bars i {
  display: block;
  width: 3px;
  height: 7px;
  border-radius: 999px;
  background: #dc2626;
  animation: voice-bar .8s infinite ease-in-out;
}

.listening-bars i:nth-child(2) { animation-delay: .12s; }
.listening-bars i:nth-child(3) { animation-delay: .24s; }
.listening-bars i:nth-child(4) { animation-delay: .36s; }
.voice-error { color: #dc2626; }

.input-tip {
  margin-top: 7px;
  color: #9ca3af;
  font-size: 12px;
}

.camera-action {
  padding: 9px 15px;
  border: 1px solid #d1d5db;
  border-radius: 10px;
  cursor: pointer;
}

.camera-action.secondary {
  background: #fff;
  color: #374151;
}

.camera-action.primary {
  border-color: #16a34a;
  background: #16a34a;
  color: #fff;
}

@keyframes voice-pulse {
  0% { opacity: .8; transform: scale(.85); }
  100% { opacity: 0; transform: scale(1.28); }
}

@keyframes voice-bar {
  0%, 100% { height: 5px; opacity: .45; }
  50% { height: 15px; opacity: 1; }
}

@media (max-width: 640px) {
  .chat-footer {
    padding: 22px 10px max(12px, env(safe-area-inset-bottom));
  }

  .input-wrapper {
    min-height: 58px;
    gap: 8px;
    padding: 8px 10px;
    border-radius: 28px;
  }

  .add-btn,
  .voice-btn {
    width: 38px;
    height: 38px;
  }

  .input-wrapper .send-btn {
    width: 42px;
    height: 42px;
  }

  .input-wrapper textarea {
    font-size: 15px;
  }

  .upload-menu {
    bottom: 66px;
    max-height: 58vh;
    border-radius: 20px;
  }

  .option-copy small,
  .input-tip {
    display: none;
  }
}
</style>
