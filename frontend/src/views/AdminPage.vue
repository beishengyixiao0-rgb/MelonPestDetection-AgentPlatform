<template>
  <div class="admin-page">
    <header class="admin-header">
      <div class="header-left">
        <router-link to="/" class="back-button">←</router-link>
        <router-link to="/" class="brand">🌿 AgriAgent</router-link>
        <span class="divider" />
        <strong>{{ copy.title }}</strong>
      </div>
      <div class="header-right">
        <LanguageSwitcher />
        <router-link to="/" class="home-link">{{ copy.home }}</router-link>
      </div>
    </header>

    <main class="admin-container">
      <div class="page-title">
        <div>
          <h1>{{ copy.title }}</h1>
          <p>{{ copy.subtitle }}</p>
        </div>
      </div>

      <div class="tab-bar">
        <button type="button" :class="{ active: activeTab === 'users' }" @click="activeTab = 'users'">
          {{ copy.users }}
        </button>
        <button type="button" :class="{ active: activeTab === 'knowledge' }" @click="activeTab = 'knowledge'">
          {{ copy.knowledge }}
        </button>
      </div>

      <section v-if="activeTab === 'users'" class="panel">
        <div class="panel-header">
          <div>
            <h2>{{ copy.userManagement }}</h2>
            <p>{{ copy.userCount(users.length) }}</p>
          </div>
          <div class="panel-actions">
            <button class="secondary-button" type="button" :disabled="usersLoading" @click="fetchUsers">{{ copy.refresh }}</button>
            <button class="primary-button" type="button" @click="openCreateUser">+ {{ copy.createUser }}</button>
          </div>
        </div>

        <div class="table-wrap">
          <el-table v-loading="usersLoading" :data="users" empty-text="--" row-key="id">
            <el-table-column prop="username" :label="copy.username" min-width="130" />
            <el-table-column prop="email" :label="copy.email" min-width="210" />
            <el-table-column prop="phone" :label="copy.phone" min-width="130">
              <template #default="{ row }">{{ row.phone || '—' }}</template>
            </el-table-column>
            <el-table-column :label="copy.role" width="120">
              <template #default="{ row }">
                <span class="role-tag" :class="{ admin: row.roles?.includes('admin') }">
                  {{ row.roles?.includes('admin') ? copy.admin : copy.user }}
                </span>
              </template>
            </el-table-column>
            <el-table-column :label="copy.status" width="100">
              <template #default="{ row }">
                <span class="state-dot" :class="row.is_active ? 'active' : 'disabled'">
                  {{ row.is_active ? copy.active : copy.disabled }}
                </span>
              </template>
            </el-table-column>
            <el-table-column :label="copy.createdAt" min-width="160">
              <template #default="{ row }">{{ formatDate(row.created_at) }}</template>
            </el-table-column>
            <el-table-column :label="copy.actions" width="170" fixed="right">
              <template #default="{ row }">
                <button class="text-button" type="button" @click="openEditUser(row)">{{ copy.edit }}</button>
                <button
                  class="text-button danger"
                  type="button"
                  :disabled="!row.is_active || row.id === userStore.user?.id"
                  @click="disableUser(row)"
                >{{ copy.disable }}</button>
              </template>
            </el-table-column>
          </el-table>
        </div>
      </section>

      <section v-else class="panel">
        <div class="panel-header">
          <div>
            <h2>{{ copy.knowledgeManagement }}</h2>
            <p>{{ copy.documentCount(knowledgePagination.total) }}</p>
          </div>
          <div class="panel-actions">
            <el-select v-model="knowledgeStatus" clearable :placeholder="copy.allStatuses" style="width: 150px" @change="resetKnowledgePage">
              <el-option :label="copy.pending" value="pending" />
              <el-option :label="copy.approved" value="approved" />
              <el-option :label="copy.rejected" value="rejected" />
              <el-option :label="copy.processing" value="processing" />
              <el-option :label="copy.failed" value="failed" />
            </el-select>
            <button class="secondary-button" type="button" :disabled="knowledgeLoading" @click="fetchKnowledge">{{ copy.refresh }}</button>
          </div>
        </div>

        <div class="table-wrap">
          <el-table v-loading="knowledgeLoading" :data="documents" empty-text="--" row-key="id">
            <el-table-column prop="title" :label="copy.document" min-width="210" />
            <el-table-column prop="uploader_name" :label="copy.submitter" min-width="120">
              <template #default="{ row }">{{ row.uploader_name || `#${row.uploader_id}` }}</template>
            </el-table-column>
            <el-table-column :label="copy.status" width="115">
              <template #default="{ row }">
                <span class="knowledge-status" :class="`status-${row.status}`">{{ statusLabel(row.status) }}</span>
              </template>
            </el-table-column>
            <el-table-column prop="chunk_count" :label="copy.chunks" width="90">
              <template #default="{ row }">{{ row.chunk_count ?? 0 }}</template>
            </el-table-column>
            <el-table-column :label="copy.submittedAt" min-width="165">
              <template #default="{ row }">{{ formatDate(row.created_at) }}</template>
            </el-table-column>
            <el-table-column :label="copy.reviewComment" min-width="180">
              <template #default="{ row }">{{ row.review_comment || '—' }}</template>
            </el-table-column>
            <el-table-column :label="copy.actions" width="300" fixed="right">
              <template #default="{ row }">
                <button class="text-button" type="button" @click="previewDocument(row)">{{ copy.preview }}</button>
                <button v-if="row.status === 'pending'" class="text-button success" type="button" :disabled="isDocumentBusy(row.id)" @click="approveDocument(row)">{{ copy.approve }}</button>
                <button v-if="row.status === 'pending'" class="text-button warning" type="button" :disabled="isDocumentBusy(row.id)" @click="openReject(row)">{{ copy.reject }}</button>
                <button v-if="row.status === 'approved'" class="text-button" type="button" :disabled="isDocumentBusy(row.id)" @click="reindexDocument(row)">{{ copy.reindex }}</button>
                <button class="text-button danger" type="button" :disabled="isDocumentBusy(row.id)" @click="deleteDocument(row)">{{ copy.delete }}</button>
              </template>
            </el-table-column>
          </el-table>
        </div>

        <div v-if="knowledgePagination.totalPages > 1" class="pagination-row">
          <el-pagination
            v-model:current-page="knowledgePagination.page"
            background
            layout="prev, pager, next"
            :page-size="knowledgePagination.pageSize"
            :total="knowledgePagination.total"
            @current-change="fetchKnowledge"
          />
        </div>
      </section>
    </main>

    <el-dialog v-model="userDialogVisible" :title="editingUserId ? copy.editUser : copy.createUser" width="min(480px, 92vw)" destroy-on-close>
      <el-form label-position="top">
        <el-form-item :label="copy.username" required><el-input v-model.trim="userForm.username" maxlength="50" /></el-form-item>
        <el-form-item :label="copy.email" required><el-input v-model.trim="userForm.email" type="email" /></el-form-item>
        <el-form-item :label="copy.phone"><el-input v-model.trim="userForm.phone" /></el-form-item>
        <el-form-item v-if="!editingUserId" :label="copy.password" required><el-input v-model="userForm.password" type="password" show-password /></el-form-item>
        <el-form-item v-if="editingUserId" :label="copy.role">
          <el-select v-model="userForm.role_name" style="width: 100%">
            <el-option :label="copy.user" value="user" />
            <el-option :label="copy.admin" value="admin" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <button class="secondary-button" type="button" @click="userDialogVisible = false">{{ copy.cancel }}</button>
        <button class="primary-button" type="button" :disabled="savingUser" @click="saveUser">{{ copy.save }}</button>
      </template>
    </el-dialog>

    <el-dialog v-model="rejectDialogVisible" :title="copy.rejectDocument" width="min(460px, 92vw)" destroy-on-close>
      <el-input v-model.trim="rejectComment" type="textarea" :rows="4" maxlength="500" show-word-limit :placeholder="copy.rejectReason" />
      <template #footer>
        <button class="secondary-button" type="button" @click="rejectDialogVisible = false">{{ copy.cancel }}</button>
        <button class="danger-button" type="button" :disabled="!rejectComment || rejecting" @click="confirmReject">{{ copy.reject }}</button>
      </template>
    </el-dialog>

    <el-dialog
      v-model="previewDialogVisible"
      :title="previewDocumentData?.title || copy.preview"
      width="min(820px, 94vw)"
      destroy-on-close
    >
      <div v-loading="previewLoading" class="document-preview">
        <div v-if="previewDocumentData" class="preview-meta">
          <span>{{ copy.submitter }}：{{ previewDocumentData.uploader_name || `#${previewDocumentData.uploader_id}` }}</span>
          <span>{{ copy.submittedAt }}：{{ formatDate(previewDocumentData.created_at) }}</span>
          <span class="knowledge-status" :class="`status-${previewDocumentData.status}`">{{ statusLabel(previewDocumentData.status) }}</span>
        </div>
        <pre v-if="previewDocumentData?.content">{{ previewDocumentData.content }}</pre>
        <div v-else-if="!previewLoading" class="preview-empty">{{ copy.noContent }}</div>
      </div>
      <template #footer>
        <button class="secondary-button" type="button" @click="previewDialogVisible = false">{{ copy.close }}</button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { createAdminUserApi, disableAdminUserApi, getAdminUsersApi, updateAdminUserApi } from '@/api/admin'
