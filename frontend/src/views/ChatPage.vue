<template>
  <div class="chat-page">
    <ChatSidebar
      :sessions="sessions"
      @new-diagnosis="startNewDiagnosis"
    />

    <main class="main-area">
      <header class="topbar">
        <span>Plant Disease Diagnosis</span>
        <span class="model-status">🟢 Model Ready</span>
      </header>

      <ChatMessageList
        ref="chatMessageListRef"
        :messages="messages"
        @use-suggestion="useSuggestion"
        @open-upload="openUploadMenu"
      />

      <ChatComposer
        ref="chatComposerRef"
        v-model="message"
        :uploadQueue="uploadQueue"
        :showUploadMenu="showUploadMenu"
        :showCameraModal="showCameraModal"
        :inputAccept="inputAccept"
        :inputMultiple="inputMultiple"
        :inputCapture="inputCapture"
        :cameraError="cameraError"
        @toggle-upload-menu="toggleUploadMenu"
        @select-upload-mode="openUploadMenu"
        @remove-upload-item="removeUploadItem"
        @file-selected="handleFileSelection"
        @close-camera="closeCameraModal"
        @capture-camera="handleCameraCapture"
        @send-message="sendMessage"
        @camera-error="handleCameraError"
      />
    </main>
  </div>
</template>

<script setup>
import { nextTick, ref } from 'vue'

import ChatComposer from '@/components/ChatComposer.vue'
import ChatMessageList from '@/components/ChatMessageList.vue'
import ChatSidebar from '@/components/ChatSidebar.vue'

const message = ref('')
const messages = ref([])

const uploadQueue = ref([])
const uploadMode = ref('image')
const inputAccept = ref('image/*')
const inputMultiple = ref(false)
const inputCapture = ref(null)
const showUploadMenu = ref(false)
const showCameraModal = ref(false)
const cameraError = ref('')

const chatComposerRef = ref(null)
const chatMessageListRef = ref(null)

const scrollToBottom = async () => {
  await nextTick()
  chatMessageListRef.value?.scrollToBottom()
}

const toggleUploadMenu = () => {
  showUploadMenu.value = !showUploadMenu.value
}

const setUploadMode = (mode) => {
  uploadMode.value = mode

  if (mode === 'image') {
    inputAccept.value = 'image/*'
    inputMultiple.value = false
    inputCapture.value = null
  } else if (mode === 'batch') {
    inputAccept.value = 'image/*'
    inputMultiple.value = true
    inputCapture.value = null
  } else if (mode === 'video') {
    inputAccept.value = 'video/*'
    inputMultiple.value = false
    inputCapture.value = null
  } else if (mode === 'camera') {
    inputAccept.value = 'image/*'
    inputMultiple.value = false
    inputCapture.value = 'environment'
  }
}

const closeCameraModal = () => {
  showCameraModal.value = false
  cameraError.value = ''
}

const handleCameraError = (error) => {
  cameraError.value = error
  showCameraModal.value = false
  setUploadMode('image')

  nextTick(() => {
    chatComposerRef.value?.openFilePicker()
  })
}

const openUploadMenu = async (mode = 'image') => {
  setUploadMode(mode)
  showUploadMenu.value = false

  if (mode === 'camera') {
    showCameraModal.value = true
    return
  }

  nextTick(() => {
    chatComposerRef.value?.openFilePicker()
  })
}

const handleCameraCapture = (file) => {
  createUploadItem(file)
  closeCameraModal()
}

const removeUploadItem = (id) => {
  const item = uploadQueue.value.find((entry) => entry.id === id)

  if (item?.timer) {
    window.clearInterval(item.timer)
  }

  if (item?.previewUrl) {
    URL.revokeObjectURL(item.previewUrl)
  }

  uploadQueue.value = uploadQueue.value.filter((entry) => entry.id !== id)
}

