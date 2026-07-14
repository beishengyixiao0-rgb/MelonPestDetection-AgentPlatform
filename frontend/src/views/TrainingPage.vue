<template>
  <div class="training-page">
    <!-- ── 页面标题 ── -->
    <div class="page-header">
      <h2>模型训练与监控</h2>
      <el-button type="primary" @click="showCreateDialog = true">
        <el-icon><Plus /></el-icon>新建训练任务
      </el-button>
    </div>

    <!-- ── 训练任务列表 ── -->
    <el-card class="task-list-card" shadow="never">
      <template #header>
        <div class="card-header">
          <span>训练任务列表</span>
          <el-button text @click="fetchTasks">
            <el-icon><Refresh /></el-icon>刷新
          </el-button>
        </div>
      </template>

      <el-table
        :data="taskList"
        stripe
        style="width: 100%"
        v-loading="loadingTasks"
      >
        <el-table-column prop="task_uuid" label="任务 ID" width="100" />
        <el-table-column prop="model_name" label="模型" width="110" />
        <el-table-column prop="device" label="设备" width="80" />
        <el-table-column label="进度" width="180">
          <template #default="{ row }">
            <el-progress
              :percentage="row.progress"
              :status="
                row.status === 'completed'
                  ? 'success'
                  : row.status === 'failed'
                    ? 'exception'
                    : ''
              "
              :stroke-width="16"
            />
          </template>
        </el-table-column>
        <el-table-column label="Epoch" width="100">
          <template #default="{ row }">
            {{ row.current_epoch }}/{{ row.epochs }}
          </template>
        </el-table-column>
        <el-table-column label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="statusType(row.status)" size="small">
              {{ statusText(row.status) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="创建时间" width="170" />
        <el-table-column label="操作" width="200" fixed="right">
          <template #default="{ row }">
            <el-button
              size="small"
              type="primary"
              text
              @click="selectTask(row)"
            >
              查看记录
            </el-button>
            <el-button
              v-if="row.status === 'running'"
              size="small"
              type="danger"
              text
              @click="stopTask(row.id || row.task_id || row.task_uuid)"
            >
              停止
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- ── 训练记录详情 ── -->
    <el-card v-if="selectedTask" class="monitor-card" shadow="never" v-loading="loadingRecord">
      <template #header>
        <div class="card-header">
          <span>
            训练记录 — 任务 {{ selectedTask.task_uuid || selectedTask.id }}
            <el-tag
              :type="statusType(selectedTask.status)"
              size="small"
              style="margin-left: 8px"
            >
              {{ statusText(selectedTask.status) }}
            </el-tag>
          </span>
          <div class="monitor-info">
            <span>模型: {{ selectedTask.model_name }}</span>
            <span>设备: {{ selectedTask.device }}</span>
            <span
              >Epoch: {{ selectedTask.current_epoch }}/{{
                selectedTask.epochs
              }}</span
            >
          </div>
        </div>
      </template>

      <el-descriptions :column="3" border class="record-descriptions">
        <el-descriptions-item label="数据集">
          {{ selectedTask.dataset_name || selectedTask.dataset_id || "-" }}
        </el-descriptions-item>
        <el-descriptions-item label="模型版本">
          {{ selectedTask.model_name || "-" }}
        </el-descriptions-item>
        <el-descriptions-item label="训练设备">
          {{ selectedTask.device || "-" }}
        </el-descriptions-item>
        <el-descriptions-item label="Epoch">
          {{ selectedTask.current_epoch || 0 }}/{{ selectedTask.epochs || "-" }}
        </el-descriptions-item>
        <el-descriptions-item label="Batch Size">
          {{ selectedTask.batch_size ?? selectedTask.batch ?? "-" }}
        </el-descriptions-item>
        <el-descriptions-item label="图像尺寸">
          {{ selectedTask.img_size ?? selectedTask.image_size ?? "-" }}
        </el-descriptions-item>
        <el-descriptions-item label="学习率">
          {{ selectedTask.lr0 ?? selectedTask.learning_rate ?? "-" }}
        </el-descriptions-item>
        <el-descriptions-item label="优化器">
          {{ selectedTask.optimizer || "-" }}
        </el-descriptions-item>
        <el-descriptions-item label="创建时间">
          {{ selectedTask.created_at || "-" }}
        </el-descriptions-item>
      </el-descriptions>

      <!-- 最新指标卡片 -->
      <el-row :gutter="16" class="metric-cards">
        <el-col :span="4" v-for="item in metricCards" :key="item.label">
          <el-card shadow="hover" class="metric-item">
            <div class="metric-value">{{ item.value }}</div>
            <div class="metric-label">{{ item.label }}</div>
          </el-card>
        </el-col>
      </el-row>

      <!-- 训练曲线图表 -->
      <el-row :gutter="16" style="margin-top: 16px">
        <el-col :span="12">
          <div ref="lossChartRef" style="height: 350px"></div>
        </el-col>
        <el-col :span="12">
          <div ref="mapChartRef" style="height: 350px"></div>
        </el-col>
      </el-row>

      <el-card v-if="evaluation" class="evaluation-card" shadow="never">
        <template #header>
          <div class="card-header">
            <span>最终评估结果</span>
            <el-button v-if="selectedTask.status === 'completed'" text type="primary" @click="downloadBestModel">
              下载最佳模型
            </el-button>
          </div>
        </template>

        <div class="evaluation-grid">
          <div v-for="item in evaluationCards" :key="item.label" class="evaluation-item">
            <span>{{ item.label }}</span>
            <strong>{{ item.value }}</strong>
          </div>
        </div>

        <el-table v-if="perClassMetrics.length" :data="perClassMetrics" size="small" style="margin-top: 16px">
          <el-table-column prop="name" label="病害类别" />
          <el-table-column prop="ap" label="AP" />
          <el-table-column prop="precision" label="Precision" />
          <el-table-column prop="recall" label="Recall" />
        </el-table>
      </el-card>

      <el-collapse v-if="trainingLogs.length" class="log-panel">
        <el-collapse-item title="训练日志" name="logs">
          <pre>{{ trainingLogs.join("\n") }}</pre>
        </el-collapse-item>
      </el-collapse>
    </el-card>

    <!-- ── 新建训练任务对话框 ── -->
    <el-dialog
      v-model="showCreateDialog"
      title="新建训练任务"
      width="600px"
      :close-on-click-modal="false"
    >
      <el-form :model="trainForm" label-width="120px">
        <el-form-item label="检测场景">
          <el-select v-model="trainForm.scene_id" placeholder="选择场景">
            <el-option label="遥感目标检测" :value="1" />
            <el-option label="工业缺陷检测" :value="2" />
            <el-option label="农业病害检测" :value="3" />
          </el-select>
        </el-form-item>

        <el-form-item label="基础模型">
          <el-select v-model="trainForm.model_name">
            <el-option label="YOLO11n (Nano, 最快)" value="yolo11n" />
            <el-option label="YOLO11s (Small)" value="yolo11s" />
            <el-option label="YOLO11m (Medium)" value="yolo11m" />
            <el-option label="YOLO11l (Large)" value="yolo11l" />
            <el-option label="YOLO11x (XLarge, 最强)" value="yolo11x" />
          </el-select>
        </el-form-item>

        <el-form-item label="训练轮数">
          <el-slider
            v-model="trainForm.epochs"
            :min="5"
            :max="500"
            :step="10"
            show-input
          />
        </el-form-item>

        <el-form-item label="批次大小">
          <el-input-number
            v-model="trainForm.batch_size"
            :min="1"
            :max="64"
            :step="2"
          />
        </el-form-item>

        <el-form-item label="图像尺寸">
          <el-select v-model="trainForm.img_size">
            <el-option label="416" :value="416" />
            <el-option label="512" :value="512" />
            <el-option label="640 (默认)" :value="640" />
            <el-option label="768" :value="768" />
          </el-select>
        </el-form-item>

        <el-form-item label="训练设备">
          <el-radio-group v-model="trainForm.device">
            <el-radio value="cpu">CPU (本地)</el-radio>
            <el-radio value="0">GPU:0</el-radio>
            <el-radio value="1">GPU:1</el-radio>
          </el-radio-group>
        </el-form-item>

        <el-form-item label="优化器">
          <el-select v-model="trainForm.optimizer">
            <el-option label="SGD (推荐)" value="SGD" />
            <el-option label="Adam" value="Adam" />
            <el-option label="AdamW" value="AdamW" />
          </el-select>
        </el-form-item>

        <el-form-item label="初始学习率">
          <el-input-number
            v-model="trainForm.lr0"
            :min="0.0001"
            :max="0.1"
            :step="0.001"
            :precision="4"
          />
        </el-form-item>
      </el-form>

      <template #footer>
        <el-button @click="showCreateDialog = false">取消</el-button>
        <el-button type="primary" @click="createTask" :loading="creating">
          启动训练
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import request from "@/utils/request";
import { Plus, Refresh } from "@element-plus/icons-vue";
import * as echarts from "echarts";
import { ElMessage, ElMessageBox } from "element-plus";
import { computed, nextTick, onBeforeUnmount, onMounted, ref } from "vue";

// ── 状态变量 ──
const taskList = ref([]);
const loadingTasks = ref(false);
const selectedTask = ref(null);
const loadingRecord = ref(false);
const evaluation = ref(null);
const trainingLogs = ref([]);
const showCreateDialog = ref(false);
const creating = ref(false);

// ── 图表引用 ──
const lossChartRef = ref(null);
const mapChartRef = ref(null);
let lossChart = null;
let mapChart = null;

// ── 轮询定时器 ──
let pollTimer = null;

// ── 训练表单 ──
const trainForm = ref({
  scene_id: 1,
  model_name: "yolo11n",
  epochs: 50,
  batch_size: 8,
  img_size: 640,
  device: "cpu",
  optimizer: "SGD",
  lr0: 0.01,
});

// ── 计算属性：最新指标卡片 ──
const metricCards = computed(() => {
  if (!selectedTask.value) return [];
  const m = selectedTask.value.latest_metric;
  if (!m)
    return [
      {
        label: "Epoch",
        value: `${selectedTask.value.current_epoch}/${selectedTask.value.epochs}`,
      },
      { label: "进度", value: `${selectedTask.value.progress}%` },
      { label: "Box Loss", value: "-" },
      { label: "Cls Loss", value: "-" },
      { label: "mAP@50", value: "-" },
      { label: "mAP@50-95", value: "-" },
    ];
  return [
    { label: "Epoch", value: `${m.epoch}/${selectedTask.value.epochs}` },
    {
      label: "Box Loss",
      value: m.box_loss != null ? m.box_loss.toFixed(4) : "-",
    },
    {
      label: "Cls Loss",
      value: m.cls_loss != null ? m.cls_loss.toFixed(4) : "-",
    },
    {
      label: "Precision",
      value: m.precision != null ? (m.precision * 100).toFixed(1) + "%" : "-",
    },
    {
      label: "mAP@50",
      value: m.map50 != null ? (m.map50 * 100).toFixed(1) + "%" : "-",
    },
    {
      label: "mAP@50-95",
      value: m.map50_95 != null ? (m.map50_95 * 100).toFixed(1) + "%" : "-",
    },
  ];
});

const formatPercent = (value) => {
  if (value == null || value === "") return "-";
  const number = Number(value);
  if (!Number.isFinite(number)) return value;
  return `${(number <= 1 ? number * 100 : number).toFixed(1)}%`;
};

const evaluationCards = computed(() => {
  if (!evaluation.value) return [];
  const data = evaluation.value.data || evaluation.value;
  return [
    { label: "mAP@50", value: formatPercent(data.map50 ?? data.mAP50) },
    { label: "mAP@50-95", value: formatPercent(data.map50_95 ?? data.mAP50_95) },
    { label: "Precision", value: formatPercent(data.precision) },
    { label: "Recall", value: formatPercent(data.recall) },
  ];
});

const perClassMetrics = computed(() => {
  const data = evaluation.value?.data || evaluation.value || {};
  const rows = data.per_class_ap || data.per_class || data.classes || [];
  if (Array.isArray(rows)) {
    return rows.map((item, index) => ({
      name: item.name || item.class_name || item.label || `类别 ${index + 1}`,
      ap: formatPercent(item.ap ?? item.map50),
      precision: formatPercent(item.precision),
      recall: formatPercent(item.recall),
    }));
  }
  return Object.entries(rows).map(([name, ap]) => ({
    name,
    ap: formatPercent(ap),
    precision: "-",
    recall: "-",
  }));
});

// ── 状态映射 ──
function statusType(status) {
  const map = {
    pending: "info",
    running: "warning",
    completed: "success",
    failed: "danger",
    cancelled: "info",
  };
  return map[status] || "info";
}

function statusText(status) {
  const map = {
    pending: "等待中",
    running: "训练中",
    completed: "已完成",
    failed: "失败",
    cancelled: "已取消",
  };
  return map[status] || status;
}

async function requestWithFallback(method, paths, data, config = {}) {
  let lastError;
  for (const url of paths) {
    try {
      return await request({ method, url, data, ...config });
    } catch (error) {
      lastError = error;
      if (error.response?.status !== 404) throw error;
    }
  }
  throw lastError;
}

// ── 获取任务列表 ──
async function fetchTasks() {
  loadingTasks.value = true;
  try {
    const res = await requestWithFallback("get", [
      "/training/task/list",
      "/training/tasks",
    ]);
    const items = res.items || res.tasks || res.data || [];
    taskList.value = Array.isArray(items) ? items : [];
  } catch (e) {
    console.error("获取任务列表失败", e);
  } finally {
    loadingTasks.value = false;
  }
}

// ── 选择任务并开始监控 ──
async function selectTask(task) {
  loadingRecord.value = true;
  evaluation.value = null;
  trainingLogs.value = [];
  selectedTask.value = { ...task };
  try {
    await nextTick();
    initCharts();
    await Promise.all([fetchMetrics(), fetchEvaluation()]);
    if (["pending", "running"].includes(selectedTask.value?.status)) {
      startPolling();
    } else {
      stopPolling();
    }
  } finally {
    loadingRecord.value = false;
  }
}

// ── 初始化 ECharts 图表 ──
function initCharts() {
  if (lossChart) lossChart.dispose();
  if (mapChart) mapChart.dispose();

  if (lossChartRef.value) {
    lossChart = echarts.init(lossChartRef.value);
  }
  if (mapChartRef.value) {
    mapChart = echarts.init(mapChartRef.value);
  }
}

// ── 获取训练指标并更新图表 ──
async function fetchMetrics() {
  if (!selectedTask.value) return;
  try {
    const taskId = selectedTask.value.id || selectedTask.value.task_id || selectedTask.value.task?.id || selectedTask.value.task_uuid;
    const res = await requestWithFallback("get", [
      `/training/task/log/${taskId}`,
      `/training/metrics/${taskId}`,
    ]);
    const metrics = res.metrics || res.items || res.data?.metrics || [];
    const logs = res.logs || res.log || res.data?.logs || [];
    trainingLogs.value = Array.isArray(logs) ? logs : logs ? [logs] : [];

    // 更新任务状态
    const statusRes = await requestWithFallback("get", [
      `/training/task/status/${taskId}`,
      `/training/status/${taskId}`,
    ]);
    if (statusRes) {
      const taskStatus = statusRes.task || statusRes.data || statusRes;
      selectedTask.value = {
        ...selectedTask.value,
        ...taskStatus,
        latest_metric: statusRes.latest_metric || taskStatus.latest_metric || metrics.at(-1),
      };

      // 同步更新任务列表中的进度（进度条 + Epoch 显示）
      if (taskStatus.id) {
        const idx = taskList.value.findIndex(
          (t) => t.id === taskStatus.id,
        );
        if (idx !== -1) {
          taskList.value[idx] = {
            ...taskList.value[idx],
            progress: taskStatus.progress,
            current_epoch: taskStatus.current_epoch,
            status: taskStatus.status,
          };
        }
      }

      if (!["pending", "running"].includes(taskStatus.status)) {
        stopPolling();
        if (!evaluation.value) fetchEvaluation();
      }
    }

    if (metrics.length > 0) {
      updateCharts(metrics);
    }
  } catch (e) {
    console.error("获取训练指标失败", e);
  }
}

async function fetchEvaluation() {
  if (!selectedTask.value) return;
  const taskId = selectedTask.value.id || selectedTask.value.task_id || selectedTask.value.task?.id || selectedTask.value.task_uuid;
  try {
    evaluation.value = await request.get(`/training/task/eval/${taskId}`);
  } catch (error) {
    if (error.response?.status !== 404) {
      console.error("获取训练评估失败", error);
    }
  }
}

// ── 更新图表 ──
function updateCharts(metrics) {
  const epochs = metrics.map((m) => m.epoch);

  // Loss 曲线
  if (lossChart) {
    lossChart.setOption({
      title: {
        text: "训练损失曲线",
        left: "center",
        textStyle: { fontSize: 14 },
      },
      tooltip: { trigger: "axis" },
      legend: { data: ["Box Loss", "Cls Loss", "DFL Loss"], bottom: 0 },
      grid: { left: "10%", right: "5%", top: "15%", bottom: "15%" },
      xAxis: { type: "category", data: epochs, name: "Epoch" },
      yAxis: { type: "value", name: "Loss" },
      series: [
        {
          name: "Box Loss",
          type: "line",
          data: metrics.map((m) => m.box_loss),
          smooth: true,
          lineStyle: { width: 2 },
        },
        {
          name: "Cls Loss",
          type: "line",
          data: metrics.map((m) => m.cls_loss),
          smooth: true,
          lineStyle: { width: 2 },
        },
        {
          name: "DFL Loss",
          type: "line",
          data: metrics.map((m) => m.dfl_loss),
          smooth: true,
          lineStyle: { width: 2 },
        },
      ],
    });
  }

  // mAP 曲线
  if (mapChart) {
    mapChart.setOption({
      title: {
        text: "评估指标曲线",
        left: "center",
        textStyle: { fontSize: 14 },
      },
      tooltip: { trigger: "axis" },
      legend: {
        data: ["mAP@50", "mAP@50-95", "Precision", "Recall"],
        bottom: 0,
      },
      grid: { left: "10%", right: "5%", top: "15%", bottom: "15%" },
      xAxis: { type: "category", data: epochs, name: "Epoch" },
      yAxis: { type: "value", name: "指标值", max: 1 },
      series: [
        {
          name: "mAP@50",
          type: "line",
          data: metrics.map((m) => m.map50),
          smooth: true,
          lineStyle: { width: 2, color: "#409eff" },
          itemStyle: { color: "#409eff" },
        },
        {
          name: "mAP@50-95",
          type: "line",
          data: metrics.map((m) => m.map50_95),
          smooth: true,
          lineStyle: { width: 2, color: "#67c23a" },
          itemStyle: { color: "#67c23a" },
        },
        {
          name: "Precision",
          type: "line",
          data: metrics.map((m) => m.precision),
          smooth: true,
          lineStyle: { width: 2, type: "dashed", color: "#e6a23c" },
          itemStyle: { color: "#e6a23c" },
        },
        {
          name: "Recall",
          type: "line",
          data: metrics.map((m) => m.recall),
          smooth: true,
          lineStyle: { width: 2, type: "dashed", color: "#f56c6c" },
          itemStyle: { color: "#f56c6c" },
        },
      ],
    });
  }
}

// ── 轮询监控 ──
function startPolling() {
  stopPolling();
  pollTimer = setInterval(() => {
    if (selectedTask.value) {
      fetchMetrics();
    }
  }, 5000); // 每 5 秒轮询一次
}

function stopPolling() {
  if (pollTimer) {
    clearInterval(pollTimer);
    pollTimer = null;
  }
}

// ── 创建训练任务 ──
async function createTask() {
  creating.value = true;
  try {
    let res;
    try {
      const created = await request.post("/training/task/create", trainForm.value);
      const taskId = created.task_id || created.id || created.task?.id;
      if (!taskId) throw new Error("创建任务后未返回任务 ID");
      const started = await request.post(`/training/task/start/${taskId}`);
      res = { ...created, ...started, id: taskId };
    } catch (error) {
      if (error.response?.status !== 404) throw error;
      res = await request.post("/training/start", trainForm.value);
    }

    ElMessage.success(`训练任务已创建：${res.task_uuid || res.task_id || res.id}`);
    showCreateDialog.value = false;
    await fetchTasks();
    // 自动选中新创建的任务
    const newTaskId = res.id || res.task_id || res.task?.id;
    if (newTaskId) {
      const newTask = taskList.value.find((t) => (t.id || t.task_id) === newTaskId);
      if (newTask) selectTask(newTask);
    }
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || "创建训练任务失败");
  } finally {
    creating.value = false;
  }
}

// ── 停止训练任务 ──
async function stopTask(taskId) {
  try {
    await ElMessageBox.confirm(
      "确定要停止当前训练任务吗？训练进度将被保留。",
      "确认停止",
      {
        type: "warning",
      },
    );
    await requestWithFallback("post", [
      `/training/task/stop/${taskId}`,
      `/training/stop/${taskId}`,
    ]);
    ElMessage.success("训练任务已停止");
    await fetchTasks();
  } catch (e) {
    if (e !== "cancel") {
      ElMessage.error("停止训练失败");
    }
  }
}

async function downloadBestModel() {
  if (!selectedTask.value) return;
  const taskId = selectedTask.value.id || selectedTask.value.task_id || selectedTask.value.task_uuid;
  try {
    const blob = await request.get(`/training/task/download/${taskId}`, {
      responseType: "blob",
    });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `${selectedTask.value.task_uuid || taskId}-best.pt`;
    link.click();
    URL.revokeObjectURL(url);
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || "下载模型失败");
  }
}

