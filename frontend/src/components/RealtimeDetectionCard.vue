<template>
  <div class="realtime-card">
    <div class="realtime-header">
      <div>
        <div class="realtime-label">{{ tr('realtime.label') }}</div>
        <h3>{{ tr('realtime.title') }}</h3>
      </div>
      <el-tag :type="statusTagType">{{ statusText }}</el-tag>
    </div>

    <div class="preview-wrapper">
      <video ref="videoRef" autoplay playsinline muted class="source-video" />
      <canvas
        ref="canvasRef"
        class="preview-canvas"
        :width="canvasWidth"
        :height="canvasHeight"
      />
      <div v-if="!isRunning" class="preview-placeholder">
        <span class="camera-icon">📹</span>
        <p>
          {{
            hasStopped ? tr('realtime.stopped') : tr('realtime.startHint')
          }}
        </p>
      </div>
    </div>

    <div class="live-stats">
      <div class="stat-item">
        <strong>{{ currentFps }}</strong>
        <span>FPS</span>
      </div>
      <div class="stat-item">
        <strong>{{ inferenceTime }}</strong>
        <span>{{ tr('realtime.inference') }}</span>
      </div>
      <div class="stat-item">
        <strong>{{ objectCount }}</strong>
        <span>{{ tr('realtime.currentTargets') }}</span>
      </div>
      <div class="stat-item">
        <strong>{{ frameCount }}</strong>
        <span>{{ tr('realtime.frames') }}</span>
      </div>
    </div>

    <div v-if="currentDetections.length" class="current-results">
      <div class="section-title">{{ tr('realtime.frameTargets') }}</div>
      <div
        v-for="(detection, index) in currentDetections"
        :key="`${detection.class_name_display || detection.class_name || 'target'}-${index}`"
        class="detection-row"
      >
        <span>{{
          detection.class_name_display || detection.class_name_cn || detection.class_name || detection.label || `目标 ${index + 1}`
        }}</span>
        <strong
          >{{
            toConfidencePercent(detection.confidence ?? detection.conf)
          }}%</strong
        >
      </div>
    </div>

    <div
      v-if="Object.keys(sessionClassCounts).length"
      class="class-distribution"
    >
      <div class="section-title">{{ tr('realtime.sessionClasses') }}</div>
      <div class="class-tags">
        <el-tag
          v-for="(count, className) in sessionClassCounts"
          :key="className"
          type="success"
          size="small"
        >
          {{ className }} {{ count }}
        </el-tag>
      </div>
    </div>

    <div class="config-panel">
      <label>
        {{ tr('realtime.mode') }}
        <el-select
          v-model="detectMode"
          size="small"
          :disabled="isBusy"
          class="mode-select"
        >
          <el-option :label="tr('realtime.cpu')" value="cpu" />
          <el-option :label="tr('realtime.gpu')" value="gpu" />
        </el-select>
      </label>
      <label class="confidence-config">
        {{ tr('realtime.confidence', { value: confThreshold.toFixed(2) }) }}
        <el-slider
          v-model="confThreshold"
          :min="0.1"
          :max="0.9"
          :step="0.05"
          :disabled="isBusy"
        />
      </label>
    </div>

    <div class="card-actions">
      <el-button
        v-if="!isRunning"
        type="success"
        :loading="isConnecting"
        :disabled="isConnecting"
        @click="startCamera"
      >
        {{ hasStopped ? tr('realtime.restart') : tr('realtime.start') }}
      </el-button>
      <el-button v-else type="danger" @click="stopCamera(true)"
        >{{ tr('realtime.stop') }}</el-button
      >
    </div>

    <p class="permission-hint">
      {{ tr('realtime.permission') }}
    </p>
  </div>
</template>

<script setup>
import { createCameraWs } from "@/utils/cameraWs";
import { ElMessage } from "element-plus";
import { computed, onBeforeUnmount, ref } from "vue";
import { useLocaleStore } from "@/stores/locale";
import { t } from "@/utils/i18n";

const localeStore = useLocaleStore();
const tr = (key, params) => t(key, localeStore.locale, params);

const props = defineProps({
  item: {
    type: Object,
    default: () => ({}),
  },
});

const emit = defineEmits(["finished"]);

const videoRef = ref(null);
const canvasRef = ref(null);
const isRunning = ref(false);
const isConnecting = ref(false);
const hasStopped = ref(false);
const detectMode = ref(props.item.config?.mode || "cpu");
const confThreshold = ref(Number(props.item.config?.conf ?? 0.5));
const currentFps = ref(0);
const frameCount = ref(0);
const inferenceTime = ref(0);
const objectCount = ref(0);
const currentDetections = ref([]);
const sessionClassCounts = ref({});
const canvasWidth = ref(640);
const canvasHeight = ref(480);

let cameraWs = null;
let mediaStream = null;
let sessionStartedAt = 0;
let inferenceTotal = 0;
let fpsTotal = 0;
let resultSamples = 0;
let peakObjectCount = 0;

