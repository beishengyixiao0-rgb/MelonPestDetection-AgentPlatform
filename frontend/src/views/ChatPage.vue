<template>
  <div class="chat-page">
    <ChatSidebar
      :sessions="sessions"
      :current-session-id="currentSessionId"
      @new-diagnosis="startNewDiagnosis"
      @select-session="handleSelectSession"
      @toggle-pin="handleTogglePin"
      @delete-session="handleDeleteSession"
      @rename-session="handleRenameSession"
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
import { uploadCommonFile } from "@/api/common";
import {
  detectBatch,
  detectSingle,
  detectVideo,
  detectZip,
  getTrainingTasks,
  getVideoStatus,
} from "@/api/detection";
import { ElMessage } from "element-plus";
import { storeToRefs } from "pinia";
import { nextTick, onBeforeUnmount, onMounted, ref } from "vue";

import ChatComposer from "@/components/ChatComposer.vue";
import ChatMessageList from "@/components/ChatMessageList.vue";
import ChatSidebar from "@/components/ChatSidebar.vue";
import { useAgentStore } from "@/stores/agent";
import { streamChat } from "@/utils/stream";

const message = ref("");
const agentStore = useAgentStore();
const { messages, sessions, currentSessionId } = storeToRefs(agentStore);

const uploadQueue = ref([]);
const uploadMode = ref("image");
const inputAccept = ref("image/*");
const inputMultiple = ref(false);
const inputCapture = ref(null);
const showUploadMenu = ref(false);
const showCameraModal = ref(false);
const cameraError = ref("");
const completedTaskId = ref(null);

const chatComposerRef = ref(null);
const chatMessageListRef = ref(null);

const scrollToBottom = async () => {
  await nextTick();
  chatMessageListRef.value?.scrollToBottom();
};

const toggleUploadMenu = () => {
  showUploadMenu.value = !showUploadMenu.value;
};

const setUploadMode = (mode) => {
  uploadMode.value = mode;

  if (mode === "image" || mode === "agent-image") {
    inputAccept.value = "image/*";
    inputMultiple.value = false;
    inputCapture.value = null;
  } else if (mode === "batch") {
    inputAccept.value = "image/*";
    inputMultiple.value = true;
    inputCapture.value = null;
  } else if (mode === "video") {
    inputAccept.value = "video/*";
    inputMultiple.value = false;
    inputCapture.value = null;
  } else if (mode === "camera") {
    inputAccept.value = "image/*";
    inputMultiple.value = false;
    inputCapture.value = "environment";
  }
};

const closeCameraModal = () => {
  showCameraModal.value = false;
  cameraError.value = "";
};

const handleCameraError = (error) => {
  cameraError.value = error;
  showCameraModal.value = false;
  setUploadMode("image");

  nextTick(() => {
    chatComposerRef.value?.openFilePicker();
  });
};

const openUploadMenu = async (mode = "image") => {
  setUploadMode(mode);
  showUploadMenu.value = false;

  if (mode === "camera") {
    showCameraModal.value = true;
    return;
  }

  nextTick(() => {
    chatComposerRef.value?.openFilePicker();
  });
};

const handleUploadModeSelection = (mode) => {
  showUploadMenu.value = false;

  if (mode === "image") {
    handleQuickDetect("single");
    return;
  }

  if (mode === "realtime-camera") {
    startRealtimeDetection();
    return;
  }

  if (mode === "batch") {
    handleQuickDetect("batch");
    return;
  }

  if (mode === "agent-image") {
    openUploadMenu("agent-image");
    return;
  }

  if (mode === "video") {
    handleVideoDetect();
    return;
  }

  openUploadMenu(mode);
};

const startRealtimeDetection = () => {
  agentStore.addMessage({
    role: "user",
    content: "请开启摄像头进行实时检测",
  });
  agentStore.addMessage({
    id: `realtime-${Date.now()}`,
    role: "assistant",
    type: "realtime-detection",
    content: "请确认摄像头权限并开始实时检测",
    config: {
      mode: "cpu",
      conf: 0.25,
      iou: 0.45,
    },
  });
  scrollToBottom();
};

const handleRealtimeFinished = ({ result }) => {
  agentStore.addMessage({
    role: "assistant",
    type: "diagnosis",
    content: `实时检测完成，共处理 ${result.processed_frames ?? 0} 帧。`,
    detectionResult: result,
    annotatedImage: result.annotated_image_url || "",
  });
  scrollToBottom();
};

