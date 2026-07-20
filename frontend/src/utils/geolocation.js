/**
 * 浏览器定位封装。
 * 定位必须由用户操作触发；局域网 HTTP 页面不属于安全上下文，需使用 HTTPS 或 fallback。
 */
export class BrowserLocationError extends Error {
  constructor(code, message) {
    super(message)
    this.name = 'BrowserLocationError'
    this.code = code
  }
}

const isLocalhost = () => ['localhost', '127.0.0.1', '::1'].includes(window.location.hostname)

export function getBrowserLocation({ timeout = 12000 } = {}) {
  if (!window.isSecureContext && !isLocalhost()) {
    return Promise.reject(new BrowserLocationError(
      'insecure_context',
      '当前页面不是 HTTPS，浏览器已禁用精确定位。',
    ))
  }

  if (!navigator.geolocation) {
    return Promise.reject(new BrowserLocationError('unsupported', '当前浏览器不支持地理位置。'))
  }

  return new Promise((resolve, reject) => {
    navigator.geolocation.getCurrentPosition(
      (position) => resolve({
        latitude: position.coords.latitude,
        longitude: position.coords.longitude,
        accuracy: position.coords.accuracy,
        source: 'browser',
      }),
      (error) => {
        const errors = {
          1: ['permission_denied', '你没有允许位置授权。'],
          2: ['position_unavailable', '暂时无法获取当前位置。'],
          3: ['timeout', '定位超时，请重试。'],
        }
        const [code, message] = errors[error.code] || ['unknown', '定位失败，请重试。']
        reject(new BrowserLocationError(code, message))
      },
      { enableHighAccuracy: true, timeout, maximumAge: 5 * 60 * 1000 },
    )
  })
}

export function coordinateLabel(latitude, longitude, locale = 'zh') {
  const lat = Number(latitude)
  const lng = Number(longitude)
  if (!Number.isFinite(lat) || !Number.isFinite(lng)) {
    return locale === 'en' ? 'Current location' : '当前位置'
  }
  return `${lat.toFixed(4)}, ${lng.toFixed(4)}`
}
