<template>
  <el-dialog
    :model-value="modelValue"
    :title="tr('profile.editTitle')"
    width="420px"
    class="profile-edit-dialog"
    @update:model-value="$emit('update:modelValue', $event)"
    @open="resetForm"
  >
    <el-form
      ref="formRef"
      :model="form"
      :rules="rules"
      label-position="top"
      @submit.prevent
    >
      <el-form-item :label="tr('profile.username')">
        <el-input :model-value="userStore.username || '-'" disabled />
      </el-form-item>

      <el-form-item :label="tr('profile.email')" prop="email">
        <el-input
          v-model.trim="form.email"
          autocomplete="email"
          :placeholder="tr('profile.emailPlaceholder')"
        />
      </el-form-item>

      <el-form-item :label="tr('profile.phone')" prop="phone">
        <el-input
          v-model.trim="form.phone"
          autocomplete="tel"
          :placeholder="tr('profile.phonePlaceholder')"
        />
      </el-form-item>
    </el-form>

    <template #footer>
      <button class="dialog-button secondary" type="button" @click="close">
        {{ tr('common.cancel') }}
      </button>
      <button
        class="dialog-button primary"
        type="button"
        :disabled="saving"
        @click="submit"
      >
        {{ saving ? tr('profile.saving') : tr('profile.save') }}
      </button>
    </template>
  </el-dialog>
</template>

<script setup>
import { reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { useLocaleStore } from '@/stores/locale'
import { useUserStore } from '@/stores/user'
import { t } from '@/utils/i18n'

defineProps({
  modelValue: {
    type: Boolean,
    default: false,
  },
})

const emit = defineEmits(['update:modelValue', 'saved'])

const userStore = useUserStore()
const localeStore = useLocaleStore()
const tr = (key, params) => t(key, localeStore.locale, params)

const formRef = ref(null)
const saving = ref(false)
const form = reactive({
  email: '',
  phone: '',
})

const rules = {
  email: [
    { required: true, message: tr('profile.emailRequired'), trigger: 'blur' },
    {
      pattern: /^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$/,
      message: tr('profile.emailInvalid'),
      trigger: 'blur',
    },
  ],
  phone: [
    {
      max: 20,
      message: tr('profile.phoneInvalid'),
      trigger: 'blur',
    },
  ],
}

const resetForm = () => {
  form.email = userStore.user?.email || ''
  form.phone = userStore.user?.phone || ''
  formRef.value?.clearValidate()
}

const close = () => {
  emit('update:modelValue', false)
}

const submit = async () => {
  const valid = await formRef.value?.validate().catch(() => false)
  if (!valid) return

  saving.value = true
  try {
    await userStore.updateProfile({
      email: form.email,
      phone: form.phone,
    })
    ElMessage.success(tr('profile.saveSuccess'))
    emit('saved')
    close()
  } finally {
    saving.value = false
  }
}
</script>

<style scoped>
:deep(.profile-edit-dialog .el-dialog__body) {
  padding-top: 8px;
}

.dialog-button {
  min-width: 84px;
  padding: 10px 14px;
  border: 0;
  border-radius: 10px;
  cursor: pointer;
  font-size: 13px;
  font-weight: 700;
}

.dialog-button.secondary {
  background: #f3f4f6;
  color: #374151;
}

.dialog-button.primary {
  margin-left: 8px;
  background: #15803d;
  color: #fff;
}

.dialog-button.primary:disabled {
  background: #9ca3af;
  cursor: not-allowed;
}
</style>
