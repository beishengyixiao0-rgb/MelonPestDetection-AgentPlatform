<template>
  <section class="summary-grid" v-loading="loading">
    <article v-for="card in cards" :key="card.label" class="summary-card">
      <div class="summary-icon" :class="card.tone">
        <el-icon><component :is="card.icon" /></el-icon>
      </div>
      <div>
        <strong :class="card.tone">{{ card.value }}</strong>
        <span>{{ card.label }}</span>
      </div>
    </article>
  </section>
</template>

<script setup>
import { Clock, DataAnalysis, Sunny, Warning } from '@element-plus/icons-vue'
import { computed } from 'vue'

const props = defineProps({
  summary: { type: Object, default: () => ({}) },
  loading: Boolean,
  locale: { type: String, default: 'zh' },
})

const cards = computed(() => {
  const risk = props.summary?.risk_counts || {}
  const treatment = props.summary?.treatment_counts || {}
  const zh = props.locale !== 'en'
  return [
    {
      label: zh ? '累计检测任务' : 'Total detections',
      value: props.summary?.total_tasks ?? 0,
      tone: 'neutral',
      icon: DataAnalysis,
    },
    {
      label: zh ? '今日新增' : 'Added today',
      value: props.summary?.today_tasks ?? 0,
      tone: 'blue',
      icon: Sunny,
    },
    {
      label: zh ? '高风险记录' : 'High-risk records',
      value: (risk.high ?? 0) + (risk.critical ?? 0),
      tone: 'danger',
      icon: Warning,
    },
    {
      label: zh ? '待跟进处理' : 'Needs follow-up',
      value: (treatment.pending ?? 0) + (treatment.in_progress ?? 0) + (treatment.monitoring ?? 0),
      tone: 'warning',
      icon: Clock,
    },
  ]
})
</script>

<style scoped>
.summary-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 14px;
}

.summary-card {
  display: flex;
  align-items: center;
  gap: 14px;
  min-height: 92px;
  padding: 18px;
  background: #fff;
  border: 1px solid #e7ebe8;
  border-radius: 18px;
  box-shadow: 0 8px 24px rgba(32, 69, 48, 0.04);
}

.summary-icon {
  width: 42px;
  height: 42px;
  border-radius: 13px;
  display: grid;
  place-items: center;
  flex-shrink: 0;
  font-size: 19px;
  background: #f2f4f3;
  color: #34443a;
}

.summary-icon.blue { background: #eaf4ff; color: #337ecc; }
.summary-icon.success { background: #e9f8ef; color: #18864b; }
.summary-icon.warning { background: #fff5df; color: #b8790b; }
.summary-icon.danger { background: #fff0f0; color: #c93636; }

.summary-card strong {
  display: block;
  color: #17251c;
  font-size: 27px;
  line-height: 1.1;
  font-weight: 800;
}

.summary-card strong.blue { color: #337ecc; }
.summary-card strong.success { color: #18864b; }
.summary-card strong.warning { color: #b8790b; }
.summary-card strong.danger { color: #c93636; }

.summary-card span {
  display: block;
  margin-top: 5px;
  color: #7b877f;
  font-size: 12px;
}

@media (max-width: 880px) {
  .summary-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
}

@media (max-width: 520px) {
  .summary-grid { grid-template-columns: 1fr; }
  .summary-card { min-height: 76px; padding: 14px 16px; }
}
</style>