const handleCameraCapture = (file) => {
  createUploadItem(file);
  closeCameraModal();
};

const removeUploadItem = (id) => {
  const item = uploadQueue.value.find((entry) => entry.id === id);

  if (item?.timer) {
    window.clearInterval(item.timer);
  }

  if (item?.previewUrl) {
    URL.revokeObjectURL(item.previewUrl);
  }

  uploadQueue.value = uploadQueue.value.filter((entry) => entry.id !== id);
};

const getUploadedFileUrl = (result) =>
  result?.url ||
  result?.file_url ||
  result?.object_url ||
  result?.data?.url ||
  result?.data?.file_url ||
  "";

const uploadAttachment = async (item) => {
  item.status = "uploading";
  item.progress = 0;
  item.errorMessage = "";

  const formData = new FormData();
  formData.append("file", item.file);

  try {
    const result = await uploadCommonFile(formData, (progressEvent) => {
      if (!progressEvent.total) return;
      item.progress = Math.min(
        99,
        Math.round((progressEvent.loaded / progressEvent.total) * 100),
      );
    });

    item.progress = 100;
    item.status = "success";
    item.uploadResult = result;
    item.uploadUrl = getUploadedFileUrl(result);

    // Agent 附件留在输入区；其他原有通道继续完成后的处理。
    if (item.mode !== "agent-image") {
      completeUpload(item, item.file);
    }
  } catch (error) {
    item.status = "error";
    item.errorMessage = getErrorMessage(error);
  }
};

const retryUploadItem = (id) => {
  const item = uploadQueue.value.find((entry) => entry.id === id);
  if (item) uploadAttachment(item);
};

const createUploadItem = (file) => {
  const isVideo = file.type.startsWith("video/");
  const previewUrl = URL.createObjectURL(file);

  const item = {
    id: `${Date.now()}-${Math.random().toString(16).slice(2)}`,
    name: file.name,
    type: isVideo ? "video" : "image",
    previewUrl,
    progress: 0,
    status: "uploading",
    mode: uploadMode.value,
    modeLabel:
      uploadMode.value === "agent-image"
        ? "Agent attachment"
        : uploadMode.value === "batch"
          ? "Batch"
          : uploadMode.value === "video"
            ? "Video"
            : uploadMode.value === "camera"
              ? "Camera"
              : "Single",
    file,
    uploadResult: null,
    uploadUrl: "",
    errorMessage: "",
  };

  uploadQueue.value.unshift(item);
  uploadAttachment(item);
};

const handleFileSelection = (files) => {
  const normalizedFiles = Array.from(files || []);

  if (!normalizedFiles.length) return;

  const selectedFiles =
    uploadMode.value === "batch"
      ? normalizedFiles
      : normalizedFiles.slice(0, 1);

  selectedFiles.forEach((file) => createUploadItem(file));
};

/**
 * 快捷检测：选择文件后直接调用检测 API，不经过 LLM 对话。
 * 由页面底部输入栏的上传菜单触发。
 */
