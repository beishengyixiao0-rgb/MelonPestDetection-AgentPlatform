<template>
  <div class="analysis-page" v-loading="loading">
    <header class="analysis-header">
      <div class="header-left">
        <router-link to="/home" class="icon-button" aria-label="返回首页">
          <el-icon><ArrowLeft /></el-icon>
        </router-link>
        <div class="brand-mark"><HeaderSeedlingIcon /></div>
        <div>
          <h1>病害数据分析</h1>
          <p>作物病害检测与评估概览</p>
        </div>
      </div>

      <nav class="header-nav" aria-label="快捷导航">
        <LanguageSwitcher />
        <router-link to="/ai-chat"><el-icon><ChatDotRound /></el-icon>智能对话</router-link>
        <router-link to="/history"><el-icon><Clock /></el-icon>历史记录</router-link>
      </nav>
    </header>

    <main class="analysis-container">
      <section class="charts-grid">
        <article class="chart-card distribution-card">
          <div class="section-header">
            <div class="section-title-row">
              <div class="section-icon">📊</div>
              <div>
                <h2>病害分布</h2>
                <p>近 30 天检测目标占比</p>
              </div>
            </div>
          </div>

          <div v-if="hasDistribution" class="distribution-layout">
            <VChart class="pie-chart" :option="pieOption" autoresize />
            <div class="legend-list">
              <div
                v-for="item in diseaseDistribution"
                :key="item.name"
                class="distribution-item"
              >
                <div class="legend-left">
                  <span class="legend-dot" :style="{ background: item.color }" />
                  <span class="legend-name">{{ item.name }}</span>
                </div>
                <strong class="legend-value">{{ item.value }}%</strong>
              </div>
            </div>
          </div>
          <div v-else class="empty-state">暂无病害分布数据</div>
        </article>

        <article class="chart-card trend-card">
          <div class="section-header">
            <div class="section-title-row">
              <div class="section-icon">📈</div>
              <div>
                <h2>检测趋势</h2>
                <p>近 7 天每日检测任务变化</p>
              </div>
            </div>
          </div>
          <VChart v-if="trendData.length" class="trend-chart" :option="lineOption" autoresize />
          <div v-else class="empty-state chart-empty">暂无检测趋势数据</div>
        </article>
      </section>

      <section class="bottom-grid">
        <article class="panel-card">
          <div class="section-header">
            <div class="section-title-row">
              <div class="section-icon">🏆</div>
              <div>
                <h2>高发病害排行</h2>
                <p>近 30 天按检测目标数量排序</p>
              </div>
            </div>
          </div>

          <div v-if="topDiseases.length" class="top-diseases-list">
            <div
              v-for="(disease, index) in topDiseases"
              :key="`${disease.name}-${index}`"
              class="rank-item"
            >
              <div class="rank-badge" :class="{ leading: index < 3 }">{{ index + 1 }}</div>
              <div class="rank-content">
                <div class="rank-row">
                  <span class="rank-name" :title="disease.name">{{ disease.name }}</span>
                  <strong>{{ formatNumber(disease.count) }} 个</strong>
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
              </div>
            </div>
          </div>
          <div v-else class="empty-state panel-empty">暂无排行数据</div>
        </article>

        <article class="panel-card severity-card">
          <div class="section-header">
            <div class="section-title-row">
              <div class="section-icon warning">⚠️</div>
              <div>
                <h2>严重程度分布</h2>
                <p>基于历史记录中的问卷评估结果</p>
              </div>
            </div>
          </div>

          <div class="severity-list">
            <div
              v-for="item in severitySummary"
              :key="item.key"
              class="severity-item"
              :style="{ '--severity-color': item.color, '--severity-soft': item.softColor }"
            >
              <span class="severity-dot" />
              <div class="severity-content">
                <div class="severity-label-row">
                  <span class="severity-name">{{ item.label }}</span>
                  <span class="severity-numbers">
                    <strong>{{ item.value }}%</strong>
                    <small>{{ item.count }} 条</small>
                  </span>
                </div>
                <div class="progress-bar compact severity-progress">
                  <div
                    class="progress-fill"
                    :style="{ width: `${item.value}%`, background: item.color }"
                  />
                </div>
              </div>
            </div>
          </div>
        </article>

        <article class="panel-card">
          <div class="section-header">
            <div class="section-title-row">
              <div class="section-icon">🎯</div>
              <div>
                <h2>模型性能</h2>
                <p>当前检测模型的验证指标</p>
              </div>
            </div>
          </div>

          <div v-if="modelPerformance.length" class="performance-list">
            <div v-for="item in modelPerformance" :key="item.label" class="performance-item">
              <div class="performance-header">
                <span>{{ item.label }}</span>
                <strong>{{ item.value }}%</strong>
              </div>
              <div class="progress-bar">
                <div
                  class="progress-fill"
                  :style="{ width: `${item.value}%`, background: item.color }"
                />
              </div>
            </div>
          </div>
          <div v-else class="empty-state panel-empty">暂无模型性能数据</div>

          <div class="performance-footer">
            <div class="footer-row">
              <span>指标来源</span>
              <strong>当前可用检测模型</strong>
            </div>
            <div class="footer-row">
              <span>数据更新时间</span>
              <strong>{{ updatedAtText }}</strong>
            </div>
          </div>
        </article>
      </section>
    </main>
  </div>
