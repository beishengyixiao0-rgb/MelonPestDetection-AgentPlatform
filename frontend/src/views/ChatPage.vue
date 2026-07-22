<template>
  <div class="chat-page">
    <button
      v-if="sidebarOpen"
      class="sidebar-backdrop"
      type="button"
      :aria-label="tr('sidebar.close')"
      @click="closeSidebar"
    />

    <div
      id="chat-sidebar-drawer"
      class="sidebar-drawer"
      :class="{ open: sidebarOpen }"
      :aria-hidden="!sidebarOpen"
      :inert="!sidebarOpen"
    >
      <ChatSidebar
        :sessions="sessions"
        :current-session-id="currentSessionId"
        @new-diagnosis="handleNewDiagnosisFromSidebar"
        @select-session="handleSelectSessionFromSidebar"
        @delete-session="handleDeleteSession"
        @rename-session="handleRenameSession"
      />
      <button
        class="drawer-close"
        type="button"
        :aria-label="tr('sidebar.close')"
        @click="closeSidebar"
      >
        ×
      </button>
    </div>

    <main class="main-area">
      <header class="topbar">
        <div class="topbar-title">
          <button
            class="sidebar-toggle"
            type="button"
            aria-controls="chat-sidebar-drawer"
            :aria-expanded="sidebarOpen"
            :aria-label="sidebarOpen ? tr('sidebar.close') : tr('sidebar.open')"
            @click="toggleSidebar"
          >
            <span />
            <span />
            <span />
          </button>
          <span>{{ tr('chat.title') }}</span>
        </div>
        <div class="topbar-actions">
          <span class="model-status">🟢 {{ tr('chat.modelReady') }}</span>
          <LanguageSwitcher />
        </div>
      </header>

      <ChatMessageList
        ref="chatMessageListRef"
        :messages="messages"
        @use-suggestion="useSuggestion"
        @realtime-finished="handleRealtimeFinished"
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
        :allowEmptySubmit="hasReadyCameraAttachment"
        @toggle-upload-menu="toggleUploadMenu"
        @select-upload-mode="handleUploadModeSelection"
        @remove-upload-item="removeUploadItem"
        @retry-upload="retryUploadItem"
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
import { uploadCommonFile } from '@/api/common'
import { submitKnowledgeDocumentApi } from '@/api/knowledge'
import {
  detectBatch,
  detectSingle,
  detectVideo,
  detectZip,
  getVideoStatus,
} from '@/api/detection'
import { ElMessage } from 'element-plus'
import { storeToRefs } from 'pinia'
import { computed, nextTick, onBeforeUnmount, onMounted, reactive, ref } from 'vue'

import ChatComposer from '@/components/ChatComposer.vue'
import ChatMessageList from '@/components/ChatMessageList.vue'
import ChatSidebar from '@/components/ChatSidebar.vue'
import LanguageSwitcher from '@/components/LanguageSwitcher.vue'
import { useAgentStore } from '@/stores/agent'
import { useLocaleStore } from '@/stores/locale'
import { t } from '@/utils/i18n'
import { streamChat } from '@/utils/stream'

const message = ref('')
const agentStore = useAgentStore()
const localeStore = useLocaleStore()
const tr = (key, params) => t(key, localeStore.locale, params)
const { messages, sessions, currentSessionId } = storeToRefs(agentStore)

const uploadQueue = ref([])
const hasReadyCameraAttachment = computed(() => uploadQueue.value.some((item) => (
  item.mode === 'camera' && item.status === 'success'
)))
const uploadMode = ref('image')
const inputAccept = ref('image/*')
const inputMultiple = ref(false)
const inputCapture = ref(null)
const showUploadMenu = ref(false)
const showCameraModal = ref(false)
const cameraError = ref('')

const chatComposerRef = ref(null)
const chatMessageListRef = ref(null)
const COMPACT_BREAKPOINT = 900
const isCompactViewport = ref(
  typeof window !== 'undefined' && window.innerWidth <= COMPACT_BREAKPOINT,
)
const sidebarOpen = ref(!isCompactViewport.value)

const closeSidebar = () => {
  sidebarOpen.value = false
}

const toggleSidebar = () => {
  sidebarOpen.value = !sidebarOpen.value
}

const closeSidebarOnCompact = () => {
  if (isCompactViewport.value) closeSidebar()
}

const handleViewportResize = () => {
  const nextCompact = window.innerWidth <= COMPACT_BREAKPOINT
  if (nextCompact === isCompactViewport.value) return
  isCompactViewport.value = nextCompact
  sidebarOpen.value = !nextCompact
}

