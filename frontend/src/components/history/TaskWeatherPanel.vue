<template>
  <section class="weather-panel">
    <div class="weather-heading">
      <div>
        <span class="weather-kicker">{{ copy.kicker }}</span>
        <h4>{{ copy.title }}</h4>
        <p>{{ hasLocation ? locationText : copy.noLocation }}</p>
      </div>
      <span v-if="weatherView.environment_risk_level" class="environment-risk" :class="`environment-${weatherView.environment_risk_level}`">
        {{ environmentRiskLabel(weatherView.environment_risk_level) }}
      </span>
    </div>

    <div v-if="weatherView.weather_summary" class="weather-result">
      <strong>{{ weatherView.weather_summary }}</strong>
      <div v-if="metrics.length" class="weather-metrics">
        <span v-for="metric in metrics" :key="metric.label"><small>{{ metric.label }}</small>{{ metric.value }}</span>
      </div>
      <ul v-if="weatherView.weather_recommendations?.length">
        <li v-for="item in weatherView.weather_recommendations" :key="item">{{ item }}</li>
      </ul>
      <small v-if="weatherView.weather_updated_at" class="updated-at">{{ copy.updated }} {{ formatDateTime(weatherView.weather_updated_at) }}</small>
    </div>

    <div v-if="errorMessage" class="location-notice">
      <strong>{{ copy.preciseFailed }}</strong>
      <span>{{ errorMessage }}</span>
    </div>

    <div class="weather-actions">
      <button type="button" class="primary" :disabled="busy" @click="useBrowserPosition">
        {{ busyAction === 'browser' ? copy.locating : (hasLocation ? copy.updateLocation : copy.authorize) }}
      </button>
      <button v-if="hasLocation" type="button" :disabled="busy" @click="refreshWeather">
        {{ busyAction === 'weather' ? copy.refreshing : copy.refresh }}
      </button>
      <button type="button" :disabled="busy" @click="showFallback = !showFallback">
        {{ copy.fallback }}
      </button>
    </div>

    <div v-if="showFallback" class="fallback-panel">
      <div class="fallback-row">
        <div>
          <strong>{{ copy.ipTitle }}</strong>
          <span>{{ copy.ipDesc }}</span>
        </div>
        <button type="button" :disabled="busy" @click="useApproximatePosition">
          {{ busyAction === 'ip' ? copy.locating : copy.useIp }}
        </button>
      </div>

      <form class="manual-form" @submit.prevent="saveManualPosition">
        <strong>{{ copy.manualTitle }}</strong>
        <input v-model.trim="manual.name" type="text" maxlength="255" :placeholder="copy.locationName" />
        <div>
          <input v-model.trim="manual.latitude" inputmode="decimal" :placeholder="copy.latitude" />
          <input v-model.trim="manual.longitude" inputmode="decimal" :placeholder="copy.longitude" />
        </div>
        <button type="submit" :disabled="busy">{{ busyAction === 'manual' ? copy.saving : copy.saveManual }}</button>
      </form>
    </div>
  </section>
</template>

<script setup>
import { getApproximateLocationByIp } from '@/api/weather'
import { refreshTaskWeatherRiskApi, updateTaskLocationApi } from '@/api/history'
import { coordinateLabel, getBrowserLocation } from '@/utils/geolocation'
import { ElMessage } from 'element-plus'
import { computed, reactive, ref } from 'vue'

const props = defineProps({
  task: { type: Object, required: true },
  locale: { type: String, default: 'zh' },
})
const emit = defineEmits(['updated'])

const busyAction = ref('')
const showFallback = ref(false)
const errorMessage = ref('')
const latestWeather = ref({})
const manual = reactive({ name: '', latitude: '', longitude: '' })