async function handleQuickDetect(type) {
  const input = document.createElement("input");
  input.type = "file";
  input.accept = type === "batch" ? "image/*,.zip" : "image/*";
  input.multiple = type === "batch";

  input.onchange = async (event) => {
    const files = Array.from(event.target?.files || []);
    if (!files.length) return;

    if (type === "single") {
      const file = files[0];
      const imagePreview = URL.createObjectURL(file);

      agentStore.addMessage({
        role: "user",
        type: "image",
        content: `[快捷检测] ${file.name}`,
        image: file.name,
        imagePreview,
        imageUrl: imagePreview,
      });

      agentStore.addMessage({
        role: "assistant",
        content: "正在检测中...",
        loading: true,
      });
      const loadingMessage =
        agentStore.messages[agentStore.messages.length - 1];
      scrollToBottom();

      const formData = new FormData();
      formData.append("file", file);

      try {
        if (!completedTaskId.value) {
          const taskResponse = await getTrainingTasks();
          const tasks = taskResponse.items || taskResponse.tasks || [];
          const completedTask = tasks.find(
            (task) => task.status === "completed",
          );

          if (!completedTask) {
            throw new Error("当前账号下没有可用的已完成模型");
          }

          completedTaskId.value = completedTask.id || completedTask.task_id;
        }

        formData.append("task_id", completedTaskId.value);
        formData.append("conf", "0.25");
        formData.append("iou", "0.45");

        const result = await detectSingle(formData);
        loadingMessage.content = `检测完成！发现 ${result.total_objects ?? 0} 个目标。`;
        loadingMessage.loading = false;
        loadingMessage.type = "diagnosis";
        loadingMessage.detectionResult = result;
        loadingMessage.annotatedImage = result.annotated_image
          ? `data:image/jpeg;base64,${result.annotated_image}`
          : result.annotated_image_url || result.result_image_url || "";
      } catch (error) {
        loadingMessage.content = `检测失败：${getErrorMessage(error)}`;
        loadingMessage.loading = false;
        loadingMessage.error = true;
      }

      scrollToBottom();
      return;
    }

    const isZip =
      files.length === 1 && files[0].name.toLowerCase().endsWith(".zip");
    const formData = new FormData();

    if (isZip) {
      formData.append("file", files[0]);
      agentStore.addMessage({
        role: "user",
        content: `[快捷检测] ZIP: ${files[0].name}`,
      });
    } else {
      files.forEach((file) => formData.append("files", file));
      agentStore.addMessage({
        role: "user",
        content: `[快捷检测] ${files.length} 张图片`,
        images: files.map((file) => URL.createObjectURL(file)),
      });
    }

    agentStore.addMessage({
      role: "assistant",
      content: "正在批量检测中...",
      loading: true,
    });
    const loadingMessage = agentStore.messages[agentStore.messages.length - 1];
    scrollToBottom();

    try {
      const result = await (isZip
        ? detectZip(formData)
        : detectBatch(formData));

      if (result.error) {
        loadingMessage.content = `批量检测失败：${result.error}`;
        loadingMessage.loading = false;
        loadingMessage.error = true;
        scrollToBottom();
        return;
      }

      const displayResult =
        !isZip && Array.isArray(result.annotated_images)
          ? {
              ...result,
              annotated_images: result.annotated_images.map((image, index) => ({
                ...image,
                original_filename: files[index]?.name || image.image_path,
              })),
            }
          : result;

      loadingMessage.content = `批量检测完成！共 ${displayResult.total_objects ?? 0} 个目标。`;
      loadingMessage.loading = false;
      loadingMessage.type = "diagnosis";
      loadingMessage.detectionResult = displayResult;
      loadingMessage.annotatedImage =
        displayResult.annotated_image_url ||
        displayResult.result_image_url ||
        "";
    } catch (error) {
      loadingMessage.content = `批量检测失败：${getErrorMessage(error)}`;
      loadingMessage.loading = false;
      loadingMessage.error = true;
    }

    scrollToBottom();
  };

  input.click();
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
const VIDEO_POLL_INTERVAL = 1500;
const VIDEO_POLL_MAX_ATTEMPTS = 200;
const activeVideoPolls = new Set();

const waitForNextVideoPoll = () =>
  new Promise((resolve) => window.setTimeout(resolve, VIDEO_POLL_INTERVAL));

const normalizeVideoResult = (payload, taskId) => {
  const nestedResult =
    payload?.result ||
    payload?.detection_result ||
    payload?.data?.result ||
    (payload?.data && typeof payload.data === "object" ? payload.data : null);
  const result =
    nestedResult && typeof nestedResult === "object" ? nestedResult : payload;

  return {
    ...result,
    type: "video",
    task_id: result?.task_id ?? taskId,
  };
};

async function pollVideoProgress(taskId, loadingMessage) {
  const pollToken = Symbol(`video-${taskId}`);
  activeVideoPolls.add(pollToken);

  try {
    for (let attempt = 0; attempt < VIDEO_POLL_MAX_ATTEMPTS; attempt += 1) {
      if (!activeVideoPolls.has(pollToken)) return null;

      const payload = (await getVideoStatus(taskId)) || {};
      const status = String(
        payload.status || payload.state || "",
      ).toLowerCase();
      const progress = Number(payload.progress ?? payload.percent ?? 0);
      const progressPercent =
        progress > 0 && progress <= 1 ? progress * 100 : progress;

      if (payload.error) {
        throw new Error(payload.error);
      }

      if (Number.isFinite(progressPercent) && progressPercent > 0) {
        loadingMessage.content = `视频处理中... ${Math.min(100, Math.round(progressPercent))}%`;
      } else {
        loadingMessage.content = payload.message || "视频已上传，正在处理中...";
      }

      if (
        [
          "completed",
          "complete",
          "success",
          "succeeded",
          "finished",
          "done",
        ].includes(status)
      ) {
        const result = normalizeVideoResult(payload, taskId);
        loadingMessage.content = `视频检测完成！共发现 ${result.total_objects ?? 0} 个目标。`;
        loadingMessage.loading = false;
        loadingMessage.type = "diagnosis";
        loadingMessage.detectionResult = result;
        scrollToBottom();
        return result;
      }

      if (
        ["failed", "failure", "error", "cancelled", "canceled"].includes(status)
      ) {
        throw new Error(payload.message || payload.detail || "视频处理失败");
      }

      await waitForNextVideoPoll();
    }

    throw new Error("视频处理超时，请稍后重试");
  } finally {
    activeVideoPolls.delete(pollToken);
  }
}

async function handleVideoDetect() {
  const input = document.createElement("input");

  input.type = "file";
  input.accept = "video/mp4,video/avi,video/quicktime,video/x-msvideo";

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
      content: `[视频检测] ${file.name} (${(file.size / (1024 * 1024)).toFixed(
        1,
      )} MB)`,
      videoUrl,
    });

    // 添加加载占位消息
    agentStore.addMessage({
      role: "assistant",
      content: "正在上传视频...",
      loading: true,
    });
    const loadingMessage = agentStore.messages[agentStore.messages.length - 1];
    scrollToBottom();

    const formData = new FormData();
    formData.append("file", file);

    try {
      // 上传视频
      const uploadResult = await detectVideo(formData);
      const taskId = uploadResult.task_id;

      if (!taskId) {
        throw new Error("后端未返回视频检测 task_id");
      }

      // 更新加载提示
      loadingMessage.content = "视频已上传，正在处理中...";

      // 轮询检测进度
      await pollVideoProgress(taskId, loadingMessage);
    } catch (error) {
      console.error("[视频检测失败]", error);

      loadingMessage.content = `视频检测失败：${getErrorMessage(error)}`;

      loadingMessage.loading = false;
      loadingMessage.error = true;
    }
  };

  input.click();
}