const handleSidebarKeydown = (event) => {
  if (event.key === 'Escape' && sidebarOpen.value) closeSidebar()
}

const scrollToBottom = async () => {
  await nextTick()
  chatMessageListRef.value?.scrollToBottom()
}

const toggleUploadMenu = () => {
  showUploadMenu.value = !showUploadMenu.value
}

const setUploadMode = (mode) => {
  uploadMode.value = mode

  if (mode === 'image' || mode === 'agent-image') {
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
  } else if (mode === 'knowledge') {
    inputAccept.value = '.md,.txt,text/markdown,text/plain'
    inputMultiple.value = false
    inputCapture.value = null
  }
}

const closeCameraModal = () => {
  showCameraModal.value = false
  cameraError.value = ''
}

const handleCameraError = (error) => {
  cameraError.value = error
  showCameraModal.value = false
  // 相机不可用时改选本地照片，但仍沿用“有提示词走 Agent、无提示词走 YOLO”的分流。
  setUploadMode('camera')
  inputCapture.value = null

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

const handleUploadModeSelection = (mode) => {
  showUploadMenu.value = false

  if (mode === 'image') {
    handleQuickDetect('single')
    return
  }

  if (mode === 'realtime-camera') {
    startRealtimeDetection()
    return
  }

  if (mode === 'batch') {
    handleQuickDetect('batch')
    return
  }

  if (mode === 'agent-image') {
    openUploadMenu('agent-image')
    return
  }

  if (mode === 'knowledge') {
    if (uploadQueue.value.length) {
      ElMessage.warning(tr('chat.knowledge.clearAttachments'))
      return
    }
    openUploadMenu('knowledge')
    return
  }

  if (mode === 'video') {
    handleVideoDetect()
    return
  }

  openUploadMenu(mode)
}

const startRealtimeDetection = () => {
  agentStore.addMessage({
    role: 'user',
    content: '请开启摄像头进行实时检测',
  })
  agentStore.addMessage({
    id: `realtime-${Date.now()}`,
    role: 'assistant',
    type: 'realtime-detection',
    content: '请确认摄像头权限并开始实时检测',
    config: {
      mode: 'cpu',
      conf: 0.25,
      iou: 0.45,
    },
  })
  scrollToBottom()
}

const handleRealtimeFinished = ({ result }) => {
  agentStore.addMessage({
    role: 'assistant',
    type: 'diagnosis',
    content: `实时检测完成，共处理 ${result.processed_frames ?? 0} 帧。`,
    detectionResult: result,
    annotatedImage: result.annotated_image_url || '',
  })
  scrollToBottom()
}

const handleCameraCapture = (file) => {
  closeCameraModal()
  setUploadMode('camera')
  createUploadItem(file)
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

const getUploadedFileUrl = (result) => (
  result?.url
  || result?.file_url
  || result?.object_url
  || result?.data?.url
  || result?.data?.file_url
  || ''
)

const uploadAttachment = async (item) => {
  item.status = 'uploading'
  item.progress = 0
  item.errorMessage = ''

  const formData = new FormData()
  formData.append('file', item.file)

  try {
    const result = await uploadCommonFile(formData, (progressEvent) => {
      if (!progressEvent.total) return
      item.progress = Math.min(99, Math.round((progressEvent.loaded / progressEvent.total) * 100))
    })

    item.progress = 100
    item.status = 'success'
    item.uploadResult = result
    item.uploadUrl = getUploadedFileUrl(result)

    // Agent 图片和手动拍照需要停留在输入区，等待用户输入文字并点击发送。
    if (!['agent-image', 'camera'].includes(item.mode)) {
      completeUpload(item, item.file)
    }
  } catch (error) {
    item.status = 'error'
    item.errorMessage = getErrorMessage(error)
  }
}

const retryUploadItem = (id) => {
  const item = uploadQueue.value.find((entry) => entry.id === id)
  if (item) uploadAttachment(item)
}

const createUploadItem = (file) => {
  const isVideo = file.type.startsWith('video/')
  const previewUrl = URL.createObjectURL(file)

  // 上传回调会持续修改这个对象，使用 reactive 才能立即刷新进度与成功状态。
  const item = reactive({
    id: `${Date.now()}-${Math.random().toString(16).slice(2)}`,
    name: file.name,
    type: isVideo ? 'video' : 'image',
    previewUrl,
    progress: 0,
    status: 'uploading',
    mode: uploadMode.value,
    modeLabel: uploadMode.value === 'agent-image'
      ? 'Agent attachment'
      : uploadMode.value === 'batch'
        ? 'Batch'
        : uploadMode.value === 'video'
          ? 'Video'
          : uploadMode.value === 'camera'
            ? 'Camera'
            : 'Single',
    file,
    uploadResult: null,
    uploadUrl: '',
    errorMessage: '',
  })

  uploadQueue.value.unshift(item)
  item.uploadPromise = uploadAttachment(item)
  return item
}

const handleFileSelection = (files) => {
  const normalizedFiles = Array.from(files || [])

  if (!normalizedFiles.length) return

  if (uploadMode.value === 'knowledge') {
    void submitKnowledgeFromChat(normalizedFiles[0])
    return
  }

  if (uploadMode.value === 'camera') {
    handleCameraCapture(normalizedFiles[0])
    return
  }

  const selectedFiles = uploadMode.value === 'batch'
    ? normalizedFiles
    : normalizedFiles.slice(0, 1)

  selectedFiles.forEach((file) => createUploadItem(file))
}

/**
 * 对话中的知识投稿采用“确定性写入 + LLM 说明”的组合流程：
 * 先调用知识接口创建 pending 记录，再把真实记录状态作为用户消息交给 Agent。
 * 当前后端 Agent 只有 search_knowledge，不能让 LLM 自主写知识库。
 */
const submitKnowledgeFromChat = async (file) => {
  if (!file || !/\.(md|txt)$/i.test(file.name)) {
    ElMessage.warning(tr('knowledge.invalidFile'))
    return
  }

  const note = message.value.trim()
  const submittingNotice = ElMessage({
    message: tr('chat.knowledge.submitting'),
    type: 'info',
    duration: 0,
  })

  try {
    const result = await submitKnowledgeDocumentApi(file)
    ElMessage.success(tr('chat.knowledge.submitted'))

    message.value = tr('chat.knowledge.agentPrompt', {
      name: file.name,
      id: result?.document_id ?? '—',
      note: note || tr('chat.knowledge.noNote'),
    })
    await sendMessage()
  } finally {
    submittingNotice.close()
  }
}

/** 把快捷检测原图上传到持久化存储，供历史会话刷新后恢复预览。 */
const uploadHistoryAttachments = async (files) => {
  const imageFiles = Array.from(files || []).filter((file) => file.type?.startsWith('image/'))
  const uploads = await Promise.allSettled(imageFiles.map(async (file) => {
    const formData = new FormData()
    formData.append('file', file)
    const result = await uploadCommonFile(formData)
    return result?.attachment_url || result?.data?.attachment_url || null
  }))

  return uploads
    .filter((item) => item.status === 'fulfilled' && item.value)
    .map((item) => item.value)
}

const persistQuickDetectionHistory = async ({
  files,
  userContent,
  assistantContent,
  result,
  attachmentUrls = [],
}) => {
  try {
    const uploadedAttachments = await uploadHistoryAttachments(files)
    const attachments = [...attachmentUrls, ...uploadedAttachments].filter(Boolean)
    await agentStore.saveQuickDetection({
      userContent,
      assistantContent,
      detectionResult: result,
      attachments,
    })
  } catch (error) {
    // 检测已经成功时，历史保存失败不应影响当前结果卡片。
    console.warn('[快捷检测历史保存失败]', error)
  }
}

/**
 * 快捷检测：选择文件后直接调用检测 API，不经过 LLM 对话。
 * 由页面底部输入栏的上传菜单触发。
 */
async function handleQuickDetect(type, selectedFiles = null) {
  const input = document.createElement('input')
  input.type = 'file'
  input.accept = type === 'batch' ? 'image/*,.zip' : 'image/*'
  input.multiple = type === 'batch'

  input.onchange = async (event) => {
    const files = Array.from(event.target?.files || [])
    if (!files.length) return

    if (type === 'single') {
      const file = files[0]
      const imagePreview = URL.createObjectURL(file)

      agentStore.addMessage({
        role: 'user',
        type: 'image',
        content: tr('chat.quick.singleUser', { name: file.name }),
        image: file.name,
        imagePreview,
        imageUrl: imagePreview,
      })

      agentStore.addMessage({
        role: 'assistant',
        content: tr('chat.quick.singleLoading'),
        loading: true,
      })
      const loadingMessage = agentStore.messages[agentStore.messages.length - 1]
      scrollToBottom()

      const formData = new FormData()
      formData.append('file', file)

      try {
        formData.append('conf', '0.25')
        formData.append('iou', '0.45')

        const result = await detectSingle(formData)
        loadingMessage.content = tr('chat.quick.singleDone', { count: result.total_objects ?? 0 })
        loadingMessage.loading = false
        loadingMessage.type = 'diagnosis'
        loadingMessage.detectionResult = result
        const annotatedBase64 = result.annotated_image_base64 || result.annotated_image
        loadingMessage.annotatedImage = annotatedBase64
          ? (String(annotatedBase64).startsWith('data:')
              ? annotatedBase64
              : `data:image/jpeg;base64,${annotatedBase64}`)
          : result.annotated_image_url || result.result_image_url || ''
        void persistQuickDetectionHistory({
          files: [file],
          userContent: tr('chat.quick.singleUser', { name: file.name }),
          assistantContent: loadingMessage.content,
          result,
        })
      } catch (error) {
        loadingMessage.content = tr('chat.quick.singleFailed', { message: getErrorMessage(error) })
        loadingMessage.loading = false
        loadingMessage.error = true
      }

      scrollToBottom()
      return
    }

    const isZip = files.length === 1 && files[0].name.toLowerCase().endsWith('.zip')
    const formData = new FormData()

    if (isZip) {
      formData.append('file', files[0])
      agentStore.addMessage({
        role: 'user',
        content: tr('chat.quick.zip', { name: files[0].name }),
      })
    } else {
      files.forEach((file) => formData.append('files', file))
      agentStore.addMessage({
        role: 'user',
        content: tr('chat.quick.batchImages', { count: files.length }),
        images: files.map((file) => URL.createObjectURL(file)),
      })
    }

    agentStore.addMessage({
      role: 'assistant',
      content: tr('chat.quick.batchLoading'),
      loading: true,
    })
    const loadingMessage = agentStore.messages[agentStore.messages.length - 1]
    scrollToBottom()

    try {
      const result = await (isZip ? detectZip(formData) : detectBatch(formData))

      if (result.error) {
        loadingMessage.content = tr('chat.quick.batchFailed', { message: result.error })
        loadingMessage.loading = false
        loadingMessage.error = true
        scrollToBottom()
        return
      }

      const displayResult = !isZip && Array.isArray(result.annotated_images)
        ? {
            ...result,
            annotated_images: result.annotated_images.map((image, index) => ({
              ...image,
              original_filename: files[index]?.name || image.image_path,
            })),
          }
        : result

      loadingMessage.content = tr('chat.quick.batchDone', { count: displayResult.total_objects ?? 0 })
      loadingMessage.loading = false
      loadingMessage.type = 'diagnosis'
      loadingMessage.detectionResult = displayResult
      loadingMessage.annotatedImage = displayResult.annotated_image_url || displayResult.result_image_url || ''
      void persistQuickDetectionHistory({
        files,
        userContent: isZip
          ? tr('chat.quick.zip', { name: files[0].name })
          : tr('chat.quick.batchImages', { count: files.length }),
        assistantContent: loadingMessage.content,
        result: displayResult,
      })
    } catch (error) {
      loadingMessage.content = tr('chat.quick.batchFailed', { message: getErrorMessage(error) })
      loadingMessage.loading = false
      loadingMessage.error = true
    }

    scrollToBottom()
  }

  if (selectedFiles?.length) {
    await input.onchange({ target: { files: selectedFiles } })
    return
  }

  input.click()
}

/**
 * 视频检测流程
 *
 * 1. 用户点击“视频检测”按钮
 * 2. 弹出文件选择框（限制视频格式）
 * 3. 选择视频后上传到后端
 * 4. 后端返回 task_id，前端开始轮询进度
 * 5. 处理完成后展示检测结果
 */
const VIDEO_POLL_INTERVAL = 1500
const VIDEO_POLL_MAX_ATTEMPTS = 200
const activeVideoPolls = new Set()

const waitForNextVideoPoll = () => (
  new Promise((resolve) => window.setTimeout(resolve, VIDEO_POLL_INTERVAL))
)

const normalizeVideoResult = (payload, taskId) => {
  const nestedResult = payload?.result
    || payload?.detection_result
    || payload?.data?.result
    || (payload?.data && typeof payload.data === 'object' ? payload.data : null)
  const result = nestedResult && typeof nestedResult === 'object' ? nestedResult : payload

  return {
    ...result,
    type: 'video',
    task_id: result?.task_id ?? taskId,
  }
}

const updateVideoProgress = (messageItem, patch) => {
  messageItem.videoProgress = {
    ...(messageItem.videoProgress || {}),
    ...patch,
  }
}

async function pollVideoProgress(taskId, loadingMessage) {
  const pollToken = Symbol(`video-${taskId}`)
  activeVideoPolls.add(pollToken)

  try {
    for (let attempt = 0; attempt < VIDEO_POLL_MAX_ATTEMPTS; attempt += 1) {
      if (!activeVideoPolls.has(pollToken)) return null

      const payload = await getVideoStatus(taskId) || {}
      const status = String(payload.status || payload.state || '').toLowerCase()
      const progress = Number(payload.progress ?? payload.percent ?? 0)
      const progressPercent = progress > 0 && progress <= 1 ? progress * 100 : progress

      if (payload.error) {
        throw new Error(payload.error)
      }

      if (Number.isFinite(progressPercent) && progressPercent > 0) {
        loadingMessage.content = `视频处理中... ${Math.min(100, Math.round(progressPercent))}%`
      } else {
        loadingMessage.content = payload.message || '视频已上传，正在处理中...'
      }
      updateVideoProgress(loadingMessage, {
        status: 'processing',
        progress: Number.isFinite(progressPercent) ? Math.min(100, Math.max(0, progressPercent)) : 0,
        message: loadingMessage.content,
        taskId,
      })

      if (['completed', 'complete', 'success', 'succeeded', 'finished', 'done'].includes(status)) {
        const result = normalizeVideoResult(payload, taskId)
        loadingMessage.content = tr('chat.video.done', { count: result.total_objects ?? 0 })
        loadingMessage.loading = false
        loadingMessage.type = 'diagnosis'
        loadingMessage.detectionResult = result
        updateVideoProgress(loadingMessage, { status: 'completed', progress: 100 })
        scrollToBottom()
        return result
      }

      if (['failed', 'failure', 'error', 'cancelled', 'canceled'].includes(status)) {
        throw new Error(payload.message || payload.detail || '视频处理失败')
      }

      await waitForNextVideoPoll()
    }

    throw new Error('视频处理超时，请稍后重试')
  } finally {
    activeVideoPolls.delete(pollToken)
  }
}

async function handleVideoDetect(selectedFile = null) {
  const input = document.createElement("input");

  input.type = "file";
  input.accept =
    ".mp4,.avi,.mov,.mkv,.wmv,.flv,video/mp4,video/quicktime,video/x-msvideo";

  input.onchange = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;

    // 文件大小限制：50 MB
    const maxSize = 50 * 1024 * 1024;
    if (file.size > maxSize) {
      ElMessage.warning("视频文件不能超过 50MB");
      return;
    }

    // 创建本地预览地址
    const videoUrl = URL.createObjectURL(file);

    // 添加用户消息
    agentStore.addMessage({
      role: "user",
      type: "video",
      content: `${tr('chat.video.user', { name: file.name })} (${(
        file.size /
        (1024 * 1024)
      ).toFixed(1)} MB)`,
      videoUrl,
    });

    // 添加加载占位消息
    agentStore.addMessage({
      role: "assistant",
      type: "video-progress",
      content: "正在上传视频...",
      loading: true,
      videoProgress: {
        fileName: file.name,
        fileSize: file.size,
        status: "uploading",
        progress: 0,
        message: "正在上传视频...",
        taskId: null,
      },
    });
    const loadingMessage =
      agentStore.messages[agentStore.messages.length - 1];
    scrollToBottom();

    const formData = new FormData();
    formData.append("file", file);
    formData.append("conf", "0.25");
    formData.append("iou", "0.45");
    formData.append("frame_sample_rate", "5");
    formData.append("max_frames", "50");

    try {
      // 上传视频
      const uploadResult = await detectVideo(formData);
      const taskId = uploadResult.task_id;

      if (!taskId) {
        throw new Error("后端未返回视频检测 task_id");
      }

      // 更新加载提示
      loadingMessage.content = "视频已上传，正在处理中...";
      updateVideoProgress(loadingMessage, {
        status: "processing",
        progress: 0,
        message: loadingMessage.content,
        taskId,
      });

      // 轮询检测进度
      const result = await pollVideoProgress(taskId, loadingMessage);
      if (result) {
        void persistQuickDetectionHistory({
          files: [],
          userContent: tr('chat.video.user', { name: file.name }),
          assistantContent: loadingMessage.content,
          result,
          attachmentUrls: [result.source_video_url],
        });
      }
    } catch (error) {
      console.error("[视频检测失败]", error);

      loadingMessage.content = tr('chat.video.failed', { message: getErrorMessage(error) });

      loadingMessage.loading = false;
      loadingMessage.error = true;
      updateVideoProgress(loadingMessage, {
        status: "failed",
        message: loadingMessage.content,
      });
    }
  };

  if (selectedFile) {
    await input.onchange({ target: { files: [selectedFile] } });
    return;
  }

  input.click();
}

const getErrorMessage = (error) => (
  error?.response?.data?.detail
  || error?.response?.data?.message
  || error?.message
  || '请重试'
)

const completeUpload = (item, file) => {
  const isVideo = item.type === 'video'
  const uploadMessage = {
    role: 'user',
    type: isVideo ? 'video' : 'image',
    imageUrl: isVideo ? '' : item.previewUrl,
    videoUrl: isVideo ? item.previewUrl : '',
    content: file.name,
  }

  agentStore.addMessage(uploadMessage)
  scrollToBottom()

  window.setTimeout(() => {
    agentStore.addMessage({
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

const sendMessage = async () => {
  const content = message.value.trim()
  const attachments = uploadQueue.value.filter((item) => (
    item.mode === 'agent-image' || item.mode === 'camera'
  ))

  if (!content && !attachments.length) return
  if (attachments.some((item) => item.status !== 'success')) return

  // 手动拍照且没有额外提示词：发送时改走快捷 YOLO，不经过 Agent/LLM。
  if (!content && attachments.length === 1 && attachments[0].mode === 'camera') {
    const cameraAttachment = attachments[0]
    const cameraFile = cameraAttachment.file

    uploadQueue.value = uploadQueue.value.filter((item) => item.id !== cameraAttachment.id)
    if (cameraAttachment.previewUrl?.startsWith('blob:')) {
      URL.revokeObjectURL(cameraAttachment.previewUrl)
    }

    await handleQuickDetect('single', [cameraFile])
    return
  }

  agentStore.abort()

  // /api/chat/upload 返回服务器临时路径；单附件和多附件分别传给对应字段。
  const attachmentPaths = attachments.map((item) => (
    item.uploadResult?.image_path
    || item.uploadResult?.data?.image_path
    || item.uploadUrl
  )).filter(Boolean)
  const imagePath = attachmentPaths.length === 1 ? attachmentPaths[0] : null
  const imagePaths = attachmentPaths.length > 1 ? attachmentPaths : null
  const attachmentUrls = attachments.map((item) => (
    item.uploadResult?.attachment_url
    || item.uploadResult?.data?.attachment_url
  )).filter(Boolean)

  const userMessage = {
    role: 'user',
    content: content || '请帮我分析这张图片',
  }

  if (attachments.length === 1) {
    userMessage.type = 'image'
    userMessage.imageUrl = attachments[0].previewUrl
  } else if (attachments.length > 1) {
    userMessage.images = attachments.map((item) => item.previewUrl)
  }

  agentStore.addMessage(userMessage)

  agentStore.addMessage({
    role: 'assistant',
    type: attachments.length ? 'agent-analysis' : undefined,
    agentPrompt: attachments.length ? userMessage.content : '',
    inputImage: attachments[0]?.previewUrl || '',
    modelThinking: false,
    content: '',
    loading: true,
  })
  const assistantMessage = agentStore.messages[agentStore.messages.length - 1]
  agentStore.setLoading(true)

  scrollToBottom()

  message.value = ''
  // 从输入区移除，但不释放 blob URL，因为它已用于消息预览。
  uploadQueue.value = uploadQueue.value.filter((item) => (
    item.mode !== 'agent-image' && item.mode !== 'camera'
  ))

  const stop = streamChat(
    '/api/chat/stream',
    {
      message: userMessage.content,
      image_path: imagePath,
      image_paths: imagePaths,
      attachment_urls: attachmentUrls,
      session_id: agentStore.currentSessionId,
    },
    {
      onMessage: (event) => {
        if (event.type === 'thinking') {
          assistantMessage.modelThinking = true
        } else if (event.type === 'text_chunk') {
          if (assistantMessage.detectionResult && event.content) {
            assistantMessage.modelThinking = false
          }
          assistantMessage.content += event.content || ''
        } else if (event.type === 'error' && event.content) {
          assistantMessage.modelThinking = false
          assistantMessage.content += event.content
        }

        if (event.session_id) {
          agentStore.currentSessionId = event.session_id
        }

        if (['tool_result', 'tool_end'].includes(event.type) && event.result) {
          try {
            const detectionResult = typeof event.result === 'string'
              ? JSON.parse(event.result)
              : event.result
            const detectionTools = [
              'detect_single_image',
              'detect_batch_images',
              'detect_zip_images_file',
              'detect_video_file',
            ]
            const isDetectionResult = detectionTools.includes(event.tool)
              || detectionResult?.type === 'video'
              || 'total_objects' in (detectionResult || {})
              || 'annotated_image_url' in (detectionResult || {})
              || 'annotated_images' in (detectionResult || {})

            if (isDetectionResult) {
              assistantMessage.type = 'agent-analysis'
              assistantMessage.detectionResult = detectionResult
              assistantMessage.modelThinking = true
            }
          } catch (error) {
            console.error('[Agent 检测结果解析失败]', error, event.result)
          }
        } else if (event.type === 'diagnosis' || event.detectionResult) {
          assistantMessage.type = 'agent-analysis'
          assistantMessage.detectionResult = event.detectionResult || event
          assistantMessage.modelThinking = true
        }

        scrollToBottom()
      },
      onDone: async () => {
        assistantMessage.loading = false
        assistantMessage.modelThinking = false
        agentStore.setLoading(false)
        agentStore.abortController = null

        if (!assistantMessage.content) {
          assistantMessage.content = assistantMessage.detectionResult
            ? 'YOLO 检测已完成，但大模型暂未返回分析内容。'
            : '分析已完成'
        }

        await agentStore.loadSessions()
        scrollToBottom()
      },
      onError: (error) => {
        assistantMessage.loading = false
        assistantMessage.modelThinking = false
        assistantMessage.error = true
        assistantMessage.content = `Agent 请求失败：${getErrorMessage(error)}`
        agentStore.setLoading(false)
        agentStore.abortController = null
        scrollToBottom()
      },
    },
  )

  agentStore.abortController = stop
}

onMounted(async () => {
  handleViewportResize()
  window.addEventListener('resize', handleViewportResize)
  window.addEventListener('keydown', handleSidebarKeydown)
  await agentStore.loadSessions()
  const pendingPrompt = agentStore.consumePendingPrompt()

  if (!pendingPrompt) return

  const pendingFiles = Array.from(pendingPrompt.files || [])

  if (pendingPrompt.mode === 'agent-image' && pendingFiles.length) {
    setUploadMode('agent-image')
    const pendingItems = pendingFiles.slice(0, 1).map((file) => createUploadItem(file))
    message.value = pendingPrompt.content || '请帮我分析这张图片'
    await Promise.all(pendingItems.map((item) => item.uploadPromise))

    if (pendingItems.every((item) => item.status === 'success')) {
      await sendMessage()
    }
    return
  }

  if (pendingPrompt.mode === 'image' && pendingFiles.length) {
    await handleQuickDetect('single', pendingFiles)
    return
  }

  if (pendingPrompt.mode === 'batch' && pendingFiles.length) {
    await handleQuickDetect('batch', pendingFiles)
    return
  }

  if (pendingPrompt.mode === 'video' && pendingFiles.length) {
    await handleVideoDetect(pendingFiles[0])
    return
  }

  if (pendingPrompt.mode === 'camera') {
    message.value = pendingPrompt.content || ''
    await nextTick()
    handleUploadModeSelection('camera')
    return
  }

  if (pendingPrompt.mode === 'realtime-camera') {
    handleUploadModeSelection('realtime-camera')
    return
  }

  if (!pendingPrompt.content) return

  message.value = pendingPrompt.content
  await nextTick()
  await sendMessage()
})

onBeforeUnmount(() => {
  activeVideoPolls.clear()
  window.removeEventListener('resize', handleViewportResize)
  window.removeEventListener('keydown', handleSidebarKeydown)
})

const useSuggestion = (text) => {
  message.value = text
  sendMessage()
}

const startNewDiagnosis = () => {
  messages.value.forEach((item) => {
    if (item.imagePreview?.startsWith('blob:')) URL.revokeObjectURL(item.imagePreview)
    if (item.imageUrl?.startsWith('blob:')) URL.revokeObjectURL(item.imageUrl)
    if (item.videoUrl?.startsWith('blob:')) URL.revokeObjectURL(item.videoUrl)
    item.images?.forEach((url) => {
      if (url.startsWith('blob:')) URL.revokeObjectURL(url)
    })
  })
  agentStore.newChat()
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

const handleNewDiagnosisFromSidebar = () => {
  startNewDiagnosis()
  closeSidebarOnCompact()
}

const handleSelectSession = async (sessionId) => {
  if (sessionId === currentSessionId.value) return

  agentStore.abort()
  messages.value.forEach((item) => {
    if (item.imagePreview?.startsWith('blob:')) URL.revokeObjectURL(item.imagePreview)
    if (item.imageUrl?.startsWith('blob:')) URL.revokeObjectURL(item.imageUrl)
    if (item.videoUrl?.startsWith('blob:')) URL.revokeObjectURL(item.videoUrl)
    item.images?.forEach((url) => {
      if (url.startsWith('blob:')) URL.revokeObjectURL(url)
    })
  })

  uploadQueue.value.forEach((item) => {
    if (item.timer) window.clearInterval(item.timer)
    if (item.previewUrl?.startsWith('blob:')) URL.revokeObjectURL(item.previewUrl)
  })
  uploadQueue.value = []
  message.value = ''
  showUploadMenu.value = false
  closeCameraModal()

  await agentStore.loadSessionMessages(sessionId)
  await scrollToBottom()
}

const handleSelectSessionFromSidebar = async (sessionId) => {
  await handleSelectSession(sessionId)
  closeSidebarOnCompact()
}

const handleDeleteSession = async (sessionId) => {
  const deletingCurrent = String(sessionId) === String(currentSessionId.value)
  const deleted = await agentStore.deleteSession(sessionId)

  if (deleted && deletingCurrent) {
    uploadQueue.value.forEach((item) => {
      if (item.timer) window.clearInterval(item.timer)
      if (item.previewUrl?.startsWith('blob:')) URL.revokeObjectURL(item.previewUrl)
    })
    uploadQueue.value = []
    message.value = ''
    showUploadMenu.value = false
    closeCameraModal()
  }
}

const handleRenameSession = async (sessionId, newTitle) => {
  await agentStore.renameSession(sessionId, newTitle)
}
</script>

<style scoped>
.chat-page {
  display: flex;
  height: 100vh;
  min-width: 0;
  overflow: hidden;
  background: #fafafa;
}

.sidebar-drawer {
  position: relative;
  z-index: 30;
  width: 300px;
  flex: 0 0 300px;
  overflow: hidden;
  background: #fff;
  transform: translateX(0);
  transition: width .24s ease, flex-basis .24s ease, transform .24s ease;
}

.sidebar-drawer:not(.open) {
  width: 0;
  flex-basis: 0;
  transform: translateX(-100%);
}

.sidebar-drawer :deep(.sidebar) {
  box-sizing: border-box;
  width: 300px;
}

.drawer-close {
  position: absolute;
  top: 13px;
  right: 12px;
  width: 30px;
  height: 30px;
  display: grid;
  place-items: center;
  border: 0;
  border-radius: 9px;
  background: #f3f5f3;
  color: #667069;
  font-size: 22px;
  line-height: 1;
  cursor: pointer;
}

.drawer-close:hover,
.sidebar-toggle:hover {
  background: #eaf5ed;
  color: #168149;
}

.sidebar-backdrop {
  display: none;
}

.main-area {
  position: relative;
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
  overflow: hidden;
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

.topbar-title {
  min-width: 0;
  display: flex;
  align-items: center;
  gap: 12px;
}

.topbar-title > span {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.sidebar-toggle {
  width: 36px;
  height: 36px;
  flex: 0 0 36px;
  display: inline-flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 4px;
  padding: 0;
  border: 1px solid #e1e7e3;
  border-radius: 10px;
  background: #fff;
  color: #536158;
  cursor: pointer;
  transition: .18s ease;
}

.sidebar-toggle span {
  width: 15px;
  height: 1.5px;
  border-radius: 999px;
  background: currentColor;
}

.topbar-actions {
  display: flex;
  align-items: center;
  gap: 12px;
}

.model-status {
  font-size: 13px;
  color: #6b7280;
  font-weight: 600;
}

@media (max-width: 900px) {
  .chat-page {
    height: 100dvh;
  }

  .sidebar-drawer,
  .sidebar-drawer:not(.open) {
    position: fixed;
    inset: 0 auto 0 0;
    z-index: 80;
    width: min(86vw, 320px);
    height: 100dvh;
    flex: none;
    overflow: visible;
    visibility: hidden;
    transform: translateX(-102%);
    transition: transform .24s ease, visibility .24s ease;
  }

  .sidebar-drawer.open {
    width: min(86vw, 320px);
    visibility: visible;
    transform: translateX(0);
    box-shadow: 18px 0 42px rgba(20, 35, 25, .18);
  }

  .sidebar-drawer :deep(.sidebar) {
    width: 100%;
    height: 100dvh;
    padding: 18px;
  }

  .sidebar-backdrop {
    position: fixed;
    inset: 0;
    z-index: 70;
    display: block;
    border: 0;
    background: rgba(24, 34, 28, .34);
    backdrop-filter: blur(2px);
  }

  .topbar {
    min-height: 62px;
    box-sizing: border-box;
    padding: 12px 14px;
  }
}

@media (max-width: 520px) {
  .topbar-title {
    gap: 9px;
  }

  .topbar-title > span {
    max-width: 45vw;
    font-size: 14px;
  }

  .topbar-actions {
    gap: 7px;
  }

  .model-status {
    display: none;
  }
}

</style>
