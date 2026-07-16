import { defineStore } from 'pinia'
import { updateDisplayLanguageApi } from '@/api/auth'

// 本地缓存键用于在刷新页面后恢复当前界面语言。
const LOCALE_KEY = 'rsod_locale'

export const useLocaleStore = defineStore('locale', {
  state: () => ({
    locale: localStorage.getItem(LOCALE_KEY) || 'zh',
  }),

  actions: {
    // 只接受 zh/en，非法值统一回退中文并同步到本地缓存。
    applyLocale(locale) {
      this.locale = locale === 'en' ? 'en' : 'zh'
      localStorage.setItem(LOCALE_KEY, this.locale)
    },

    // 先持久化到后端用户偏好，再更新当前浏览器的语言状态。
    async setLocale(locale) {
      const nextLocale = locale === 'en' ? 'en' : 'zh'
      await updateDisplayLanguageApi(nextLocale)
      this.applyLocale(nextLocale)
    },
  },
})