const startUploadProgress = (item, file) => {
  const timer = window.setInterval(() => {
    if (item.status !== 'uploading') {
      window.clearInterval(timer)
      return
    }

    item.progress += 10 + Math.floor(Math.random() * 12)

    if (item.progress >= 100) {
      item.progress = 100
      item.status = 'success'
      window.clearInterval(timer)
      completeUpload(item, file)
    }
  }, 120)

  item.timer = timer
}

const createUploadItem = (file) => {
  const isVideo = file.type.startsWith('video/')
  const previewUrl = URL.createObjectURL(file)

  const item = {
    id: `${Date.now()}-${Math.random().toString(16).slice(2)}`,
    name: file.name,
    type: isVideo ? 'video' : 'image',
    previewUrl,
    progress: 0,
    status: 'uploading',
    mode: uploadMode.value,
    modeLabel: uploadMode.value === 'batch' ? 'Batch' : uploadMode.value === 'video' ? 'Video' : uploadMode.value === 'camera' ? 'Camera' : 'Single',
  }

  uploadQueue.value.unshift(item)
  startUploadProgress(item, file)
}

const handleFileSelection = (files) => {
  const normalizedFiles = Array.from(files || [])

  if (!normalizedFiles.length) return

  const selectedFiles = uploadMode.value === 'batch'
    ? normalizedFiles
    : normalizedFiles.slice(0, 1)

  selectedFiles.forEach((file) => createUploadItem(file))
}

const completeUpload = (item, file) => {
  const isVideo = item.type === 'video'
  const uploadMessage = {
    role: 'user',
    type: isVideo ? 'video' : 'image',
    imageUrl: isVideo ? '' : item.previewUrl,
    videoUrl: isVideo ? item.previewUrl : '',
    content: file.name,
  }

  messages.value.push(uploadMessage)
  scrollToBottom()

  window.setTimeout(() => {
    messages.value.push({
      role: 'assistant',
      type: 'diagnosis',
      disease: isVideo ? 'Video inspection queued' : 'Tomato Late Blight',
      plant: isVideo ? 'Crop stream' : 'Tomato',
      severity: isVideo ? 'Medium' : 'High',
      confidence: isVideo ? 88.4 : 94.2,
      annotatedImage: item.previewUrl,
      description: isVideo
        ? 'The uploaded video clip has been received and is ready for plant disease inspection.'
        : 'The uploaded image shows symptoms consistent with Tomato Late Blight, including dark lesions and leaf deterioration.',
      treatments: [
        'Inspect the affected leaves closely',
        'Apply the recommended treatment plan',
        'Monitor the plant over the next few days',
      ],
    })
    scrollToBottom()
  }, 600)
}

const sendMessage = () => {
  const content = message.value.trim()

  if (!content) return

  messages.value.push({
    role: 'user',
    content,
  })

  scrollToBottom()

  message.value = ''

  window.setTimeout(() => {
    messages.value.push({
      role: 'assistant',
      content: 'Thanks for the details. Please upload a clear image or video of the affected leaf so I can provide a more accurate diagnosis.',
    })
    scrollToBottom()
  }, 600)
}

const useSuggestion = (text) => {
  message.value = text
  sendMessage()
}

const startNewDiagnosis = () => {
  messages.value = []
  uploadQueue.value.forEach((item) => {
    if (item.timer) {
      window.clearInterval(item.timer)
    }
    if (item.previewUrl) {
      URL.revokeObjectURL(item.previewUrl)
    }
  })
  uploadQueue.value = []
  message.value = ''
  showUploadMenu.value = false
  showCameraModal.value = false
  cameraError.value = ''
}

const sessions = ref([
  'Tomato leaf disease',
  'Grape black rot',
  'Pepper diagnosis',
])
</script>

<style scoped>
.chat-page {
  display: flex;
  height: 100vh;
  background: #fafafa;
}

.main-area {
  flex: 1;
  display: flex;
  flex-direction: column;
}

.topbar {
  padding: 18px 24px;
  border-bottom: 1px solid #e5e7eb;
  font-weight: 600;
  background: white;
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.model-status {
  font-size: 13px;
  color: #6b7280;
  font-weight: 600;
}
</style>
