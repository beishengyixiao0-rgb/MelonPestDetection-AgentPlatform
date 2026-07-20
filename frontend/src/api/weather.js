const WEATHER_CACHE_KEY = 'agriagent_current_weather'
const WEATHER_CACHE_TTL = 20 * 60 * 1000

const WEATHER_CODES = [
  { codes: [0], text: '晴', icon: '☀️' },
  { codes: [1, 2], text: '少云', icon: '🌤️' },
  { codes: [3], text: '多云', icon: '☁️' },
  { codes: [45, 48], text: '有雾', icon: '🌫️' },
  { codes: [51, 53, 55, 56, 57], text: '毛毛雨', icon: '🌦️' },
  { codes: [61, 63, 65, 66, 67, 80, 81, 82], text: '有雨', icon: '🌧️' },
  { codes: [71, 73, 75, 77, 85, 86], text: '有雪', icon: '🌨️' },
  { codes: [95, 96, 99], text: '雷雨', icon: '⛈️' },
]

const getWeatherDescription = (code) => (
  WEATHER_CODES.find((item) => item.codes.includes(Number(code)))
  || { text: '天气未知', icon: '🌦️' }
)

const fetchJson = async (url, options = {}, timeout = 5000) => {
  const controller = new AbortController()
  const timer = window.setTimeout(() => controller.abort(), timeout)

  try {
    const response = await fetch(url, {
      ...options,
      signal: controller.signal,
    })

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`)
    }

    return await response.json()
  } finally {
    window.clearTimeout(timer)
  }
}

const normalizeWeather = (raw, fallback = {}) => {
  const payload = raw?.data || raw || {}
  const current = payload.current || {}
  const temperature = Number(
    payload.temperature
    ?? payload.temperature_2m
    ?? current.temperature_2m,
  )
  const weatherCode = Number(
    payload.weather_code
    ?? payload.weatherCode
    ?? current.weather_code,
  )

  if (!Number.isFinite(temperature)) return null

  const description = getWeatherDescription(weatherCode)
  return {
    city: payload.city || fallback.city || '当前位置',
    latitude: Number(payload.latitude ?? fallback.latitude),
    longitude: Number(payload.longitude ?? fallback.longitude),
    temperature: Math.round(temperature),
    weatherCode: Number.isFinite(weatherCode) ? weatherCode : null,
    weatherText: payload.weather_text || payload.weatherText || description.text,
    icon: payload.icon || description.icon,
    updatedAt: payload.updated_at || payload.updatedAt || new Date().toISOString(),
    source: payload.source || fallback.source || 'backend',
  }
}

export const readWeatherCache = () => {
  try {
    const cache = JSON.parse(localStorage.getItem(WEATHER_CACHE_KEY) || 'null')
    if (!cache?.savedAt || Date.now() - cache.savedAt > WEATHER_CACHE_TTL) return null
    return cache.weather || null
  } catch {
    return null
  }
}

export const saveWeatherCache = (weather) => {
  try {
    localStorage.setItem(WEATHER_CACHE_KEY, JSON.stringify({
      savedAt: Date.now(),
      weather,
    }))
  } catch {
    // 隐私模式或存储空间不足时，天气展示仍可继续使用。
  }
}

const getBackendWeather = async () => {
  const token = localStorage.getItem('rsod_token')
  const headers = token ? { Authorization: `Bearer ${token}` } : {}
  const payload = await fetchJson('/api/common/weather', { headers }, 2500)
  return normalizeWeather(payload, { source: 'backend' })
}

export const getApproximateLocationByIp = async () => {
  const payload = await fetchJson('https://ipwho.is/?lang=zh-CN', {}, 5000)

  if (payload?.success === false) {
    throw new Error(payload.message || 'IP 定位失败')
  }

  const latitude = Number(payload?.latitude)
  const longitude = Number(payload?.longitude)
  if (!Number.isFinite(latitude) || !Number.isFinite(longitude)) {
    throw new Error('IP 定位未返回有效坐标')
  }

  return {
    city: payload.city || payload.region || payload.country || '当前位置',
    latitude,
    longitude,
  }
}

export const getWeatherByCoordinates = async (location) => {
  const query = new URLSearchParams({
    latitude: String(location.latitude),
    longitude: String(location.longitude),
    current: 'temperature_2m,weather_code',
    temperature_unit: 'celsius',
    timezone: 'auto',
  })
  const payload = await fetchJson(
    `https://api.open-meteo.com/v1/forecast?${query.toString()}`,
    {},
    7000,
  )

  return normalizeWeather(payload, {
    ...location,
    source: 'open-meteo',
  })
}

/**
 * 获取首页当前天气：本地缓存 → 预留后端接口 → IP 定位与公开天气服务。
 * 所有异常由调用组件降级处理，不触发现有 Axios 全局错误弹窗。
 */
export const getCurrentWeather = async ({ force = false } = {}) => {
  if (!force) {
    const cached = readWeatherCache()
    if (cached) return cached
  }

  try {
    const backendWeather = await getBackendWeather()
    if (backendWeather) {
      saveWeatherCache(backendWeather)
      return backendWeather
    }
  } catch {
    // 后端接口尚未实现时，静默转入前端真实天气降级流程。
  }

  const location = await getApproximateLocationByIp()
  const weather = await getWeatherByCoordinates(location)
  if (!weather) throw new Error('天气服务未返回有效数据')

  saveWeatherCache(weather)
  return weather
}