</template>

<script setup>
import LanguageSwitcher from "@/components/LanguageSwitcher.vue";
import HeaderSeedlingIcon from "@/components/HeaderSeedlingIcon.vue";
import request from "@/utils/request";
import { ArrowLeft, ChatDotRound, Clock } from "@element-plus/icons-vue";
import { LineChart, PieChart } from "echarts/charts";
import { GridComponent, TooltipComponent } from "echarts/components";
import { use } from "echarts/core";
import { CanvasRenderer } from "echarts/renderers";
import { computed, onMounted, ref } from "vue";
import VChart from "vue-echarts";

use([CanvasRenderer, PieChart, LineChart, TooltipComponent, GridComponent]);

const loading = ref(true);
const summary = ref({
  total_detections: 0,
  detection_change: 0,
  diseases_identified: 0,
  identification_rate: 0,
  model_accuracy: 0,
  accuracy_change: 0,
  avg_confidence: 0,
  data_updated_at: null,
});
const diseaseDistribution = ref([]);
const trendData = ref([]);
const modelPerformance = ref([]);
const topDiseases = ref([]);
const riskCounts = ref({});

const performanceLabelMap = {
  Precision: "精确率",
  Recall: "召回率",
  "F1 Score": "F1 分数",
  F1: "F1 分数",
  "mAP@50": "mAP@50",
};

const severitySummary = computed(() => {
  const counts = riskCounts.value || {};
  const pending = Number(counts.insufficient_information || 0) + Number(counts.unassessed || 0);
  const definitions = [
    { key: "critical", label: "严重", count: Number(counts.critical || 0), color: "#dc2626", softColor: "#fef2f2" },
    { key: "high", label: "较高", count: Number(counts.high || 0), color: "#f97316", softColor: "#fff7ed" },
    { key: "moderate", label: "中等", count: Number(counts.moderate || 0), color: "#eab308", softColor: "#fefce8" },
    { key: "low", label: "较低", count: Number(counts.low || 0), color: "#16a34a", softColor: "#f0fdf4" },
    { key: "pending", label: "待评估", count: pending, color: "#94a3b8", softColor: "#f8fafc" },
  ];
  const total = definitions.reduce((sum, item) => sum + item.count, 0);
  return definitions.map((item) => ({
    ...item,
    value: total ? Math.round((item.count / total) * 100) : 0,
  }));
});

const hasDistribution = computed(
  () => diseaseDistribution.value.length > 0 && diseaseDistribution.value.some((item) => Number(item.value) > 0),
);