const getErrorMessage = (error) =>
  error?.response?.data?.detail ||
  error?.response?.data?.message ||
  error?.message ||
  "请重试";

const completeUpload = (item, file) => {
  const isVideo = item.type === "video";
  const uploadMessage = {
    role: "user",
    type: isVideo ? "video" : "image",
    imageUrl: isVideo ? "" : item.previewUrl,
    videoUrl: isVideo ? item.previewUrl : "",
    content: file.name,
  };

  agentStore.addMessage(uploadMessage);
  scrollToBottom();

  window.setTimeout(() => {
    agentStore.addMessage({
      role: "assistant",
      type: "diagnosis",
      disease: isVideo ? "Video inspection queued" : "Tomato Late Blight",
      plant: isVideo ? "Crop stream" : "Tomato",
      severity: isVideo ? "Medium" : "High",
      confidence: isVideo ? 88.4 : 94.2,
      annotatedImage: item.previewUrl,
      description: isVideo
        ? "The uploaded video clip has been received and is ready for plant disease inspection."
        : "The uploaded image shows symptoms consistent with Tomato Late Blight, including dark lesions and leaf deterioration.",
      treatments: [
        "Inspect the affected leaves closely",
        "Apply the recommended treatment plan",
        "Monitor the plant over the next few days",
      ],
    });
    scrollToBottom();
  }, 600);
};

