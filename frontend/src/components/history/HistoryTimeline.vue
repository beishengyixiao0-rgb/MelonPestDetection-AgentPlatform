<template>
  <section class="timeline-shell" v-loading="loading">
    <template v-if="items.length">
      <div class="timeline-line" />

      <template v-for="(task, index) in items" :key="task.id">
        <div v-if="showDate(index)" class="date-label">
          <el-icon><Calendar /></el-icon>
          <span>{{ formatDate(task.created_at) }}</span>
        </div>

        <div class="timeline-row">
          <div class="timeline-marker">
            <span :class="statusTone(task.status)" />
          </div>

          <article class="history-card" tabindex="0" @click="$emit('open', task)" @keyup.enter="$emit('open', task)">
            <div class="task-avatar" :class="taskTone(task.task_type)">
              <el-icon><component :is="taskIcon(task.task_type)" /></el-icon>
            </div>

            <div class="task-main">
              <div class="task-title-row">
                <h3>{{ taskTitle(task) }}</h3>
                <span class="status-chip" :class="statusTone(task.status)">
                  {{ statusLabel(task.status) }}
                </span>
              </div>
              <p class="task-subtitle">
                {{ task.scene_name || (locale === 'en' ? 'General detection' : '通用检测场景') }}
              </p>
              <div class="task-metrics">
                <span><b>{{ task.total_objects ?? 0 }}</b> {{ locale === 'en' ? 'objects' : '个目标' }}</span>
                <span><b>{{ task.total_images ?? 0 }}</b> {{ locale === 'en' ? 'files' : '个文件' }}</span>
                <span><b>{{ formatTime(task.total_inference_time) }}</b></span>
              </div>
            </div>

            <div class="task-side">
              <time>{{ formatClock(task.created_at) }}</time>
              <code>#{{ task.id }}</code>
              <div class="task-actions">
                <button type="button" @click.stop="$emit('ask-ai', task)">
                  <el-icon><ChatDotRound /></el-icon>
                  {{ locale === 'en' ? 'Ask AI' : '询问 AI' }}
                </button>
                <button class="danger" type="button" :aria-label="locale === 'en' ? 'Delete task' : '删除任务'" @click.stop="$emit('delete', task)">
                  <el-icon><Delete /></el-icon>
                </button>
              </div>
            </div>
            <el-icon class="open-arrow"><ArrowRight /></el-icon>
          </article>
        </div>
      </template>
    </template>

    <div v-else class="empty-state">
      <div class="empty-icon"><el-icon><Filter /></el-icon></div>
      <h3>{{ locale === 'en' ? 'No matching detection records' : '没有匹配的检测记录' }}</h3>
      <p>{{ locale === 'en' ? 'Try changing the filters or start a new detection.' : '可以调整筛选条件，或开始一次新的检测。' }}</p>
      <button type="button" @click="$emit('clear')">
        {{ locale === 'en' ? 'Clear filters' : '清除筛选' }}
      </button>
    </div>
  </section>
</template>

<script setup>
import {
  ArrowRight,
  Calendar,
  ChatDotRound,
  Collection,
  Delete,
  Film,
  Filter,
  Picture,
  VideoCamera,
} from '@element-plus/icons-vue'

const props = defineProps({
  items: { type: Array, default: () => [] },
  loading: Boolean,
  locale: { type: String, default: 'zh' },
})

defineEmits(['open', 'ask-ai', 'delete', 'clear'])

function parsedDate(value) {
  const date = value ? new Date(value) : null
  return date && !Number.isNaN(date.getTime()) ? date : null
}

function dateKey(value) {
  const date = parsedDate(value)
  return date ? `${date.getFullYear()}-${date.getMonth()}-${date.getDate()}` : 'unknown'
}

function showDate(index) {
  if (index === 0) return true
  return dateKey(props.items[index]?.created_at) !== dateKey(props.items[index - 1]?.created_at)
}

function formatDate(value) {
  const date = parsedDate(value)
  if (!date) return props.locale === 'en' ? 'Unknown date' : '时间未知'
  return new Intl.DateTimeFormat(props.locale === 'en' ? 'en-US' : 'zh-CN', {
    year: 'numeric', month: 'long', day: 'numeric', weekday: 'short',
  }).format(date)
}

function formatClock(value) {
  const date = parsedDate(value)
  if (!date) return '--:--'
  return new Intl.DateTimeFormat(props.locale === 'en' ? 'en-US' : 'zh-CN', {
    hour: '2-digit', minute: '2-digit', hour12: props.locale === 'en',
  }).format(date)
}

function formatTime(value) {
  const ms = Number(value)
  return Number.isFinite(ms) ? `${ms.toFixed(ms >= 100 ? 0 : 1)} ms` : '0 ms'
}

function taskTitle(task) {
  const labels = props.locale === 'en'
    ? { single: 'Single-image detection', batch: 'Batch detection', zip: 'ZIP batch detection', video: 'Video detection', realtime: 'Live detection', camera: 'Camera detection' }
    : { single: '单图检测', batch: '批量图片检测', zip: 'ZIP 批量检测', video: '视频检测', realtime: '实时摄像头检测', camera: '相机检测' }
  return labels[task.task_type] || (props.locale === 'en' ? 'Detection task' : '检测任务')
}

function statusLabel(status) {
  const labels = props.locale === 'en'
    ? { completed: 'Completed', processing: 'Processing', pending: 'Pending', failed: 'Failed' }
    : { completed: '已完成', processing: '处理中', pending: '待处理', failed: '失败' }
  return labels[status] || status || (props.locale === 'en' ? 'Unknown' : '未知')
}