const isBusy = computed(() => isRunning.value || isConnecting.value);
const statusText = computed(() => {
  if (isConnecting.value) return "连接中";
  if (isRunning.value) return "运行中";
  if (hasStopped.value) return "已停止";
  return "待启动";
});
const statusTagType = computed(() => {
  if (isConnecting.value) return "warning";
  if (isRunning.value) return "success";
  return "info";
});

const resetSessionStats = () => {
  currentFps.value = 0;
  frameCount.value = 0;
  inferenceTime.value = 0;
  objectCount.value = 0;
  currentDetections.value = [];
  sessionClassCounts.value = {};
  inferenceTotal = 0;
  fpsTotal = 0;
  resultSamples = 0;
  peakObjectCount = 0;
};

const toConfidencePercent = (value) => {
  const number = Number(value);
  if (!Number.isFinite(number)) return 0;
  return Math.round((number <= 1 ? number * 100 : number) * 10) / 10;
};

const createCameraWsInstance = () => {
  cameraWs = createCameraWs({
    mode: detectMode.value,
    conf: confThreshold.value,
    iou: Number(props.item.config?.iou ?? 0.45),
    sceneId: props.item.config?.sceneId,
    onResult: handleDetectionResult,
    onConfigOk: handleConfigOk,
    onError: handleWsError,
    onClose: handleWsClose,
  });
};

async function startCamera() {
  if (!navigator.mediaDevices?.getUserMedia) {
    ElMessage.error("当前浏览器或访问环境不支持摄像头实时检测");
    return;
  }

  try {
    isConnecting.value = true;
    hasStopped.value = false;
    resetSessionStats();

    mediaStream = await navigator.mediaDevices.getUserMedia({
      video: {
        width: { ideal: 640 },
        height: { ideal: 480 },
        facingMode: { ideal: "environment" },
      },
      audio: false,
    });

    videoRef.value.srcObject = mediaStream;
    await videoRef.value.play();
    canvasWidth.value = videoRef.value.videoWidth || 640;
    canvasHeight.value = videoRef.value.videoHeight || 480;

    createCameraWsInstance();
    cameraWs.connect();
  } catch (error) {
    releaseResources();
    isConnecting.value = false;
    ElMessage.error(`摄像头开启失败：${error.message || error}`);
  }
}

function handleConfigOk() {
  isConnecting.value = false;
  isRunning.value = true;
  sessionStartedAt = Date.now();
  requestAnimationFrame(sendSingleFrame);
}

function handleDetectionResult(data) {
  renderAnnotatedFrame(data.annotatedFrame);
  currentFps.value = Number(data.fps || 0).toFixed(1);
  frameCount.value = data.frameCount || 0;
  inferenceTime.value = Number(data.inferenceTime || 0).toFixed(1);
  objectCount.value = data.objectCount || 0;
  currentDetections.value = data.detections || [];

  inferenceTotal += Number(data.inferenceTime || 0);
  fpsTotal += Number(data.fps || 0);
  resultSamples += 1;
  peakObjectCount = Math.max(peakObjectCount, Number(data.objectCount || 0));

  const nextCounts = { ...sessionClassCounts.value };
  currentDetections.value.forEach((detection) => {
    const name = detection.class_name_display || detection.class_name_cn || detection.class_name || detection.label || "未知目标";
    nextCounts[name] = (nextCounts[name] || 0) + 1;
  });
  sessionClassCounts.value = nextCounts;
}

function handleWsError(message) {
  isConnecting.value = false;
  isRunning.value = false;
  releaseResources();
  ElMessage.error(message);
}

function handleWsClose() {
  isConnecting.value = false;
  if (isRunning.value) {
    isRunning.value = false;
    releaseMediaStream();
  }
}

function sendSingleFrame() {
  if (
    !cameraWs?.isConnected ||
    !videoRef.value ||
    videoRef.value.readyState < 2
  )
    return;

  const targetSize = detectMode.value === "cpu" ? 416 : 640;
  const tempCanvas = document.createElement("canvas");
  tempCanvas.width = targetSize;
  tempCanvas.height = targetSize;
  const context = tempCanvas.getContext("2d");
  const videoWidth = videoRef.value.videoWidth;
  const videoHeight = videoRef.value.videoHeight;
  const scale = Math.min(targetSize / videoWidth, targetSize / videoHeight);
  const x = (targetSize - videoWidth * scale) / 2;
  const y = (targetSize - videoHeight * scale) / 2;

  context.drawImage(
    videoRef.value,
    x,
    y,
    videoWidth * scale,
    videoHeight * scale,
  );
  const base64Data = tempCanvas.toDataURL("image/jpeg", 0.6).split(",")[1];
  cameraWs.sendFrame(base64Data);
}