const copy = computed(() => props.locale === 'en'
  ? {
      kicker: 'Weather context', title: 'Location and environmental risk', noLocation: 'Add a location to assess weather-related spread risk.', updated: 'Updated',
      authorize: 'Use precise location', updateLocation: 'Update location', locating: 'Locating…', refresh: 'Refresh weather risk', refreshing: 'Refreshing…', fallback: 'Other location options',
      preciseFailed: 'Precise location was not available', ipTitle: 'Approximate network location', ipDesc: 'Less precise. Suitable as a fallback only.', useIp: 'Use approximate location',
      manualTitle: 'Enter coordinates manually', locationName: 'Location name (optional)', latitude: 'Latitude, e.g. 30.52', longitude: 'Longitude, e.g. 114.31', saveManual: 'Save and analyze', saving: 'Saving…',
      invalidCoordinates: 'Enter valid latitude and longitude.', saved: 'Location and weather risk updated', weatherUpdated: 'Weather risk refreshed', unavailable: 'Weather source is temporarily unavailable. The location has still been saved.',
      risks: { low: 'Low environmental risk', moderate: 'Moderate environmental risk', high: 'High environmental risk', critical: 'Critical environmental risk', unavailable: 'Weather unavailable' },
      humidity: 'Avg. humidity', temperature: 'Avg. temp.', precipitationChance: 'Max rain chance', precipitation: '3-day rainfall',
    }
  : {
      kicker: '天气环境', title: '位置与环境风险', noLocation: '补充检测地点后，可结合未来天气判断病害扩散风险。', updated: '更新于',
      authorize: '授权精确定位', updateLocation: '更新位置', locating: '正在定位…', refresh: '重新分析天气', refreshing: '正在分析…', fallback: '其他定位方式',
      preciseFailed: '未能使用精确定位', ipTitle: '使用网络估算位置', ipDesc: '精度较低，仅作为无法授权定位时的降级方案。', useIp: '使用估算位置',
      manualTitle: '手动填写经纬度', locationName: '地点名称（可选）', latitude: '纬度，例如 30.52', longitude: '经度，例如 114.31', saveManual: '保存并分析', saving: '正在保存…',
      invalidCoordinates: '请输入有效的经纬度。', saved: '位置和天气风险已更新', weatherUpdated: '天气风险已刷新', unavailable: '天气源暂不可用，但位置已经保存，可稍后重试。',
      risks: { low: '低环境风险', moderate: '中等环境风险', high: '高环境风险', critical: '严重环境风险', unavailable: '天气不可用' },
      humidity: '平均湿度', temperature: '平均气温', precipitationChance: '最高降雨概率', precipitation: '三日降水量',
    })

const busy = computed(() => Boolean(busyAction.value))
const weatherView = computed(() => ({ ...props.task, ...latestWeather.value }))
const hasLocation = computed(() => Number.isFinite(Number(weatherView.value.latitude)) && Number.isFinite(Number(weatherView.value.longitude)))
const locationText = computed(() => weatherView.value.location_name || coordinateLabel(weatherView.value.latitude, weatherView.value.longitude, props.locale))
const metrics = computed(() => {
  const value = weatherView.value.weather_metrics || {}
  return [
    ['avg_humidity', copy.value.humidity, '%'],
    ['avg_temperature', copy.value.temperature, '°C'],
    ['max_precipitation_probability', copy.value.precipitationChance, '%'],
    ['total_precipitation', copy.value.precipitation, ' mm'],
  ].filter(([key]) => value[key] !== undefined && value[key] !== null)
    .map(([key, label, unit]) => ({ label, value: `${value[key]}${unit}` }))
})

function environmentRiskLabel(value) {
  return copy.value.risks[value] || value
}

function formatDateTime(value) {
  if (!value) return ''
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return ''
  return new Intl.DateTimeFormat(props.locale === 'en' ? 'en-US' : 'zh-CN', {
    year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit',
  }).format(date)
}

async function persistLocation(location, source) {
  const response = await updateTaskLocationApi(props.task.id, {
    latitude: Number(location.latitude),
    longitude: Number(location.longitude),
    location_name: location.city || location.name || coordinateLabel(location.latitude, location.longitude, props.locale),
    location_source: source,
  })
  latestWeather.value = response || {}
  emit('updated', response)
  ElMessage.success(copy.value.saved)
  if (response?.environment_risk_level === 'unavailable') ElMessage.warning(copy.value.unavailable)
}

async function useBrowserPosition() {
  busyAction.value = 'browser'
  errorMessage.value = ''
  try {
    const location = await getBrowserLocation()
    await persistLocation(location, 'browser')
  } catch (error) {
    errorMessage.value = error?.message || String(error)
    showFallback.value = true
  } finally {
    busyAction.value = ''
  }
}

async function useApproximatePosition() {
  busyAction.value = 'ip'
  errorMessage.value = ''
  try {
    await persistLocation(await getApproximateLocationByIp(), 'other')
  } catch (error) {
    errorMessage.value = error?.message || String(error)
  } finally {
    busyAction.value = ''
  }
}

async function saveManualPosition() {
  const latitude = Number(manual.latitude)
  const longitude = Number(manual.longitude)
  if (!Number.isFinite(latitude) || !Number.isFinite(longitude) || latitude < -90 || latitude > 90 || longitude < -180 || longitude > 180) {
    ElMessage.warning(copy.value.invalidCoordinates)
    return
  }
  busyAction.value = 'manual'
  errorMessage.value = ''
  try {
    await persistLocation({ latitude, longitude, name: manual.name }, 'manual')
  } catch (error) {
    errorMessage.value = error?.response?.data?.detail || error?.message || String(error)
  } finally {
    busyAction.value = ''
  }
}