const updatedAtText = computed(() => {
  const value = summary.value.data_updated_at;
  if (!value) return "暂无记录";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return String(value);
  return new Intl.DateTimeFormat("zh-CN", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  }).format(date);
});

const pieOption = computed(() => ({
  tooltip: { trigger: "item", formatter: "{b}：{d}%" },
  series: [
    {
      name: "病害占比",
      type: "pie",
      radius: ["56%", "78%"],
      center: ["50%", "50%"],
      label: { show: false },
      emphasis: { scale: true, scaleSize: 7 },
      itemStyle: { borderRadius: 8, borderColor: "#ffffff", borderWidth: 3 },
      data: diseaseDistribution.value.map((item) => ({
        value: Number(item.value || 0),
        name: item.name || "未命名病害",
        itemStyle: { color: item.color || "#94a3b8" },
      })),
    },
  ],
}));

const lineOption = computed(() => ({
  tooltip: { trigger: "axis", valueFormatter: (value) => `${value} 次` },
  grid: { left: 44, right: 18, top: 24, bottom: 32 },
  xAxis: {
    type: "category",
    boundaryGap: false,
    data: trendData.value.map((item) => item.date || item.month),
    axisLine: { lineStyle: { color: "#e5e7eb" } },
    axisTick: { show: false },
    axisLabel: { color: "#6b7280" },
  },
  yAxis: {
    type: "value",
    minInterval: 1,
    axisLine: { show: false },
    axisTick: { show: false },
    splitLine: { lineStyle: { color: "#eef2f0" } },
    axisLabel: { color: "#6b7280" },
  },
  series: [
    {
      name: "检测次数",
      type: "line",
      smooth: true,
      symbolSize: 7,
      lineStyle: { width: 3, color: "#16a34a" },
      itemStyle: { color: "#16a34a", borderColor: "#ffffff", borderWidth: 2 },
      areaStyle: { color: "rgba(22, 163, 74, 0.10)" },
      data: trendData.value.map((item) => Number(item.detections || 0)),
    },
  ],
}));

function formatNumber(value) {
  return Number(value || 0).toLocaleString("zh-CN");
}

function normalizePerformance(items) {
  if (!Array.isArray(items)) return [];
  return items.map((item) => ({
    ...item,
    label: performanceLabelMap[item.label] || item.label || "模型指标",
    value: Number(item.value || 0),
  }));
}

async function loadAnalyticsData() {
  loading.value = true;
  try {
    const [summaryRes, distributionRes, trendRes, performanceRes, topRes, historySummaryRes] =
      await Promise.all([
        request.get("/analytics/summary"),
        request.get("/analytics/disease-distribution"),
        request.get("/analytics/detection-trend"),
        request.get("/analytics/model-performance"),
        request.get("/analytics/top-diseases"),
        request.get("/history/summary"),
      ]);

    summary.value = summaryRes || summary.value;
    diseaseDistribution.value = Array.isArray(distributionRes)
      ? distributionRes.map((item) => ({ ...item, name: item.name === "No Data" ? "暂无数据" : item.name }))
      : [];
    trendData.value = Array.isArray(trendRes) ? trendRes : [];
    modelPerformance.value = normalizePerformance(performanceRes);
    topDiseases.value = Array.isArray(topRes)
      ? topRes.map((item) => ({ ...item, name: item.name === "No Data" ? "暂无数据" : item.name }))
      : [];
    riskCounts.value = historySummaryRes?.risk_counts || {};
  } catch (error) {
    console.error("加载数据分析失败", error);
    diseaseDistribution.value = [];
    trendData.value = [];
    modelPerformance.value = [];
    topDiseases.value = [];
    riskCounts.value = {};
  } finally {
    loading.value = false;
  }
}

onMounted(loadAnalyticsData);
</script>

<style scoped>
.analysis-page {
  min-height: 100vh;
  background: #f6f8f7;
  color: #17201b;
}