function renderAnnotatedFrame(annotatedBase64) {
  if (!canvasRef.value || !annotatedBase64) return;

  const image = new Image();
  image.onload = () => {
    if (!canvasRef.value || !isRunning.value) return;
    const context = canvasRef.value.getContext("2d");
    canvasRef.value.width = image.width;
    canvasRef.value.height = image.height;
    context.drawImage(image, 0, 0);
    requestAnimationFrame(sendSingleFrame);
  };
  image.src = annotatedBase64.startsWith("data:")
    ? annotatedBase64
    : `data:image/jpeg;base64,${annotatedBase64}`;
}

const releaseMediaStream = () => {
  if (mediaStream) {
    mediaStream.getTracks().forEach((track) => track.stop());
    mediaStream = null;
  }
  if (videoRef.value) videoRef.value.srcObject = null;
};

const releaseResources = () => {
  const ws = cameraWs;
  cameraWs = null;
  ws?.close();
  releaseMediaStream();
};

const createSessionSummary = (snapshot) => ({
  type: "camera",
  filename: "实时摄像头检测",
  duration_seconds: sessionStartedAt
    ? Number(((Date.now() - sessionStartedAt) / 1000).toFixed(1))
    : 0,
  processed_frames: frameCount.value,
  average_fps: resultSamples
    ? Number((fpsTotal / resultSamples).toFixed(1))
    : 0,
  inference_time: resultSamples
    ? Number((inferenceTotal / resultSamples).toFixed(1))
    : 0,
  total_objects: peakObjectCount,
  total_detection_occurrences: Object.values(sessionClassCounts.value).reduce(
    (sum, count) => sum + count,
    0,
  ),
  class_counts: { ...sessionClassCounts.value },
  annotated_image_url: snapshot,
});

function stopCamera(shouldEmitSummary = false) {
  const hadSession = Boolean(sessionStartedAt && resultSamples);
  const snapshot =
    canvasRef.value && resultSamples
      ? canvasRef.value.toDataURL("image/jpeg", 0.86)
      : "";

  releaseResources();
  isRunning.value = false;
  isConnecting.value = false;
  hasStopped.value = true;

  if (shouldEmitSummary && hadSession) {
    emit("finished", createSessionSummary(snapshot));
    ElMessage.success("实时检测已停止，已生成检测总结");
  }

  sessionStartedAt = 0;
}

onBeforeUnmount(() => {
  stopCamera(false);
});
</script>

<style scoped>
.realtime-card {
  width: 100%;
  max-width: 720px;
  padding: 18px;
  border: 1px solid #d1fae5;
  border-radius: 20px;
  background: white;
  box-shadow: 0 6px 20px rgba(0, 0, 0, 0.06);
}

.realtime-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 14px;
}

.realtime-label {
  color: #15803d;
  font-size: 12px;
  font-weight: 700;
}

.realtime-header h3 {
  margin: 4px 0 0;
  color: #111827;
}

.preview-wrapper {
  position: relative;
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
  min-height: 300px;
  border-radius: 14px;
  background: #111827;
}

.source-video {
  position: absolute;
  width: 1px;
  height: 1px;
  opacity: 0;
  pointer-events: none;
}

.preview-canvas {
  display: block;
  width: 100%;
  height: auto;
}

.preview-placeholder {
  position: absolute;
  inset: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 24px;
  color: #d1d5db;
  text-align: center;
  background: #111827;
}

.camera-icon {
  font-size: 38px;
}

.live-stats {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 8px;
  margin: 12px 0;
}

.stat-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 3px;
  padding: 9px 5px;
  border-radius: 10px;
  background: #f0fdf4;
}

.stat-item strong {
  color: #166534;
}

.stat-item span {
  color: #6b7280;
  font-size: 11px;
}

.current-results,
.class-distribution {
  margin-top: 12px;
}

.section-title {
  margin-bottom: 7px;
  color: #374151;
  font-size: 13px;
  font-weight: 700;
}

.detection-row {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  padding: 7px 9px;
  border-bottom: 1px solid #f3f4f6;
  color: #4b5563;
  font-size: 13px;
}

.detection-row strong {
  color: #15803d;
}

.class-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.config-panel {
  display: grid;
  grid-template-columns: minmax(140px, 0.7fr) minmax(220px, 1.3fr);
  gap: 18px;
  margin-top: 16px;
  padding: 12px;
  border-radius: 12px;
  background: #f9fafb;
}

.config-panel label {
  display: flex;
  align-items: center;
  gap: 10px;
  color: #4b5563;
  font-size: 12px;
  white-space: nowrap;
}

.mode-select {
  min-width: 105px;
}

.confidence-config :deep(.el-slider) {
  flex: 1;
  min-width: 100px;
}

.card-actions {
  display: flex;
  justify-content: flex-end;
  margin-top: 14px;
}

.permission-hint {
  margin: 10px 0 0;
  color: #9ca3af;
  font-size: 11px;
  text-align: right;
}

@media (max-width: 620px) {
  .realtime-card {
    padding: 14px;
  }

  .preview-wrapper {
    min-height: 220px;
  }

  .live-stats {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .config-panel {
    grid-template-columns: 1fr;
  }
}
</style>