const sendMessage = async () => {
  const content = message.value.trim();
  const attachments = uploadQueue.value.filter(
    (item) => item.mode === "agent-image",
  );

  if (!content && !attachments.length) return;
  if (attachments.some((item) => item.status !== "success")) return;

  agentStore.abort();

  const attachmentData = attachments.map((item) => ({
    name: item.name,
    type: item.file.type,
    url: item.uploadUrl,
    upload: item.uploadResult,
  }));

  const userMessage = {
    role: "user",
    content: content || "请帮我分析这张图片",
  };

  if (attachments.length === 1) {
    userMessage.type = "image";
    userMessage.imageUrl = attachments[0].previewUrl;
  } else if (attachments.length > 1) {
    userMessage.images = attachments.map((item) => item.previewUrl);
  }

  agentStore.addMessage(userMessage);

  agentStore.addMessage({
    role: "assistant",
    content: "",
    loading: true,
  });
  const assistantMessage = agentStore.messages[agentStore.messages.length - 1];
  agentStore.setLoading(true);

  scrollToBottom();

  message.value = "";
  // 从输入区移除，但不释放 blob URL，因为它已用于消息预览。
  uploadQueue.value = uploadQueue.value.filter(
    (item) => item.mode !== "agent-image",
  );

  const imagePath = attachments.length === 1 ? attachments[0].uploadUrl : null;
  const imagePaths =
    attachments.length > 1 ? attachments.map((item) => item.uploadUrl) : null;

  const stop = streamChat(
    "/api/chat/stream",
    {
      message: userMessage.content,
      session_id: agentStore.currentSessionId,
      image_path: imagePath,
      image_paths: imagePaths,
    },
    {
      onMessage: (event) => {
        if (event.type === "text_chunk" || typeof event.content === "string") {
          assistantMessage.content += event.content || "";
        }

        if (event.session_id) {
          agentStore.currentSessionId = event.session_id;
        }

        if (
          event.type === "diagnosis" ||
          event.detectionResult ||
          event.result
        ) {
          assistantMessage.type = "diagnosis";
          assistantMessage.detectionResult =
            event.detectionResult || event.result;
        }

        scrollToBottom();
      },
      onDone: async () => {
        assistantMessage.loading = false;
        agentStore.setLoading(false);
        agentStore.abortController = null;

        if (!assistantMessage.content && !assistantMessage.detectionResult) {
          assistantMessage.content = "分析已完成";
        }

        await agentStore.loadSessions();
        scrollToBottom();
      },
      onError: (error) => {
        assistantMessage.loading = false;
        assistantMessage.error = true;
        assistantMessage.content = `Agent 请求失败：${getErrorMessage(error)}`;
        agentStore.setLoading(false);
        agentStore.abortController = null;
        scrollToBottom();
      },
    },
  );

  agentStore.abortController = stop;
};

onMounted(async () => {
  await agentStore.loadSessions();

  const pendingPrompt = agentStore.consumePendingPrompt();

  if (!pendingPrompt?.content) return;

  message.value = pendingPrompt.content;
  await nextTick();
  await sendMessage();
});

onBeforeUnmount(() => {
  activeVideoPolls.clear();
});

const useSuggestion = (text) => {
  message.value = text;
  sendMessage();
};

const startNewDiagnosis = () => {
  messages.value.forEach((item) => {
    if (item.imagePreview?.startsWith("blob:"))
      URL.revokeObjectURL(item.imagePreview);
    if (item.imageUrl?.startsWith("blob:")) URL.revokeObjectURL(item.imageUrl);
    item.images?.forEach((url) => {
      if (url.startsWith("blob:")) URL.revokeObjectURL(url);
    });
  });
  agentStore.newChat();
  uploadQueue.value.forEach((item) => {
    if (item.timer) {
      window.clearInterval(item.timer);
    }
    if (item.previewUrl) {
      URL.revokeObjectURL(item.previewUrl);
    }
  });
  uploadQueue.value = [];
  message.value = "";
  showUploadMenu.value = false;
  showCameraModal.value = false;
  cameraError.value = "";
};

const handleSelectSession = async (sessionId) => {
  messages.value.forEach((item) => {
    if (item.imagePreview?.startsWith("blob:"))
      URL.revokeObjectURL(item.imagePreview);
    if (item.imageUrl?.startsWith("blob:")) URL.revokeObjectURL(item.imageUrl);
    item.images?.forEach((url) => {
      if (url.startsWith("blob:")) URL.revokeObjectURL(url);
    });
  });
  await agentStore.loadSessionMessages(sessionId);
  uploadQueue.value.forEach((item) => {
    if (item.timer) {
      window.clearInterval(item.timer);
    }
    if (item.previewUrl) {
      URL.revokeObjectURL(item.previewUrl);
    }
  });
  uploadQueue.value = [];
  message.value = "";
  showUploadMenu.value = false;
  showCameraModal.value = false;
  cameraError.value = "";
};

const handleTogglePin = async (sessionId) => {
  await agentStore.togglePinSession(sessionId);
};

const handleDeleteSession = async (sessionId) => {
  if (confirm("确定要删除这个会话吗？")) {
    await agentStore.deleteSession(sessionId);
    uploadQueue.value.forEach((item) => {
      if (item.timer) {
        window.clearInterval(item.timer);
      }
      if (item.previewUrl) {
        URL.revokeObjectURL(item.previewUrl);
      }
    });
    uploadQueue.value = [];
    message.value = "";
    showUploadMenu.value = false;
    showCameraModal.value = false;
    cameraError.value = "";
  }
};

const handleRenameSession = async (sessionId, newTitle) => {
  await agentStore.renameSession(sessionId, newTitle);
};
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
