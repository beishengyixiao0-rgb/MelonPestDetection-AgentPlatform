<template>
  <div class="chat-footer">
    <input
      ref="fileInputRef"
      type="file"
      :accept="inputAccept"
      :multiple="inputMultiple"
      :capture="inputCapture"
      style="display: none"
      @change="handleFileSelection"
    />

    <div v-if="uploadQueue.length" class="upload-panel">
      <div v-for="item in uploadQueue" :key="item.id" class="upload-item">
        <div class="upload-item-main">
          <div
            class="upload-preview"
            v-if="item.type === 'image' && item.previewUrl"
          >
            <img :src="item.previewUrl" alt="preview" />
          </div>
          <div class="upload-preview video-preview" v-else>
            <span>{{ item.type === "video" ? "🎬" : "📷" }}</span>
          </div>

          <div class="upload-info">
            <div class="upload-name">{{ item.name }}</div>
            <div class="upload-meta">
              {{ item.type === "video" ? "Video" : "Image" }} •
              {{ item.modeLabel }}
            </div>
            <div class="upload-progress-track">
              <div
                class="upload-progress-bar"
                :style="{ width: item.progress + '%' }"
              />
            </div>
            <div class="upload-status">
              <span v-if="item.status === 'uploading'"
                >Uploading… {{ item.progress }}%</span
              >
              <span
                v-else-if="
                  item.status === 'success' && item.mode === 'agent-image'
                "
                class="success-text"
                >上传成功，可输入内容后发送 ✓</span
              >
              <span v-else-if="item.status === 'success'" class="success-text"
                >Upload complete ✓</span
              >
              <span v-else class="error-text">{{
                item.errorMessage || "上传失败"
              }}</span>
            </div>
          </div>
        </div>

        <div class="upload-item-actions">
          <button
            v-if="item.status === 'error'"
            class="retry-upload"
            @click="$emit('retry-upload', item.id)"
          >
            重试
          </button>
          <button
            class="upload-remove"
            @click="$emit('remove-upload-item', item.id)"
            aria-label="Remove upload"
          >
            ×
          </button>
        </div>
      </div>
    </div>

    <div v-if="showUploadMenu" class="upload-menu">
      <button
        class="upload-option primary"
        @click="$emit('select-upload-mode', 'agent-image')"
      >
        📎 添加图片到 Agent 对话
      </button>
      <button
        class="upload-option"
        @click="$emit('select-upload-mode', 'image')"
      >
        ⚡ 快捷单图检测
      </button>
      <button
        class="upload-option"
        @click="$emit('select-upload-mode', 'realtime-camera')"
      >
        📡 实时摄像头检测
      </button>
      <button
        class="upload-option"
        @click="$emit('select-upload-mode', 'batch')"
      >
        🗂️ 快捷批量检测（图片 / ZIP）
      </button>
      <button
        class="upload-option"
        @click="$emit('select-upload-mode', 'video')"
      >
        🎬 视频检测
      </button>
      <button
        class="upload-option"
        @click="$emit('select-upload-mode', 'camera')"
      >
        📹 相机拍摄
      </button>
    </div>

    <div v-if="showCameraModal" class="camera-modal">
      <div class="camera-panel">
        <div class="camera-header">
          <strong>Camera capture</strong>
          <button
            class="upload-remove"
            @click="$emit('close-camera')"
            aria-label="Close camera"
          >
            ×
          </button>
        </div>
        <video
          ref="cameraVideoRef"
          autoplay
          playsinline
          muted
          class="camera-video"
        />
        <canvas ref="cameraCanvasRef" class="camera-canvas" />
        <div class="camera-actions">
          <button class="upload-option" @click="$emit('close-camera')">
            Cancel
          </button>
          <button class="upload-option primary" @click="captureCameraPhoto">
            Capture
          </button>
        </div>
        <div v-if="cameraError" class="camera-error">{{ cameraError }}</div>
      </div>
    </div>

    <div class="input-wrapper">
      <button class="image-btn" @click="$emit('toggle-upload-menu')">📎</button>

      <textarea
        :value="modelValue"
        placeholder="Describe symptoms or upload a plant photo..."
        @input="$emit('update:modelValue', $event.target.value)"
        @keydown.enter.exact.prevent="$emit('send-message')"
      />

      <button class="send-btn" @click="$emit('send-message')">➤</button>
    </div>

    <div class="input-tip">
      Press Enter to send • Supports JPEG, PNG, WebP, MP4 and camera capture
    </div>
  </div>
</template>

<script setup>
import { nextTick, ref, watch } from "vue";

const props = defineProps({
  modelValue: {
    type: String,
    default: "",
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
    default: "image/*",
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
    default: "",
  },
});

const emit = defineEmits([
  "update:modelValue",
  "toggle-upload-menu",
  "select-upload-mode",
  "remove-upload-item",
  "retry-upload",
  "file-selected",
  "close-camera",
  "capture-camera",
  "send-message",
  "camera-error",
]);

const fileInputRef = ref(null);
const cameraVideoRef = ref(null);
const cameraCanvasRef = ref(null);
const cameraStreamRef = ref(null);

const handleFileSelection = (event) => {
  const files = Array.from(event.target.files || []);
  emit("file-selected", files);
  event.target.value = "";
};

const stopCameraStream = () => {
  if (cameraStreamRef.value) {
    cameraStreamRef.value.getTracks().forEach((track) => track.stop());
    cameraStreamRef.value = null;
  }
};

const startCameraStream = async () => {
  if (!props.showCameraModal) {
    stopCameraStream();
    return;
  }

  if (!navigator.mediaDevices?.getUserMedia) {
    emit(
      "camera-error",
      "This browser does not support camera capture. Falling back to file selection.",
    );
    return;
  }

  try {
    stopCameraStream();
    const stream = await navigator.mediaDevices.getUserMedia({
      video: { facingMode: "environment" },
      audio: false,
    });

    cameraStreamRef.value = stream;
    await nextTick();

    if (cameraVideoRef.value) {
      cameraVideoRef.value.srcObject = stream;
      await cameraVideoRef.value.play();
    }
  } catch (error) {
    emit(
      "camera-error",
      "Unable to access the camera. Please select a file instead.",
    );
  }
};

watch(
  () => props.showCameraModal,
  async (visible) => {
    if (visible) {
      await startCameraStream();
    } else {
      stopCameraStream();
    }
  },
);

const captureCameraPhoto = () => {
  const video = cameraVideoRef.value;
  const canvas = cameraCanvasRef.value;

  if (!video || !canvas) return;

  const width = video.videoWidth || 1280;
  const height = video.videoHeight || 720;

  canvas.width = width;
  canvas.height = height;
  const context = canvas.getContext("2d");
  context?.drawImage(video, 0, 0, width, height);

  canvas.toBlob(
    (blob) => {
      if (!blob) return;

      const file = new File([blob], `camera-capture-${Date.now()}.jpg`, {
        type: "image/jpeg",
      });

      emit("capture-camera", file);
      emit("close-camera");
      stopCameraStream();
    },
    "image/jpeg",
    0.92,
  );
};

const openFilePicker = () => {
  fileInputRef.value?.click();
};

defineExpose({ openFilePicker });
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
</style>