import {
  approveKnowledgeDocumentApi,
  deleteKnowledgeDocumentApi,
  getAdminKnowledgeDocumentsApi,
  getKnowledgeDocumentDetailApi,
  reindexKnowledgeDocumentApi,
  rejectKnowledgeDocumentApi,
} from '@/api/knowledge'
import LanguageSwitcher from '@/components/LanguageSwitcher.vue'
import { useLocaleStore } from '@/stores/locale'
import { useUserStore } from '@/stores/user'
import { ElMessage, ElMessageBox } from 'element-plus'
import { computed, onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'

const COPY = {
  zh: {
    title: '管理中心', subtitle: '管理用户与知识投稿。', home: '返回首页', users: '用户管理', knowledge: '知识审核',
    userManagement: '用户', knowledgeManagement: '知识投稿', refresh: '刷新', createUser: '新建用户', username: '用户名', email: '邮箱', phone: '手机号',
    role: '角色', status: '状态', createdAt: '创建时间', actions: '操作', admin: '管理员', user: '普通用户', active: '正常', disabled: '已禁用',
    edit: '编辑', disable: '禁用', editUser: '编辑用户', password: '密码', cancel: '取消', save: '保存', document: '文档', submitter: '提交人', chunks: '分块',
    submittedAt: '提交时间', reviewComment: '审核意见', allStatuses: '全部状态', pending: '待审核', approved: '已发布', rejected: '已驳回',
    processing: '处理中', failed: '失败', approve: '通过', reject: '驳回', reindex: '重建索引', delete: '删除', rejectDocument: '驳回文档', rejectReason: '请输入驳回原因',
    preview: '预览', noContent: '文档内容为空或文件无法读取', close: '关闭',
    disableConfirm: (name) => `确定禁用用户“${name}”？`, deleteConfirm: (name) => `确定删除文档“${name}”？`, approveConfirm: (name) => `通过“${name}”并加入知识库？`,
    reindexConfirm: (name) => `重新构建“${name}”的索引？`, userCount: (count) => `${count} 个用户`, documentCount: (count) => `${count} 条记录`,
    saved: '用户信息已保存', created: '用户已创建', disabledDone: '用户已禁用', approvedDone: '文档已发布', rejectedDone: '文档已驳回',
    deletedDone: '文档已删除', reindexedDone: '索引已重建', required: '请填写必填项', passwordLength: '密码至少 6 位', noPermission: '仅管理员可访问',
  },
  en: {
    title: 'Admin', subtitle: 'Manage users and knowledge submissions.', home: 'Home', users: 'Users', knowledge: 'Knowledge review',
    userManagement: 'Users', knowledgeManagement: 'Knowledge submissions', refresh: 'Refresh', createUser: 'New user', username: 'Username', email: 'Email', phone: 'Phone',
    role: 'Role', status: 'Status', createdAt: 'Created', actions: 'Actions', admin: 'Admin', user: 'User', active: 'Active', disabled: 'Disabled',
    edit: 'Edit', disable: 'Disable', editUser: 'Edit user', password: 'Password', cancel: 'Cancel', save: 'Save', document: 'Document', submitter: 'Submitter', chunks: 'Chunks',
    submittedAt: 'Submitted', reviewComment: 'Review comment', allStatuses: 'All statuses', pending: 'Pending', approved: 'Published', rejected: 'Rejected',
    processing: 'Processing', failed: 'Failed', approve: 'Approve', reject: 'Reject', reindex: 'Reindex', delete: 'Delete', rejectDocument: 'Reject document', rejectReason: 'Reason for rejection',
    preview: 'Preview', noContent: 'The document is empty or cannot be read', close: 'Close',
    disableConfirm: (name) => `Disable user "${name}"?`, deleteConfirm: (name) => `Delete document "${name}"?`, approveConfirm: (name) => `Approve "${name}" and publish it?`,
    reindexConfirm: (name) => `Rebuild the index for "${name}"?`, userCount: (count) => `${count} users`, documentCount: (count) => `${count} records`,
    saved: 'User saved', created: 'User created', disabledDone: 'User disabled', approvedDone: 'Document published', rejectedDone: 'Document rejected',
    deletedDone: 'Document deleted', reindexedDone: 'Index rebuilt', required: 'Complete the required fields', passwordLength: 'Password must be at least 6 characters', noPermission: 'Administrator access required',
  },
}

const router = useRouter()
const userStore = useUserStore()
const localeStore = useLocaleStore()
const copy = computed(() => COPY[localeStore.locale === 'en' ? 'en' : 'zh'])
const activeTab = ref('users')

const users = ref([])
const usersLoading = ref(false)
const userDialogVisible = ref(false)
const editingUserId = ref(null)
const savingUser = ref(false)
const userForm = reactive({ username: '', email: '', phone: '', password: '', role_name: 'user' })

const documents = ref([])
const knowledgeLoading = ref(false)
const knowledgeStatus = ref('')
const knowledgePagination = reactive({ page: 1, pageSize: 15, total: 0, totalPages: 0 })
const busyDocumentIds = ref(new Set())
const rejectDialogVisible = ref(false)
const rejecting = ref(false)
const rejectingDocument = ref(null)
const rejectComment = ref('')
const previewDialogVisible = ref(false)
const previewLoading = ref(false)
const previewDocumentData = ref(null)

const formatDate = (value) => {
  if (!value) return '—'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return '—'
  return date.toLocaleString(localeStore.locale === 'en' ? 'en-US' : 'zh-CN', {
    year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit',
  })
}

const statusLabel = (status) => copy.value[status] || status

const fetchUsers = async () => {
  usersLoading.value = true
  try {
    const result = await getAdminUsersApi()
    users.value = Array.isArray(result?.data) ? result.data : []
  } finally {
    usersLoading.value = false
  }
}

const resetUserForm = () => Object.assign(userForm, { username: '', email: '', phone: '', password: '', role_name: 'user' })
const openCreateUser = () => {
  editingUserId.value = null
  resetUserForm()
  userDialogVisible.value = true
}
const openEditUser = (row) => {
  editingUserId.value = row.id
  Object.assign(userForm, {
    username: row.username || '', email: row.email || '', phone: row.phone || '', password: '',
    role_name: row.roles?.includes('admin') ? 'admin' : 'user',
  })
  userDialogVisible.value = true
}

const saveUser = async () => {
  if (!userForm.username || !userForm.email) return ElMessage.warning(copy.value.required)
  if (!editingUserId.value && userForm.password.length < 6) return ElMessage.warning(copy.value.passwordLength)
  savingUser.value = true
  try {
    if (editingUserId.value) {
      await updateAdminUserApi(editingUserId.value, {
        username: userForm.username, email: userForm.email, phone: userForm.phone, role_name: userForm.role_name,
      })
      ElMessage.success(copy.value.saved)
    } else {
      await createAdminUserApi({
        username: userForm.username, email: userForm.email, password: userForm.password,
        ...(userForm.phone ? { phone: userForm.phone } : {}),
      })
      ElMessage.success(copy.value.created)
    }
    userDialogVisible.value = false
    await fetchUsers()
  } finally {
    savingUser.value = false
  }
}

const disableUser = async (row) => {
  try {
    await ElMessageBox.confirm(copy.value.disableConfirm(row.username), copy.value.disable, { type: 'warning' })
  } catch {
    return
  }
  await disableAdminUserApi(row.id)
  ElMessage.success(copy.value.disabledDone)
  await fetchUsers()
}

const fetchKnowledge = async () => {
  knowledgeLoading.value = true
  try {
    const result = await getAdminKnowledgeDocumentsApi({
      page: knowledgePagination.page,
      page_size: knowledgePagination.pageSize,
      ...(knowledgeStatus.value ? { status: knowledgeStatus.value } : {}),
    })
    documents.value = Array.isArray(result?.items) ? result.items : []
    knowledgePagination.total = Number(result?.total || 0)
    knowledgePagination.totalPages = Number(result?.total_pages || 0)
  } finally {
    knowledgeLoading.value = false
  }
}

const resetKnowledgePage = () => {
  knowledgePagination.page = 1
  fetchKnowledge()
}

const markDocumentBusy = (id, busy) => {
  const next = new Set(busyDocumentIds.value)
  if (busy) next.add(id)
  else next.delete(id)
  busyDocumentIds.value = next
}
const isDocumentBusy = (id) => busyDocumentIds.value.has(id)

const approveDocument = async (row) => {
  try {
    await ElMessageBox.confirm(copy.value.approveConfirm(row.title), copy.value.approve, { type: 'warning' })
  } catch {
    return
  }
  markDocumentBusy(row.id, true)
  try {
    await approveKnowledgeDocumentApi(row.id)
    ElMessage.success(copy.value.approvedDone)
    await fetchKnowledge()
  } finally {
    markDocumentBusy(row.id, false)
  }
}

const openReject = (row) => {
  rejectingDocument.value = row
  rejectComment.value = ''
  rejectDialogVisible.value = true
}

const previewDocument = async (row) => {
  previewDialogVisible.value = true
  previewLoading.value = true
  previewDocumentData.value = { ...row, content: '' }
  try {
    previewDocumentData.value = await getKnowledgeDocumentDetailApi(row.id)
  } finally {
    previewLoading.value = false
  }
}

const confirmReject = async () => {
  if (!rejectingDocument.value || !rejectComment.value) return
  rejecting.value = true
  try {
    await rejectKnowledgeDocumentApi(rejectingDocument.value.id, rejectComment.value)
    ElMessage.success(copy.value.rejectedDone)
    rejectDialogVisible.value = false
    await fetchKnowledge()
  } finally {
    rejecting.value = false
  }
}

const deleteDocument = async (row) => {
  try {
    await ElMessageBox.confirm(copy.value.deleteConfirm(row.title), copy.value.delete, { type: 'warning' })
  } catch {
    return
  }
  markDocumentBusy(row.id, true)
  try {
    await deleteKnowledgeDocumentApi(row.id)
    ElMessage.success(copy.value.deletedDone)
    await fetchKnowledge()
  } finally {
    markDocumentBusy(row.id, false)
  }
}

const reindexDocument = async (row) => {
  try {
    await ElMessageBox.confirm(copy.value.reindexConfirm(row.title), copy.value.reindex, { type: 'warning' })
  } catch {
    return
  }
  markDocumentBusy(row.id, true)
  try {
    await reindexKnowledgeDocumentApi(row.id)
    ElMessage.success(copy.value.reindexedDone)
    await fetchKnowledge()
  } finally {
    markDocumentBusy(row.id, false)
  }
}

onMounted(async () => {
  if (!userStore.isAdmin) {
    try { await userStore.fetchUserProfile() } catch { return }
  }
  if (!userStore.isAdmin) {
    ElMessage.error(copy.value.noPermission)
    router.replace('/')
    return
  }
  await Promise.all([fetchUsers(), fetchKnowledge()])
})
</script>

<style scoped>
.admin-page { min-height: 100vh; background: #f7f9f7; color: #1f2937; }
.admin-header {
  display: flex; min-height: 68px; align-items: center; justify-content: space-between;
  padding: 0 36px; border-bottom: 1px solid #e5e9e6; background: #fff;
}
.header-left, .header-right { display: flex; align-items: center; gap: 13px; }
.back-button { display: grid; width: 36px; height: 36px; place-items: center; border: 1px solid #dde4df; border-radius: 10px; color: #374151; text-decoration: none; }
.brand { color: #15803d; font-size: 19px; font-weight: 800; text-decoration: none; }
.divider { width: 1px; height: 22px; background: #dfe5e1; }
.home-link { padding: 8px 12px; border: 1px solid #dde4df; border-radius: 9px; color: #374151; text-decoration: none; }
.admin-container { width: min(1240px, calc(100% - 40px)); margin: 0 auto; padding: 34px 0 60px; }
.page-title h1 { margin: 0 0 5px; font-size: 30px; }
.page-title p, .panel-header p { margin: 0; color: #7b867e; font-size: 13px; }
.tab-bar { display: flex; gap: 5px; margin: 24px 0 14px; padding: 5px; border: 1px solid #e2e8e4; border-radius: 12px; background: #fff; width: fit-content; }
.tab-bar button { padding: 9px 16px; border: 0; border-radius: 8px; background: transparent; color: #657168; cursor: pointer; font-weight: 650; }
.tab-bar button.active { background: #eaf8ee; color: #15803d; }
.tab-bar span { margin-left: 6px; padding: 2px 6px; border-radius: 999px; background: #f59e0b; color: #fff; font-size: 10px; }
.panel { padding: 24px; border: 1px solid #e2e8e4; border-radius: 16px; background: #fff; box-shadow: 0 8px 25px rgba(31,41,55,.04); }
.panel-header { display: flex; align-items: center; justify-content: space-between; gap: 18px; margin-bottom: 20px; }
.panel-header h2 { margin: 0 0 5px; font-size: 20px; }
.panel-actions { display: flex; align-items: center; gap: 9px; }
.table-wrap { overflow-x: auto; }
.primary-button, .secondary-button, .danger-button {
  padding: 9px 14px; border-radius: 9px; cursor: pointer; font-weight: 650;
}
.primary-button { border: 1px solid #15803d; background: #15803d; color: #fff; }
.secondary-button { border: 1px solid #dce3de; background: #fff; color: #374151; }
.danger-button { border: 1px solid #dc2626; background: #dc2626; color: #fff; }
.primary-button:disabled, .secondary-button:disabled, .danger-button:disabled { opacity: .55; cursor: not-allowed; }
.text-button { padding: 4px 7px; border: 0; background: transparent; color: #2563eb; cursor: pointer; font-size: 13px; }
.text-button.success { color: #15803d; }
.text-button.warning { color: #b45309; }
.text-button.danger { color: #dc2626; }
.text-button:disabled { color: #b7bdb9; cursor: not-allowed; }
.role-tag, .knowledge-status, .state-dot { display: inline-flex; align-items: center; padding: 4px 8px; border-radius: 999px; font-size: 11px; font-weight: 700; }
.role-tag { background: #f1f5f3; color: #526058; }
.role-tag.admin { background: #fff7df; color: #a16207; }
.state-dot.active { background: #e9f8ed; color: #15803d; }
.state-dot.disabled { background: #f2f3f2; color: #7b827d; }
.status-pending { background: #fff7df; color: #a16207; }
.status-approved { background: #e8f8ed; color: #15803d; }
.status-rejected, .status-failed { background: #fef0f0; color: #c43131; }
.status-processing { background: #eaf3ff; color: #2563eb; }
.pagination-row { display: flex; justify-content: center; margin-top: 20px; }
.document-preview { min-height: 280px; }
.preview-meta { display: flex; flex-wrap: wrap; align-items: center; gap: 10px 18px; margin-bottom: 14px; color: #68736c; font-size: 12px; }
.document-preview pre {
  box-sizing: border-box;
  max-height: 58vh;
  margin: 0;
  padding: 18px;
  overflow: auto;
  border: 1px solid #e3e9e5;
  border-radius: 12px;
  background: #f8faf8;
  color: #26332a;
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  font-size: 13px;
  line-height: 1.7;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
}
.preview-empty { display: grid; min-height: 250px; place-items: center; color: #89928c; }

@media (max-width: 720px) {
  .admin-header { padding: 0 14px; }
  .header-left .divider, .header-left > strong { display: none; }
  .admin-container { width: min(100% - 20px, 1240px); padding-top: 22px; }
  .panel { padding: 16px; }
  .panel-header { align-items: flex-start; flex-direction: column; }
  .panel-actions { width: 100%; flex-wrap: wrap; }
}
</style>