// ── 生命周期 ──
onMounted(() => {
  fetchTasks();
});

onBeforeUnmount(() => {
  stopPolling();
  if (lossChart) lossChart.dispose();
  if (mapChart) mapChart.dispose();
});
</script>

<style scoped>
.training-page {
  padding: 20px;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.page-header h2 {
  margin: 0;
  font-size: 22px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.monitor-info {
  display: flex;
  gap: 16px;
  font-size: 13px;
  color: #909399;
}

.metric-cards {
  margin-bottom: 8px;
}

.metric-item {
  text-align: center;
  padding: 8px 0;
}

.metric-value {
  font-size: 20px;
  font-weight: 700;
  color: #303133;
}

.metric-label {
  font-size: 12px;
  color: #909399;
  margin-top: 4px;
}

.task-list-card,
.monitor-card {
  margin-bottom: 20px;
}

.record-descriptions {
  margin-bottom: 20px;
}

.evaluation-card {
  margin-top: 20px;
}

.evaluation-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
}

.evaluation-item {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 14px;
  border: 1px solid #e5e7eb;
  border-radius: 12px;
  background: #f9fafb;
}

.evaluation-item span {
  color: #6b7280;
  font-size: 12px;
}

.evaluation-item strong {
  color: #111827;
  font-size: 20px;
}

.log-panel {
  margin-top: 20px;
}

.log-panel pre {
  max-height: 320px;
  margin: 0;
  padding: 14px;
  overflow: auto;
  border-radius: 10px;
  background: #111827;
  color: #d1fae5;
  font-size: 12px;
  line-height: 1.6;
  white-space: pre-wrap;
}

@media (max-width: 900px) {
  .evaluation-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .monitor-info {
    display: none;
  }
}
</style>
