<template>
  <div class="user-menu" @mouseenter="open = true" @mouseleave="open = false">
    <button class="user-trigger" type="button" @click="open = !open">
      <span class="avatar">{{ userInitial }}</span>
      <span class="user-meta">
        <strong>{{ userStore.username || 'User' }}</strong>
        <small>{{ roleLabel }}</small>
      </span>
    </button>

    <div v-if="open" class="user-dropdown">
      <div class="dropdown-header">
        <span class="avatar large">{{ userInitial }}</span>
        <div class="dropdown-identity">
          <strong>{{ userStore.username || 'User' }}</strong>
          <span :class="{ admin: userStore.isAdmin }">{{ roleLabel }}</span>
        </div>
      </div>

      <div class="dropdown-body">
        <div class="info-row">
          <span>{{ tr('home.email') }}</span>
          <strong>{{ userStore.user?.email || '—' }}</strong>
        </div>
        <div class="info-row">
          <span>{{ tr('home.accountStatus') }}</span>
          <strong :class="userStore.user?.is_active === false ? 'disabled' : 'active'">
            {{ userStore.user?.is_active === false ? tr('home.disabled') : tr('home.active') }}
          </strong>
        </div>
        <div class="info-row">
          <span>{{ tr('home.lastLogin') }}</span>
          <strong>{{ formatDate(userStore.user?.last_login_at) }}</strong>
        </div>
      </div>

      <div v-if="userStore.user?.detection_stats" class="profile-stats">
        <div><strong>{{ userStore.user.detection_stats.total_tasks ?? 0 }}</strong><span>{{ tr('home.tasks') }}</span></div>
        <div><strong>{{ userStore.user.detection_stats.total_objects ?? 0 }}</strong><span>{{ tr('home.objects') }}</span></div>
      </div>

      <router-link v-if="userStore.isAdmin" to="/admin" class="admin-link" @click="open = false">
        ⚙️ {{ tr('admin.entry') }}
      </router-link>

      <button class="profile-edit-button" type="button" @click="openProfileEditor">
        {{ tr('profile.editAction') }}
      </button>

      <button class="logout-button" type="button" @click="logout">{{ tr('user.logout') }}</button>
    </div>

    <ProfileEditDialog v-model="profileEditorOpen" />
  </div>
</template>

<script setup>
import ProfileEditDialog from '@/components/ProfileEditDialog.vue'
import { useLocaleStore } from '@/stores/locale'
import { useUserStore } from '@/stores/user'
import { t } from '@/utils/i18n'
import { ElMessage } from 'element-plus'
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'

const router = useRouter()
const userStore = useUserStore()
const localeStore = useLocaleStore()
const tr = (key, params) => t(key, localeStore.locale, params)
const open = ref(false)
const profileEditorOpen = ref(false)

const roleLabel = computed(() => (userStore.isAdmin ? tr('home.admin') : tr('home.user')))
const userInitial = computed(() => (userStore.username || 'U').charAt(0).toUpperCase())

const formatDate = (value) => {
  if (!value) return '—'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return '—'
  return date.toLocaleString(localeStore.locale === 'en' ? 'en-US' : 'zh-CN', {
    month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit',
  })
}

const logout = () => {
  userStore.logout()
  open.value = false
  ElMessage.success(tr('home.logoutDone'))
  router.push('/login')
}

const openProfileEditor = () => {
  open.value = false
  profileEditorOpen.value = true
}

onMounted(async () => {
  try {
    await userStore.fetchUserProfile()
  } catch (error) {
    console.warn('[用户资料刷新失败]', error)
  }
})
</script>

<style scoped>
.user-menu { position: relative; }
.user-trigger {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 10px;
  border: 0;
  border-radius: 999px;
  background: #f3f4f6;
  cursor: pointer;
}
.avatar {
  display: inline-flex;
  width: 32px;
  height: 32px;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
  background: linear-gradient(135deg, #16a34a, #22c55e);
  color: #fff;
  font-weight: 750;
}
.avatar.large { width: 42px; height: 42px; font-size: 18px; }
.user-meta { display: flex; flex-direction: column; align-items: flex-start; line-height: 1.2; }
.user-meta small { color: #6b7280; }
.user-dropdown {
  position: absolute;
  top: calc(100% + 8px);
  right: 0;
  z-index: 50;
  width: 300px;
  padding: 14px;
  border: 1px solid #e5e7eb;
  border-radius: 16px;
  background: #fff;
  box-shadow: 0 12px 30px rgba(0,0,0,.1);
}
.dropdown-header { display: flex; align-items: center; gap: 10px; padding-bottom: 11px; border-bottom: 1px solid #f0f2f1; }
.dropdown-identity { display: flex; min-width: 0; flex-direction: column; gap: 2px; }
.dropdown-identity span { color: #6b7280; font-size: 12px; }
.dropdown-identity span.admin { color: #b45309; font-weight: 700; }
.dropdown-body { display: flex; flex-direction: column; gap: 8px; padding: 12px 0; }
.info-row { display: flex; justify-content: space-between; gap: 10px; font-size: 13px; }
.info-row > span { color: #6b7280; }
.info-row strong { max-width: 185px; overflow-wrap: anywhere; color: #374151; text-align: right; }
.info-row .active { color: #15803d; }
.info-row .disabled { color: #dc2626; }
.profile-stats { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; margin-bottom: 10px; }
.profile-stats div { display: flex; flex-direction: column; align-items: center; padding: 9px; border-radius: 10px; background: #f0fdf4; }
.profile-stats strong { color: #166534; }
.profile-stats span { color: #6b7280; font-size: 11px; }
.admin-link,
.profile-edit-button,
.logout-button {
  display: block;
  box-sizing: border-box;
  width: 100%;
  padding: 10px 12px;
  border: 0;
  border-radius: 10px;
  cursor: pointer;
  font-size: 13px;
  font-weight: 700;
  text-align: center;
  text-decoration: none;
}
.admin-link { margin-bottom: 8px; background: #ecfdf5; color: #15803d; }
.admin-link:hover { background: #dcfce7; }
.profile-edit-button { margin-bottom: 8px; background: #f0fdf4; color: #166534; }
.profile-edit-button:hover { background: #dcfce7; }
.logout-button { background: #fef2f2; color: #dc2626; }

@media (max-width: 760px) {
  .user-meta { display: none; }
  .user-dropdown { width: min(300px, calc(100vw - 24px)); }
}
</style>