.analysis-header {
  position: sticky;
  top: 0;
  z-index: 20;
  min-height: 72px;
  padding: 12px 28px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 20px;
  box-sizing: border-box;
  border-bottom: 1px solid rgba(222, 229, 224, 0.9);
  background: rgba(250, 252, 250, 0.9);
  backdrop-filter: blur(16px);
}

.header-left,
.header-nav,
.section-title-row,
.metric-top,
.legend-left,
.rank-row,
.severity-label-row,
.performance-header,
.footer-row {
  display: flex;
  align-items: center;
}

.header-left { gap: 10px; min-width: 0; }
.header-nav { gap: 7px; }
.section-title-row { gap: 11px; }

.section-icon,
.metric-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex: 0 0 auto;
  width: 38px;
  height: 38px;
  border-radius: 12px;
  background: #ecf8f0;
  color: #16803f;
  font-size: 18px;
}

.section-icon.warning { background: #fff7ed; }
.icon-button { width: 34px; height: 34px; display: grid; place-items: center; border-radius: 10px; color: #68766d; text-decoration: none; }
.icon-button:hover { background: #edf2ee; color: #25372c; }
.brand-mark { width: 34px; height: 34px; margin-left: 2px; display: grid; place-items: center; flex: 0 0 auto; border-radius: 10px; background: #1c8b51; color: #fff; font-size: 18px; }
.header-left h1 { margin: 0; color: #17251c; font-size: 18px; font-weight: 800; }
.header-left p { margin: 2px 0 0; color: #879189; font-size: 12px; }
.header-nav > a { display: inline-flex; align-items: center; gap: 6px; padding: 8px 10px; border-radius: 9px; color: #637068; text-decoration: none; font-size: 13px; }
.header-nav > a:hover { background: #edf3ef; color: #18834a; }

.analysis-container {
  width: min(1320px, calc(100% - 48px));
  margin: 0 auto;
  padding: 26px 0 40px;
  display: flex;
  flex-direction: column;
  gap: 22px;
}

.charts-grid,
.bottom-grid { display: grid; gap: 18px; }
.charts-grid { grid-template-columns: minmax(320px, 0.9fr) minmax(480px, 1.4fr); }
.bottom-grid { grid-template-columns: repeat(3, minmax(0, 1fr)); align-items: stretch; }

.chart-card,
.panel-card {
  min-width: 0;
  box-sizing: border-box;
  background: #ffffff;
  border: 1px solid #e3e9e5;
  border-radius: 18px;
  box-shadow: 0 7px 24px rgba(26, 55, 37, 0.045);
}

.chart-card,
.panel-card { padding: 22px; }
.panel-card { min-height: 390px; display: flex; flex-direction: column; }
.section-header { margin-bottom: 18px; }
.section-title-row h2 { margin: 0; font-size: 16px; font-weight: 720; color: #17201b; }
.section-title-row p { margin: 3px 0 0; font-size: 12px; line-height: 1.45; color: #7a857d; }

.distribution-layout { display: grid; grid-template-columns: minmax(160px, 0.9fr) minmax(150px, 1.1fr); align-items: center; gap: 16px; min-height: 292px; }
.pie-chart { width: 100%; height: 260px; }
.trend-chart { width: 100%; height: 292px; }
.legend-list { min-width: 0; display: flex; flex-direction: column; gap: 3px; }
.distribution-item { padding: 9px 0; justify-content: space-between; gap: 12px; border-bottom: 1px solid #f0f3f1; font-size: 13px; }
.distribution-item:last-child { border-bottom: 0; }
.legend-left { gap: 8px; min-width: 0; }
.legend-dot { width: 9px; height: 9px; flex: 0 0 auto; border-radius: 50%; }
.legend-name { min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; color: #48534c; }
.legend-value { flex: 0 0 auto; color: #1f2923; }

.top-diseases-list,
.severity-list,
.performance-list { display: flex; flex-direction: column; }
.top-diseases-list { gap: 17px; }
.rank-item { display: flex; align-items: flex-start; gap: 11px; }
.rank-badge { width: 26px; height: 26px; flex: 0 0 auto; display: inline-flex; align-items: center; justify-content: center; border-radius: 9px; background: #f1f4f2; color: #667168; font-size: 12px; font-weight: 700; }
.rank-badge.leading { background: #e9f7ee; color: #16803f; }
.rank-content { min-width: 0; flex: 1; }
.rank-row { justify-content: space-between; gap: 10px; font-size: 13px; color: #4a554e; }
.rank-row strong { flex: 0 0 auto; color: #253029; font-size: 12px; }
.rank-name { min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }

.severity-list { gap: 9px; }
.severity-item { min-height: 47px; padding: 9px 10px; display: flex; align-items: center; gap: 10px; box-sizing: border-box; border: 1px solid color-mix(in srgb, var(--severity-color) 17%, transparent); border-radius: 11px; background: var(--severity-soft); }
.severity-dot { width: 9px; height: 32px; flex: 0 0 auto; border-radius: 999px; background: var(--severity-color); }
.severity-content { min-width: 0; flex: 1; }
.severity-label-row { min-height: 20px; justify-content: space-between; gap: 12px; }
.severity-name { font-size: 13px; font-weight: 650; color: #38433c; }
.severity-numbers { min-width: 86px; display: grid; grid-template-columns: 42px 38px; align-items: baseline; justify-content: end; text-align: right; }
.severity-numbers strong { font-size: 13px; color: #253029; }
.severity-numbers small { font-size: 11px; color: #7a857d; }
.severity-progress { margin-top: 6px; background: rgba(255, 255, 255, 0.78); }

.performance-list { gap: 16px; }
.performance-header { justify-content: space-between; gap: 12px; font-size: 13px; color: #4a554e; }
.performance-header strong { color: #253029; }
.progress-bar { height: 9px; margin-top: 8px; overflow: hidden; border-radius: 999px; background: #e9eeeb; }
.progress-bar.compact { height: 7px; }
.progress-fill { height: 100%; min-width: 0; border-radius: inherit; transition: width 0.3s ease; }
.performance-footer { margin-top: auto; padding-top: 16px; border-top: 1px solid #edf1ee; display: flex; flex-direction: column; gap: 9px; }
.footer-row { justify-content: space-between; gap: 16px; font-size: 12px; color: #7a857d; }
.footer-row strong { color: #354039; font-weight: 600; text-align: right; }

.empty-state { min-height: 260px; display: flex; align-items: center; justify-content: center; color: #89938c; font-size: 13px; border-radius: 14px; background: #fafcfb; }
.chart-empty { min-height: 292px; }
.panel-empty { min-height: 180px; flex: 1; }

@media (max-width: 1100px) {
  .bottom-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .bottom-grid .panel-card:last-child { grid-column: 1 / -1; min-height: 330px; }
}

@media (max-width: 820px) {
  .analysis-header { align-items: flex-start; padding: 12px 16px; }
  .header-left p { display: none; }
  .header-nav > a { width: 34px; height: 34px; padding: 0; justify-content: center; font-size: 0; }
  .header-nav > a .el-icon { font-size: 15px; }
  .analysis-container { width: min(100% - 28px, 680px); padding-top: 18px; }
  .charts-grid,
  .bottom-grid { grid-template-columns: 1fr; }
  .bottom-grid .panel-card:last-child { grid-column: auto; }
  .distribution-layout { grid-template-columns: 1fr; }
  .pie-chart { height: 230px; }
  .panel-card { min-height: auto; }
}

@media (max-width: 520px) {
  .analysis-header { gap: 8px; }
  .brand-mark { display: none; }
  .header-nav { gap: 2px; }
  .chart-card,
  .panel-card { padding: 18px; border-radius: 15px; }
  .severity-numbers { min-width: 80px; grid-template-columns: 38px 38px; }
}
</style>
