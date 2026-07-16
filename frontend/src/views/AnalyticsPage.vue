<template>
  <div class="analysis-page">
    <header class="analysis-header">
      <div class="header-left">
        <router-link to="/" class="back-btn"> ← </router-link>

        <div class="title-row">
          <div class="title-icon">🌿</div>
          <div>
            <div class="title">Disease Analytics</div>
            <div class="subtitle">Crop disease monitoring overview</div>
          </div>
        </div>
      </div>

      <div class="header-right">
        <router-link to="/ai-chat" class="nav-btn"> 🤖 AI Agent </router-link>
        <router-link to="/history" class="nav-btn"> 🕒 History </router-link>
      </div>
    </header>

    <div class="analysis-container">
      <section class="metrics-grid">
        <div v-for="metric in metrics" :key="metric.label" class="metric-card">
          <div class="metric-top">
            <div class="metric-label">
              {{ metric.label }}
            </div>
            <div
              class="metric-icon"
              :class="metric.up ? 'positive' : 'negative'"
            >
              {{ metric.up ? "↗" : "↘" }}
            </div>
          </div>

          <div class="metric-value">
            {{ metric.value }}
          </div>

          <div
            class="metric-change"
            :class="metric.up ? 'positive' : 'negative'"
          >
            {{ metric.sub }}
          </div>
        </div>
      </section>

      <section class="charts-grid">
        <div class="chart-card">
          <div class="section-header">
            <div class="section-title-row">
              <div class="section-icon">📊</div>
              <div>
                <h2>Disease Distribution</h2>
                <p>By detection count, last 30 days</p>
              </div>
            </div>
          </div>

          <div class="distribution-list">
            <VChart class="chart" :option="pieOption" />

            <div class="legend-list">
              <div
                v-for="item in diseaseDistribution"
                :key="item.name"
                class="distribution-item"
              >
                <div class="legend-left">
                  <span
                    class="legend-dot"
                    :style="{ background: item.color }"
                  />
                  <span>{{ item.name }}</span>
                </div>
                <span class="legend-value">{{ item.value }}%</span>
              </div>
            </div>
          </div>
        </div>

        <div class="chart-card">
          <div class="section-header">
            <div class="section-title-row">
              <div class="section-icon">📈</div>
              <div>
                <h2>Detection Trend</h2>
                <p>Monthly detections vs identifications, 2026</p>
              </div>
            </div>
          </div>

          <VChart class="chart" :option="lineOption" />
        </div>
      </section>

      <section class="bottom-grid">
        <div class="panel-card">
          <div class="section-header">
            <div class="section-title-row">
              <div class="section-icon">🏆</div>
              <div>
                <h2>Top Diseases</h2>
                <p>Ranked by detection volume</p>
              </div>
            </div>
          </div>

          <div class="top-diseases-list">
            <div
              v-for="(disease, index) in topDiseases"
              :key="disease.name"
              class="rank-item"
            >
              <div class="rank-badge">{{ index + 1 }}</div>
              <div class="rank-content">
                <div class="rank-row">
                  <span class="rank-name">{{ disease.name }}</span>
                  <span
                    class="rank-change"
                    :class="disease.change > 0 ? 'positive' : 'negative'"
                  >
                    {{ disease.change > 0 ? "+" : "" }}{{ disease.change }}%
                  </span>
                </div>
                <div class="progress-bar compact">
                  <div
                    class="progress-fill"
                    :style="{
                      width: `${(disease.count / (disease.max_count || 1)) * 100}%`,
                      background: disease.color,
                    }"
                  />
                </div>
                <span class="rank-meta"
                  >{{ disease.count.toLocaleString() }} cases</span
                >
              </div>
            </div>
          </div>
        </div>

        <div class="panel-card">
          <div class="section-header">
            <div class="section-title-row">
              <div class="section-icon">⚠️</div>
              <div>
                <h2>Severity Breakdown</h2>
                <p>By severity level, this week</p>
              </div>
            </div>
          </div>

          <div class="severity-list">
            <div
              v-for="item in severitySummary"
              :key="item.label"
              class="severity-item"
            >
              <div class="severity-label-row">
                <span>{{ item.label }}</span>
                <span>{{ item.value }}%</span>
              </div>
              <div class="progress-bar compact">
                <div
                  class="progress-fill"
                  :style="{ width: `${item.value}%`, background: item.color }"
                />
              </div>
            </div>
          </div>
        </div>

        <div class="panel-card">
          <div class="section-header">
            <div class="section-title-row">
              <div class="section-icon">🎯</div>
              <div>
                <h2>Model Performance</h2>
                <p>YOLO v11 + LLM classifier metrics</p>
              </div>
            </div>
          </div>

          <div
            v-for="item in modelPerformance"
            :key="item.label"
            class="performance-item"
          >
            <div class="performance-header">
              <span>{{ item.label }}</span>
              <span>{{ item.value }}%</span>
            </div>

            <div class="progress-bar">
              <div
                class="progress-fill"
                :style="{ width: item.value + '%', background: item.color }"
              />
            </div>
          </div>

          <div class="performance-footer">
            <div class="footer-row">
              <span>Dataset</span>
              <strong>12,847 samples</strong>
            </div>
            <div class="footer-row">
              <span>Last trained</span>
              <strong>Jul 5, 2026</strong>
            </div>
            <div class="footer-row">
              <span>Classes</span>
              <strong>35 diseases</strong>
            </div>
          </div>
        </div>
      </section>
    </div>
  </div>