function statusTone(status) {
  return ['completed', 'processing', 'pending', 'failed'].includes(status) ? status : 'unknown'
}

function taskTone(type) {
  if (type === 'video' || type === 'realtime') return 'purple'
  if (type === 'batch' || type === 'zip') return 'blue'
  return 'green'
}

function taskIcon(type) {
  if (type === 'video') return Film
  if (type === 'realtime' || type === 'camera') return VideoCamera
  if (type === 'batch' || type === 'zip') return Collection
  return Picture
}
</script>

<style scoped>
.timeline-shell { position: relative; min-height: 180px; }
.timeline-line { position: absolute; top: 42px; bottom: 28px; left: 19px; width: 1px; background: #dfe5e1; }
.date-label { display: flex; align-items: center; gap: 8px; margin: 22px 0 10px 42px; color: #7a867e; font-size: 11px; font-weight: 700; letter-spacing: .06em; text-transform: uppercase; }
.date-label:first-child { margin-top: 0; }
.timeline-row { position: relative; display: flex; align-items: stretch; gap: 10px; margin-bottom: 12px; }
.timeline-marker { width: 30px; flex: 0 0 30px; display: flex; justify-content: center; padding-top: 29px; z-index: 1; }
.timeline-marker span { width: 9px; height: 9px; border-radius: 50%; border: 2px solid #fff; box-shadow: 0 0 0 3px #dde5e0; background: #7d8a81; }
.timeline-marker span.completed { background: #20a05a; box-shadow: 0 0 0 3px #cdeed9; }
.timeline-marker span.processing { background: #4088d2; box-shadow: 0 0 0 3px #d5e9fb; }
.timeline-marker span.pending { background: #e39a20; box-shadow: 0 0 0 3px #f8e7c6; }
.timeline-marker span.failed { background: #d95353; box-shadow: 0 0 0 3px #f6d5d5; }

.history-card { position: relative; flex: 1; min-width: 0; display: flex; align-items: center; gap: 14px; padding: 15px 44px 15px 16px; background: #fff; border: 1px solid #e4e9e6; border-radius: 17px; cursor: pointer; transition: .2s ease; outline: none; }
.history-card:hover, .history-card:focus-visible { border-color: #afd8bd; box-shadow: 0 10px 26px rgba(39, 91, 59, .08); transform: translateY(-1px); }
.task-avatar { width: 48px; height: 48px; border-radius: 14px; display: grid; place-items: center; flex: 0 0 48px; background: #e9f8ef; color: #19834a; font-size: 21px; }
.task-avatar.blue { background: #eaf4ff; color: #337ecc; }
.task-avatar.purple { background: #f2ecff; color: #7955b7; }
.task-main { flex: 1; min-width: 0; }
.task-title-row { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.task-title-row h3 { margin: 0; color: #1a271f; font-size: 14px; font-weight: 700; }
.status-chip { padding: 3px 8px; border-radius: 999px; border: 1px solid #dfe5e1; background: #f5f7f6; color: #6c7870; font-size: 10px; font-weight: 700; }
.status-chip.completed { border-color: #c9ead5; background: #eaf8ef; color: #18854b; }
.status-chip.processing { border-color: #cce1f5; background: #ebf5ff; color: #337ecc; }
.status-chip.pending { border-color: #f2dfb9; background: #fff6e3; color: #b8790b; }
.status-chip.failed { border-color: #f0cccc; background: #fff0f0; color: #c94444; }
.task-subtitle { margin: 4px 0 8px; color: #7b877f; font-size: 12px; }
.task-metrics { display: flex; gap: 15px; flex-wrap: wrap; color: #7b877f; font-size: 11px; }
.task-metrics b { color: #34443a; font-weight: 700; }
.task-side { flex: 0 0 auto; min-width: 132px; text-align: right; }
.task-side time, .task-side code { display: block; color: #879189; font-size: 10px; }
.task-side code { margin-top: 3px; }
.task-actions { display: flex; justify-content: flex-end; gap: 5px; margin-top: 9px; }
.task-actions button { border: 0; border-radius: 8px; background: #f3f6f4; color: #617067; padding: 5px 8px; display: inline-flex; align-items: center; gap: 4px; font-size: 10px; cursor: pointer; }
.task-actions button:hover { background: #e9f6ed; color: #18854b; }
.task-actions button.danger { padding-inline: 6px; }
.task-actions button.danger:hover { background: #fff0f0; color: #c94444; }
.open-arrow { position: absolute; right: 15px; color: #a6afa9; font-size: 14px; }

.empty-state { text-align: center; padding: 58px 20px; background: #fff; border: 1px dashed #d9e0dc; border-radius: 18px; color: #7b877f; }
.empty-icon { width: 48px; height: 48px; margin: 0 auto 12px; border-radius: 50%; display: grid; place-items: center; background: #f1f5f2; color: #89958d; font-size: 21px; }
.empty-state h3 { margin: 0; color: #34443a; font-size: 14px; }
.empty-state p { margin: 7px 0 14px; font-size: 12px; }
.empty-state button { border: 0; background: transparent; color: #16834a; font-size: 12px; cursor: pointer; }

@media (max-width: 680px) {
  .history-card { align-items: flex-start; flex-wrap: wrap; padding-right: 34px; }
  .task-side { width: 100%; min-width: 0; text-align: left; padding-left: 62px; }
  .task-side time, .task-side code { display: inline; margin-right: 8px; }
  .task-actions { justify-content: flex-start; }
}
</style>
