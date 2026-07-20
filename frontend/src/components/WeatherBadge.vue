<template>
  <button
    type="button"
    class="weather-badge"
    :class="[`status-${status}`, { approximate: weather.approximate }]"
    :title="badgeTitle"
    :disabled="status === 'loading'"
    @click="loadWeather"
  >
    <template v-if="status === 'success'">
      <span class="weather-icon">{{ weather.icon }}</span>
      <span>{{ weather.city }}</span>
      <i />
      <strong>{{ weather.temperature }}°C</strong>
      <i />
      <span>{{ weather.weatherText }}</span>
      <small v-if="weather.approximate">{{ copy.approximate }}</small>
    </template>

    <template v-else-if="status === 'loading'">
      <span class="weather-icon">🌦️</span>
      <span>{{ copy.locating }}</span>
    </template>

    <template v-else-if="status === 'error'">
      <span class="weather-icon">🌿</span>
      <span>{{ copy.retry }}</span>
    </template>

    <template v-else>
      <span class="weather-icon">📍</span>
      <span>{{ copy.enable }}</span>
    </template>
  </button>
</template>

<script setup>
import { getApproximateLocationByIp, getWeatherByCoordinates, readWeatherCache, saveWeatherCache } from '@/api/weather'
import { getBrowserLocation } from '@/utils/geolocation'
import { useLocaleStore } from '@/stores/locale'
import { computed, onMounted, ref } from 'vue'

const localeStore = useLocaleStore()
const status = ref('idle')
const weather = ref({})
const lastError = ref('')

const copy = computed(() => localeStore.locale === 'en'
  ? { enable: 'Enable local weather', locating: 'Locating and loading weather…', retry: 'Weather unavailable · retry', approximate: 'Approx.' }
  : { enable: '获取当地天气', locating: '正在定位并获取天气…', retry: '天气暂不可用 · 重试', approximate: '约' })

const badgeTitle = computed(() => {
  if (status.value === 'error') return lastError.value
  if (status.value !== 'success') return copy.value.enable
  const updated = new Date(weather.value.updatedAt).toLocaleString(localeStore.locale === 'en' ? 'en-US' : 'zh-CN')
  const source = weather.value.approximate
    ? (localeStore.locale === 'en' ? 'Approximate IP location' : 'IP 估算位置')
    : (localeStore.locale === 'en' ? 'Browser location' : '浏览器精确定位')
  return `${source} · ${updated}`
})

async function loadWeather() {
  if (status.value === 'loading') return
  status.value = 'loading'
  lastError.value = ''

  try {
    const location = await getBrowserLocation()
    weather.value = {
      ...await getWeatherByCoordinates({
        ...location,
        city: localeStore.locale === 'en' ? 'Current location' : '当前位置',
      }),
      approximate: false,
    }
    saveWeatherCache(weather.value)
    status.value = 'success'
    return
  } catch (error) {
    lastError.value = error?.message || String(error)
  }

  try {
    const approximateLocation = await getApproximateLocationByIp()
    weather.value = {
      ...await getWeatherByCoordinates(approximateLocation),
      approximate: true,
    }
    saveWeatherCache(weather.value)
    status.value = 'success'
  } catch (error) {
    lastError.value = `${lastError.value} ${error?.message || String(error)}`.trim()
    status.value = 'error'
  }
}

onMounted(() => {
  const cached = readWeatherCache()
  if (!cached) return
  weather.value = cached
  status.value = 'success'
})
</script>

<style scoped>
.weather-badge {
  display: inline-flex;
  min-height: 34px;
  align-items: center;
  gap: 7px;
  padding: 7px 14px;
  border: 1px solid #d1fae5;
  border-radius: 999px;
  background: #ecfdf5;
  color: #15803d;
  font: inherit;
  font-size: 12px;
  font-weight: 600;
  box-shadow: 0 5px 16px rgba(22, 101, 52, 0.06);
  cursor: pointer;
}
.weather-badge:disabled { cursor: wait; }
.weather-badge i { width: 3px; height: 3px; border-radius: 50%; background: #86efac; }
.weather-badge small { padding: 2px 5px; border-radius: 999px; background: #fff6d8; color: #9a6700; font-size: 9px; }
.weather-icon { font-size: 15px; }
.status-loading .weather-icon { animation: weather-pulse 1.4s ease-in-out infinite; }
.status-error { border-color: #e2e7e3; background: #f6f8f6; color: #66736a; }
.weather-badge.approximate { border-color: #e9dfb9; background: #fffdf5; color: #52705d; }
@keyframes weather-pulse { 50% { opacity: .45; transform: translateY(-1px); } }
</style>