</template>

<script setup>
import request from "@/utils/request";
import { LineChart, PieChart } from "echarts/charts";
import {
  GridComponent,
  LegendComponent,
  TooltipComponent,
} from "echarts/components";
import { use } from "echarts/core";
import { CanvasRenderer } from "echarts/renderers";
import { computed, onMounted, ref } from "vue";
import VChart from "vue-echarts";

use([
  CanvasRenderer,
  PieChart,
  LineChart,
  TooltipComponent,
  LegendComponent,
  GridComponent,
]);

const loading = ref(true);

const summary = ref({
  total_detections: 0,
  detection_change: 0,
  diseases_identified: 0,
  identification_rate: 0,
  model_accuracy: 0,
  accuracy_change: 0,
  avg_confidence: 0,
  confidence_change: 0,
});

const diseaseDistribution = ref([]);
const trendData = ref([]);
const modelPerformance = ref([]);
const topDiseases = ref([]);

const severitySummary = ref([
  { label: "High", value: 0, color: "#ef4444" },
  { label: "Moderate", value: 0, color: "#f59e0b" },
  { label: "Low", value: 0, color: "#16a34a" },
]);

const metrics = computed(() => [
  {
    label: "Total Detections",
    value: summary.value.total_detections.toLocaleString(),
    sub:
      summary.value.detection_change !== 0
        ? `${summary.value.detection_change > 0 ? "+" : ""}${summary.value.detection_change}% vs last month`
        : "No change",
    up: summary.value.detection_change >= 0,
  },
  {
    label: "Diseases Identified",
    value: summary.value.diseases_identified.toLocaleString(),
    sub: `${summary.value.identification_rate}% identification rate`,
    up: summary.value.identification_rate > 0,
  },
  {
    label: "Model Accuracy",
    value: `${summary.value.model_accuracy}%`,
    sub:
      summary.value.accuracy_change !== 0
        ? `${summary.value.accuracy_change > 0 ? "+" : ""}${summary.value.accuracy_change}% from last version`
        : "No change",
    up: summary.value.accuracy_change >= 0,
  },
  {
    label: "Avg Confidence",
    value: `${summary.value.avg_confidence}%`,
    sub:
      summary.value.confidence_change !== 0
        ? `${summary.value.confidence_change > 0 ? "" : ""}${summary.value.confidence_change}% this week`
        : "No change",
    up: summary.value.confidence_change >= 0,
  },
]);

