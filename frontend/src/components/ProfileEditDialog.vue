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

      <section class="password-reset-section">
        <div class="section-heading">
          <strong>{{ tr('profile.resetPassword') }}</strong>
          <span>{{ tr('profile.resetPasswordDesc') }}</span>
        </div>

        <button
          class="dialog-button secondary reset-code-button"
          type="button"
          :disabled="sendingCode"
          @click="sendResetCode"
        >
          {{ sendingCode ? tr('profile.sendingCode') : tr('profile.sendCode') }}
        </button>

        <el-form-item :label="tr('profile.code')" prop="code">
          <el-input
            v-model.trim="form.code"
            maxlength="6"
            autocomplete="one-time-code"
            :placeholder="tr('profile.codePlaceholder')"
          />
        </el-form-item>

        <el-form-item :label="tr('profile.newPassword')" prop="newPassword">
          <el-input
            v-model="form.newPassword"
            type="password"
            show-password
            autocomplete="new-password"
            :placeholder="tr('profile.newPasswordPlaceholder')"
          />
        </el-form-item>

        <el-form-item :label="tr('profile.confirmPassword')" prop="confirmPassword">
          <el-input
            v-model="form.confirmPassword"
            type="password"
            show-password
            autocomplete="new-password"
            :placeholder="tr('profile.confirmPasswordPlaceholder')"
          />
        </el-form-item>

        <button
          class="dialog-button primary reset-password-button"
          type="button"
          :disabled="resettingPassword"
          @click="resetPassword"
        >
          {{ resettingPassword ? tr('profile.resettingPassword') : tr('profile.confirmResetPassword') }}
        </button>
      </section>
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
import { forgotPasswordApi, resetPasswordApi } from '@/api/auth'
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
const sendingCode = ref(false)
const resettingPassword = ref(false)
const form = reactive({
  email: '',
  phone: '',
  code: '',
  newPassword: '',
  confirmPassword: '',
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
  code: [
    {
      pattern: /^$|^\d{6}$/,
      message: tr('profile.codeInvalid'),
      trigger: 'blur',
    },
  ],
  newPassword: [
    {
      min: 6,
      max: 100,
      message: tr('profile.passwordInvalid'),
      trigger: 'blur',
    },
  ],
  confirmPassword: [
    {
      validator: (_rule, value, callback) => {
        if (!value && !form.newPassword) return callback()
        if (value !== form.newPassword) return callback(new Error(tr('profile.passwordMismatch')))
        callback()
      },
      trigger: 'blur',
    },
  ],
}

const resetForm = () => {
  form.email = userStore.user?.email || ''
  form.phone = userStore.user?.phone || ''
  form.code = ''
  form.newPassword = ''
  form.confirmPassword = ''
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

const syncProfileBeforePasswordReset = async () => {
  await formRef.value?.validateField(['email', 'phone'])
  if (form.email === userStore.user?.email && form.phone === (userStore.user?.phone || '')) {
    return
  }
  await userStore.updateProfile({
    email: form.email,
    phone: form.phone,
  })
  emit('saved')
}

const sendResetCode = async () => {
  sendingCode.value = true
  try {
    await syncProfileBeforePasswordReset()
    await forgotPasswordApi({ email: form.email })
    ElMessage.success(tr('profile.codeSent'))
  } finally {
    sendingCode.value = false
  }
}

const resetPassword = async () => {
  const valid = await formRef.value?.validateField(['email', 'code', 'newPassword', 'confirmPassword']).catch(() => false)
  if (valid === false) return
  if (!form.code || !form.newPassword || !form.confirmPassword) {
    ElMessage.warning(tr('profile.resetFieldsRequired'))
    return
  }

  resettingPassword.value = true
  try {
    await resetPasswordApi({
      email: form.email,
      code: form.code,
      new_password: form.newPassword,
    })
    form.code = ''
    form.newPassword = ''
    form.confirmPassword = ''
    ElMessage.success(tr('profile.passwordResetSuccess'))
  } finally {
    resettingPassword.value = false
  }
}
</script>

<style scoped>
:deep(.profile-edit-dialog .el-dialog__body) {
  padding-top: 8px;
}

.password-reset-section {
  margin-top: 18px;
  padding-top: 16px;
  border-top: 1px solid #e5e7eb;
}

.section-heading {
  display: flex;
  flex-direction: column;
  gap: 4px;
  margin-bottom: 10px;
}

.section-heading strong {
  color: #111827;
  font-size: 14px;
}

.section-heading span {
  color: #6b7280;
  font-size: 12px;
  line-height: 1.5;
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

.reset-code-button,
.reset-password-button {
  width: 100%;
  margin: 0 0 12px;
}

.reset-password-button {
  margin-bottom: 0;
}
</style>
