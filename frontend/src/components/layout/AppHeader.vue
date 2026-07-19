<template>
  <header class="app-header">
    <!-- 左侧：Logo + 平台名称 -->
    <div class="header-left">
      <img src="/favicon.svg" alt="logo" class="header-logo" />
      <span class="header-title">RSOD Agent Platform</span>
    </div>

    <!-- 右侧：语言、用户信息 + 退出按钮 -->
    <div class="header-right">
      <el-button
        v-if="canRebuildKnowledgeIndex"
        :icon="Refresh"
        :loading="rebuildingKnowledgeIndex"
        @click="rebuildKnowledgeIndex"
      >
        {{ t('knowledge.rebuildIndex') }}
      </el-button>
      <el-button-group class="language-switch" aria-label="Language">
        <el-button :type="localeStore.locale === 'zh' ? 'primary' : 'default'" @click="setLocale('zh')">{{ t('language.zh') }}</el-button>
        <el-button :type="localeStore.locale === 'en' ? 'primary' : 'default'" @click="setLocale('en')">{{ t('language.en') }}</el-button>
      </el-button-group>
      <el-dropdown trigger="click" @command="handleCommand">
        <div class="user-info">
          <el-avatar :size="32" :src="userStore.avatar || undefined">
            {{ userStore.username?.charAt(0)?.toUpperCase() }}
          </el-avatar>
          <span class="username">{{ userStore.username }}</span>
          <el-icon><ArrowDown /></el-icon>
        </div>
        <template #dropdown>
          <el-dropdown-menu>
            <el-dropdown-item command="profile">
              <el-icon><User /></el-icon>个人中心
            </el-dropdown-item>
            <el-dropdown-item command="logout" divided>
              <el-icon><SwitchButton /></el-icon>退出登录
            </el-dropdown-item>
          </el-dropdown-menu>
        </template>
      </el-dropdown>
    </div>
  </header>
</template>

<script setup>
import { computed, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ArrowDown, User, SwitchButton, Refresh } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { rebuildKnowledgeIndexApi } from '@/api/knowledge'
import { useUserStore } from '@/stores/user'
import { useLocaleStore } from '@/stores/locale'
import { t as translate } from '@/utils/i18n'

const router = useRouter()
const userStore = useUserStore()
const localeStore = useLocaleStore()
// 重建索引会执行外部 Embedding 请求，执行期间禁用重复点击。
const rebuildingKnowledgeIndex = ref(false)
// 读取响应式语言状态，切换后顶栏文案会自动重新渲染。
const t = (key) => translate(key, localeStore.locale)

// 仅管理员可见该高成本操作；兼容旧用户信息中的 is_superuser 字段。
const canRebuildKnowledgeIndex = computed(() => {
  return userStore.isSuperuser || userStore.roles.includes('admin')
})

/** 管理员确认后强制重建知识库向量索引。 */
async function rebuildKnowledgeIndex() {
  try {
    await ElMessageBox.confirm(
      t('knowledge.rebuildConfirm'),
      t('common.tip'),
      {
        confirmButtonText: t('common.confirm'),
        cancelButtonText: t('common.cancel'),
        type: 'warning',
      },
    )
  } catch {
    // 用户取消确认框时不发起接口请求。
    return
  }

  rebuildingKnowledgeIndex.value = true
  try {
    await rebuildKnowledgeIndexApi()
    ElMessage.success(t('knowledge.rebuildSuccess'))
  } catch {
    // Axios 响应拦截器已统一展示后端返回的失败原因。
  } finally {
    rebuildingKnowledgeIndex.value = false
  }
}

/** 保存用户语言偏好后再切换当前界面，避免前后端状态不一致。 */
async function setLocale(locale) {
  if (locale === localeStore.locale) return
  try {
    await localeStore.setLocale(locale)
    ElMessage.success(t('language.changed'))
  } catch {
    ElMessage.error(t('language.failed'))
  }
}

/** 处理下拉菜单命令 */
function handleCommand(command) {
  switch (command) {
    case 'profile':
      // 个人中心（后续实现）
      break
    case 'logout':
      ElMessageBox.confirm(t('user.logoutConfirm'), t('common.tip'), {
        confirmButtonText: t('common.confirm'),
        cancelButtonText: t('common.cancel'),
        type: 'warning',
      })
        .then(() => {
          userStore.logout()
          router.push('/login')
        })
        .catch(() => {})
      break
  }
}
</script>

<style lang="scss" scoped>
.app-header {
  height: $header-height;
  background: #fff;
  border-bottom: 1px solid #ebeef5;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 $spacing-lg;
  box-shadow: $shadow-sm;
  z-index: 100;
}

.header-left {
  display: flex;
  align-items: center;
  gap: $spacing-sm;
}

.header-logo {
  width: 28px;
  height: 28px;
}

.header-title {
  font-size: 16px;
  font-weight: 600;
  color: $text-primary;
}

.header-right {
  display: flex;
  align-items: center;
  gap: $spacing-md;
}

.language-switch :deep(.el-button) {
  min-width: 48px;
}

.user-info {
  display: flex;
  align-items: center;
  gap: $spacing-sm;
  cursor: pointer;
  padding: 4px 8px;
  border-radius: $border-radius-sm;
  transition: background 0.2s;

  &:hover {
    background: #f5f7fa;
  }
}

.username {
  font-size: 14px;
  color: $text-primary;
}
</style>