const pieOption = computed(() => ({
  tooltip: {
    trigger: "item",
    formatter: "{b}: {d}%",
  },
  series: [
    {
      type: "pie",
      radius: ["58%", "78%"],
      center: ["50%", "50%"],
      emphasis: {
        scale: true,
        scaleSize: 8,
      },
      itemStyle: {
        borderRadius: 8,
        borderColor: "#ffffff",
        borderWidth: 2,
      },
      data: diseaseDistribution.value.map((item) => ({
        value: item.value,
        name: item.name,
        itemStyle: {
          color: item.color,
        },
      })),
    },
  ],
}));

const lineOption = computed(() => ({
  tooltip: {
    trigger: "axis",
    axisPointer: {
      type: "cross",
    },
  },
  legend: {
    top: 0,
    textStyle: {
      color: "#6b7280",
    },
  },
  grid: {
    left: "8%",
    right: "4%",
    top: "18%",
    bottom: "10%",
  },
  xAxis: {
    type: "category",
    data: trendData.value.map((item) => item.month),
    axisLine: { show: false },
    axisTick: { show: false },
    axisLabel: {
      color: "#6b7280",
    },
  },
  yAxis: {
    type: "value",
    axisLine: { show: false },
    axisTick: { show: false },
    splitLine: {
      lineStyle: {
        color: "rgba(0, 0, 0, 0.06)",
      },
    },
    axisLabel: {
      color: "#6b7280",
    },
  },
  series: [
    {
      name: "Total Detections",
      type: "line",
      smooth: true,
      lineStyle: {
        width: 3,
        color: "#16a34a",
      },
      itemStyle: {
        color: "#16a34a",
      },
      areaStyle: {
        color: "rgba(22, 163, 74, 0.08)",
      },
      data: trendData.value.map((item) => item.detections),
    },
    {
      name: "Identified",
      type: "line",
      smooth: true,
      lineStyle: {
        width: 3,
        color: "#0ea5e9",
      },
      itemStyle: {
        color: "#0ea5e9",
      },
      data: trendData.value.map((item) => item.identified),
    },
  ],
}));

async function loadAnalyticsData() {
  loading.value = true;
  try {
    const [summaryRes, distributionRes, trendRes, performanceRes, topRes] =
      await Promise.all([
        request.get("/analytics/summary"),
        request.get("/analytics/disease-distribution"),
        request.get("/analytics/detection-trend"),
        request.get("/analytics/model-performance"),
        request.get("/analytics/top-diseases"),
      ]);

    summary.value = summaryRes;
    diseaseDistribution.value = distributionRes;
    trendData.value = trendRes;
    modelPerformance.value = performanceRes;
    topDiseases.value = topRes;
  } catch (error) {
    console.error("加载分析数据失败", error);
    diseaseDistribution.value = [
      { name: "No Data", value: 100, color: "#94a3b8" },
    ];
    trendData.value = [];
    modelPerformance.value = [];
    topDiseases.value = [];
  } finally {
    loading.value = false;
  }
}

onMounted(() => {
  loadAnalyticsData();
});
</script>

<style scoped>
.analysis-page {
  background: #f9fafb;
  min-height: 100vh;
  padding-bottom: 40px;
}

.analysis-header {
  height: 72px;
  background: white;
  border-bottom: 1px solid #e5e7eb;
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0 24px;
}

.header-left,
.header-right {
  display: flex;
  align-items: center;
  gap: 16px;
}

.title-row {
  display: flex;
  align-items: center;
  gap: 10px;
}

.title-icon,
.section-icon,
.metric-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 36px;
  height: 36px;
  border-radius: 12px;
  background: #ecfdf3;
  color: #16a34a;
  font-size: 18px;
}

.title {
  font-size: 18px;
  font-weight: 700;
  color: #111827;
}

.subtitle {
  margin-top: 2px;
  font-size: 12px;
  color: #6b7280;
}

.back-btn,
.nav-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 8px 12px;
  border-radius: 10px;
  color: #374151;
  text-decoration: none;
  transition:
    background 0.2s ease,
    color 0.2s ease;
}

