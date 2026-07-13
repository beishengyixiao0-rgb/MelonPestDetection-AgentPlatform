<template>
  <div class="analysis-page">
    <header class="analysis-header">
      <div class="header-left">
        <router-link to="/" class="back-btn">
          ←
        </router-link>

        <div class="title-row">
          <div class="title-icon">🌿</div>
          <div>
            <div class="title">Disease Analytics</div>
            <div class="subtitle">Crop disease monitoring overview</div>
          </div>
        </div>
      </div>

      <div class="header-right">
        <router-link
          to="/ai-chat"
          class="nav-btn"
        >
          🤖 AI Agent
        </router-link>

        <router-link
          to="/history"
          class="nav-btn"
        >
          🕒 History
        </router-link>
      </div>
    </header>

    <div class="analysis-container">
      <section class="metrics-grid">
        <div
          v-for="metric in metrics"
          :key="metric.label"
          class="metric-card"
        >
          <div class="metric-top">
            <div class="metric-label">
              {{ metric.label }}
            </div>
            <div class="metric-icon" :class="metric.up ? 'positive' : 'negative'">
              {{ metric.up ? '↗' : '↘' }}
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
            <VChart
              class="chart"
              :option="pieOption"
            />

            <div class="legend-list">
              <div
                v-for="item in diseaseDistribution"
                :key="item.name"
                class="distribution-item"
              >
                <div class="legend-left">
                  <span class="legend-dot" :style="{ background: item.color }" />
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

          <VChart
            class="chart"
            :option="lineOption"
          />
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
                  <span class="rank-change" :class="disease.change > 0 ? 'positive' : 'negative'">
                    {{ disease.change > 0 ? '+' : '' }}{{ disease.change }}%
                  </span>
                </div>
                <div class="progress-bar compact">
                  <div
                    class="progress-fill"
                    :style="{ width: `${(disease.count / 900) * 100}%`, background: disease.color }"
                  />
                </div>
                <span class="rank-meta">{{ disease.count.toLocaleString() }} cases</span>
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

import { LineChart, PieChart } from 'echarts/charts'
import {
  GridComponent,
  LegendComponent,
  TooltipComponent,
} from 'echarts/components'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import VChart from 'vue-echarts'

use([
  CanvasRenderer,
  PieChart,
  LineChart,
  TooltipComponent,
  LegendComponent,
  GridComponent,
])


const metrics = [
  {
    label: 'Total Detections',
    value: '3,091',
    sub: '+18% vs last month',
    up: true,
  },
  {
    label: 'Diseases Identified',
    value: '2,804',
    sub: '90.7% identification rate',
    up: true,
  },
  {
    label: 'Model Accuracy',
    value: '94.2%',
    sub: '+1.3% from last version',
    up: true,
  },
  {
    label: 'Avg Confidence',
    value: '91.3%',
    sub: '-0.4% this week',
    up: false,
  },
]

const diseaseDistribution = [
  { name: 'Tomato Late Blight', value: 28, color: '#16a34a' },
  { name: 'Grape Black Rot', value: 19, color: '#0ea5e9' },
  { name: 'Pepper Bacterial Spot', value: 17, color: '#f59e0b' },
  { name: 'Apple Scab', value: 14, color: '#8b5cf6' },
  { name: 'Strawberry Leaf Scorch', value: 12, color: '#ec4899' },
  { name: 'Other', value: 10, color: '#94a3b8' },
]

const trendData = [
  { month: 'Jan', detections: 124, identified: 112 },
  { month: 'Feb', detections: 158, identified: 143 },
  { month: 'Mar', detections: 203, identified: 187 },
  { month: 'Apr', detections: 178, identified: 165 },
  { month: 'May', detections: 241, identified: 228 },
  { month: 'Jun', detections: 289, identified: 271 },
  { month: 'Jul', detections: 312, identified: 298 },
]

const modelPerformance = [
  { label: 'Precision', value: 92.8, color: '#16a34a' },
  { label: 'Recall', value: 93.5, color: '#0ea5e9' },
  { label: 'F1 Score', value: 93.1, color: '#8b5cf6' },
  { label: 'Accuracy', value: 94.2, color: '#f59e0b' },
]

const topDiseases = [
  { name: 'Tomato Late Blight', count: 847, change: 12, color: '#16a34a' },
  { name: 'Grape Black Rot', count: 623, change: -4, color: '#0ea5e9' },
  { name: 'Pepper Bacterial Spot', count: 541, change: 8, color: '#f59e0b' },
  { name: 'Apple Scab', count: 418, change: 3, color: '#8b5cf6' },
]

const severitySummary = [
  { label: 'High', value: 31, color: '#ef4444' },
  { label: 'Moderate', value: 24, color: '#f59e0b' },
  { label: 'Low', value: 45, color: '#16a34a' },
]

const recentDiagnoses = [
  {
    id: 1,
    name: 'Tomato Late Blight',
    confidence: 94.2,
  },
  {
    id: 2,
    name: 'Grape Black Rot',
    confidence: 91.6,
  },
  {
    id: 3,
    name: 'Pepper Leaf Spot',
    confidence: 89.7,
  },
]

const pieOption = {
  tooltip: {
    trigger: 'item',
    formatter: '{b}: {d}%',
  },
  series: [
    {
      type: 'pie',
      radius: ['58%', '78%'],
      center: ['50%', '50%'],
      emphasis: {
        scale: true,
        scaleSize: 8,
      },
      itemStyle: {
        borderRadius: 8,
        borderColor: '#ffffff',
        borderWidth: 2,
      },
      data: diseaseDistribution.map((item) => ({
        value: item.value,
        name: item.name,
        itemStyle: {
          color: item.color,
        },
      })),
    },
  ],
}

const lineOption = {
  tooltip: {
    trigger: 'axis',
    axisPointer: {
      type: 'cross',
    },
  },
  legend: {
    top: 0,
    textStyle: {
      color: '#6b7280',
    },
  },
  grid: {
    left: '8%',
    right: '4%',
    top: '18%',
    bottom: '10%',
  },
  xAxis: {
    type: 'category',
    data: ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul'],
    axisLine: { show: false },
    axisTick: { show: false },
    axisLabel: {
      color: '#6b7280',
    },
  },
  yAxis: {
    type: 'value',
    axisLine: { show: false },
    axisTick: { show: false },
    splitLine: {
      lineStyle: {
        color: 'rgba(0, 0, 0, 0.06)',
      },
    },
    axisLabel: {
      color: '#6b7280',
    },
  },
  series: [
    {
      name: 'Total Detections',
      type: 'line',
      smooth: true,
      lineStyle: {
        width: 3,
        color: '#16a34a',
      },
      itemStyle: {
        color: '#16a34a',
      },
      areaStyle: {
        color: 'rgba(22, 163, 74, 0.08)',
      },
      data: [124, 158, 203, 178, 241, 289, 312],
    },
    {
      name: 'Identified',
      type: 'line',
      smooth: true,
      lineStyle: {
        width: 3,
        color: '#0ea5e9',
      },
      itemStyle: {
        color: '#0ea5e9',
      },
      data: [112, 143, 187, 165, 228, 271, 298],
    },
  ],
}

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
  transition: background 0.2s ease, color 0.2s ease;
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