async function refreshWeather() {
  busyAction.value = 'weather'
  errorMessage.value = ''
  try {
    const response = await refreshTaskWeatherRiskApi(props.task.id)
    latestWeather.value = response || {}
    emit('updated', response)
    ElMessage.success(copy.value.weatherUpdated)
    if (response?.environment_risk_level === 'unavailable') ElMessage.warning(copy.value.unavailable)
  } catch (error) {
    errorMessage.value = error?.response?.data?.detail || error?.message || String(error)
  } finally {
    busyAction.value = ''
  }
}
</script>

<style scoped>
.weather-panel { margin-top: 18px; padding: 16px; border: 1px solid #dbe8df; border-radius: 15px; background: linear-gradient(145deg, #f8fcf9, #fff); }
.weather-heading { display: flex; align-items: flex-start; justify-content: space-between; gap: 14px; }
.weather-kicker { display: block; margin-bottom: 4px; color: #277a49; font-size: 10px; font-weight: 800; letter-spacing: .08em; text-transform: uppercase; }
.weather-heading h4 { margin: 0; color: #26372d; font-size: 13px; }
.weather-heading p { margin: 4px 0 0; color: #7b887f; font-size: 11px; }
.environment-risk { padding: 5px 9px; border-radius: 999px; white-space: nowrap; font-size: 10px; font-weight: 800; }
.environment-low { background: #e9f8ef; color: #18854b; }
.environment-moderate { background: #fff6e3; color: #ad730d; }
.environment-high { background: #fff0e7; color: #c45118; }
.environment-critical { background: #fff0f0; color: #c93636; }
.environment-unavailable { background: #f1f3f2; color: #737d77; }
.weather-result { margin-top: 13px; padding: 12px; border-radius: 12px; background: #fff; border: 1px solid #e3ebe5; }
.weather-result > strong { color: #34443a; font-size: 12px; line-height: 1.6; }
.weather-result ul { margin: 9px 0 0; padding-left: 19px; color: #58655d; font-size: 11px; line-height: 1.65; }
.weather-metrics { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 7px; margin-top: 10px; }
.weather-metrics span { padding: 8px; border-radius: 9px; background: #f4f8f5; color: #304038; font-size: 11px; font-weight: 700; }
.weather-metrics small { display: block; margin-bottom: 3px; color: #859088; font-size: 9px; font-weight: 500; }
.updated-at { display: block; margin-top: 8px; color: #909991; font-size: 9px; }
.location-notice { display: flex; flex-direction: column; gap: 3px; margin-top: 11px; padding: 9px 11px; border-radius: 10px; background: #fff8e8; color: #8d650f; font-size: 10px; }
.weather-actions { display: flex; flex-wrap: wrap; gap: 7px; margin-top: 13px; }
.weather-actions button, .fallback-panel button { border: 1px solid #dce5df; border-radius: 9px; padding: 7px 10px; background: #fff; color: #536158; font-size: 10px; cursor: pointer; }
.weather-actions button.primary { border-color: #1b8a50; background: #1b8a50; color: #fff; }
button:disabled { opacity: .55; cursor: wait; }
.fallback-panel { margin-top: 11px; padding-top: 11px; border-top: 1px solid #e8ede9; }
.fallback-row { display: flex; align-items: center; justify-content: space-between; gap: 12px; }
.fallback-row strong, .fallback-row span { display: block; }
.fallback-row strong, .manual-form > strong { color: #405047; font-size: 11px; }
.fallback-row span { margin-top: 3px; color: #89938c; font-size: 9px; }
.manual-form { display: grid; gap: 7px; margin-top: 12px; }
.manual-form > div { display: grid; grid-template-columns: 1fr 1fr; gap: 7px; }
.manual-form input { box-sizing: border-box; width: 100%; min-width: 0; padding: 8px 9px; border: 1px solid #dce4df; border-radius: 9px; outline: none; color: #34443a; font-size: 10px; }
.manual-form input:focus { border-color: #8cc8a0; }
.manual-form button { justify-self: start; border-color: #b8d9c3; color: #187744; }
@media (max-width: 620px) {
  .weather-heading, .fallback-row { align-items: flex-start; flex-direction: column; }
  .weather-metrics { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .manual-form > div { grid-template-columns: 1fr; }
}
</style>