.back-btn:hover,
.nav-btn:hover {
  background: #f3f4f6;
  color: #111827;
}

.analysis-container {
  max-width: 1280px;
  margin: 0 auto;
  padding: 24px 24px 32px;
  box-sizing: border-box;
  display: flex;
  flex-direction: column;
  gap: 24px;
}

.metrics-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 16px;
}

.metric-card,
.chart-card,
.panel-card {
  background: white;
  border-radius: 20px;
  border: 1px solid #e5e7eb;
  box-shadow: 0 1px 2px rgba(15, 23, 42, 0.04);
  min-width: 0;
  box-sizing: border-box;
}

.metric-card {
  padding: 20px 20px 18px;
}

.metric-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.metric-label {
  font-size: 13px;
  color: #6b7280;
}

.metric-value {
  font-size: 30px;
  font-weight: 700;
  margin-top: 10px;
  color: #111827;
}

.metric-change {
  margin-top: 10px;
  font-size: 13px;
}

.positive {
  color: #16a34a;
}

.negative {
  color: #dc2626;
}

.chart-card,
.panel-card {
  padding: 24px;
}

.section-header {
  margin-bottom: 16px;
}

.section-title-row {
  display: flex;
  align-items: center;
  gap: 10px;
}

.section-title-row h2 {
  margin: 0;
  font-size: 16px;
  font-weight: 700;
  color: #111827;
}

.section-title-row p {
  margin: 2px 0 0;
  font-size: 12px;
  color: #6b7280;
}

.distribution-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.legend-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.distribution-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 0;
  border-bottom: 1px solid #f3f4f6;
  font-size: 13px;
  color: #374151;
}

.legend-left {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
}

.legend-dot {
  width: 10px;
  height: 10px;
  border-radius: 999px;
  flex-shrink: 0;
}

.legend-value {
  font-weight: 600;
  color: #111827;
}

.charts-grid {
  display: grid;
  grid-template-columns: minmax(0, 2fr) minmax(0, 3fr);
  gap: 24px;
}

.bottom-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 24px;
}

.chart {
  width: 100%;
  height: 320px;
}

.top-diseases-list,
.severity-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.rank-item {
  display: flex;
  align-items: flex-start;
  gap: 10px;
}

.rank-badge {
  width: 24px;
  height: 24px;
  border-radius: 999px;
  background: #f3f4f6;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
  font-weight: 700;
  color: #6b7280;
  flex-shrink: 0;
}

.rank-content {
  flex: 1;
  min-width: 0;
}

.rank-row,
.severity-label-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  color: #374151;
}

.rank-name {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.rank-meta {
  display: block;
  margin-top: 4px;
  font-size: 12px;
  color: #6b7280;
}

.progress-bar {
  height: 10px;
  margin-top: 8px;
  background: #e5e7eb;
  border-radius: 999px;
  overflow: hidden;
}

.progress-bar.compact {
  height: 8px;
}

.progress-fill {
  height: 100%;
  background: #16a34a;
  border-radius: 999px;
  transition: width 0.3s ease;
}

.performance-item {
  margin-bottom: 14px;
}

.performance-header {
  display: flex;
  justify-content: space-between;
  margin-bottom: 6px;
  font-size: 13px;
  color: #374151;
}

.performance-footer {
  margin-top: 18px;
  padding-top: 14px;
  border-top: 1px solid #f3f4f6;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.footer-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 12px;
  color: #6b7280;
}

.footer-row strong {
  color: #111827;
  font-weight: 600;
}

.record-item {
  padding: 12px 0;
  border-bottom: 1px solid #f3f4f6;
}

.record-name {
  font-weight: 600;
  color: #111827;
}

.record-info {
  font-size: 13px;
  color: #6b7280;
  margin-top: 4px;
}

@media (max-width: 960px) {
  .metrics-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .charts-grid,
  .bottom-grid {
    grid-template-columns: 1fr;
  }

  .analysis-header {
    height: auto;
    flex-direction: column;
    align-items: flex-start;
    padding: 16px 20px;
    gap: 12px;
  }
}
</style>