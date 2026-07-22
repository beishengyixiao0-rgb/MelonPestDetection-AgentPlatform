<template>
  <div class="login-page">
    <div class="background-overlay"></div>

    <div class="login-container">
      <div class="logo-section">
        <div class="logo-icon">🌿</div>
        <h1>AgriAgent</h1>
        <p>AI作物健康监测</p>
      </div>

      <button class="back-btn" @click="goBack">← 返回首页</button>

      <div class="login-card">
        <div v-if="!showForgotPassword && !showResetPassword" class="tabs">
          <button
            class="tab-btn"
            :class="{ active: isLogin }"
            @click="isLogin = true"
          >
            登录
          </button>
          <button
            class="tab-btn"
            :class="{ active: !isLogin }"
            @click="isLogin = false"
          >
            注册
          </button>
        </div>

        <div v-if="showForgotPassword" class="form-header">
          <h3>忘记密码</h3>
          <button class="close-btn" @click="closeForgotPassword">×</button>
        </div>

        <div v-if="showResetPassword" class="form-header">
          <h3>重置密码</h3>
          <button class="close-btn" @click="closeResetPassword">×</button>
        </div>

        <form
          v-if="isLogin && !showForgotPassword && !showResetPassword"
          @submit.prevent="handleLogin"
          class="login-form"
        >
          <div class="form-group">
            <label>用户名</label>
            <div class="input-wrapper">
              <span class="input-icon">👤</span>
              <input
                v-model="loginForm.username"
                type="text"
                placeholder="请输入用户名"
              />
            </div>
          </div>

          <div class="form-group">
            <label>密码</label>
            <div class="input-wrapper">
              <span class="input-icon">🔒</span>
              <input
                v-model="loginForm.password"
                type="password"
                placeholder="请输入密码"
                @keyup.enter="handleLogin"
              />
            </div>
          </div>

          <div class="form-actions">
            <button
              type="button"
              class="forgot-btn"
              @click="showForgotPassword = true"
            >
              忘记密码？
            </button>
          </div>

          <button type="submit" class="submit-btn" :disabled="loading">
            {{ loading ? "登录中..." : "登录" }}
          </button>
        </form>

        <form
          v-if="showForgotPassword"
          @submit.prevent="handleForgotPassword"
          class="login-form"
        >
          <div class="form-group">
            <label>邮箱</label>
            <div class="input-wrapper">
              <span class="input-icon">📧</span>
              <input
                v-model="forgotForm.email"
                type="email"
                placeholder="请输入注册过的邮箱"
                @keyup.enter="handleForgotPassword"
              />
            </div>
          </div>

          <div v-if="forgotSuccess" class="success-message">
            ✅ 验证码已发送至邮箱，请查收后继续重置密码。
          </div>

          <button
            v-if="forgotSuccess"
            type="button"
            class="submit-btn"
            @click="openResetPassword"
          >
            输入验证码
          </button>

          <button v-else type="submit" class="submit-btn" :disabled="loading">
            {{ loading ? "生成中..." : "获取重置令牌" }}
          </button>
        </form>

        <form
          v-if="showResetPassword"
          @submit.prevent="handleResetPassword"
          class="login-form"
        >
          <div class="form-group">
            <label>邮箱</label>
            <div class="input-wrapper">
              <span class="input-icon">📧</span>
              <input
                v-model="resetForm.email"
                type="email"
                placeholder="请输入注册邮箱"
              />
            </div>
          </div>

          <div class="form-group">
            <label>6 位验证码</label>
            <div class="input-wrapper">
              <span class="input-icon">🔑</span>
              <input
                v-model.trim="resetForm.code"
                type="text"
                inputmode="numeric"
                maxlength="6"
                placeholder="请输入邮箱中的验证码"
              />
            </div>
          </div>

          <div class="form-group">
            <label>新密码</label>
            <div class="input-wrapper">
              <span class="input-icon">🔒</span>
              <input
                v-model="resetForm.newPassword"
                type="password"
                placeholder="请输入新密码"
              />
            </div>
          </div>

          <div class="form-group">
            <label>确认新密码</label>
            <div class="input-wrapper">
              <span class="input-icon">🔒</span>
              <input
                v-model="resetForm.confirmPassword"
                type="password"
                placeholder="请确认新密码"
                @keyup.enter="handleResetPassword"
              />
            </div>
          </div>

          <button type="submit" class="submit-btn" :disabled="loading">
            {{ loading ? "重置中..." : "重置密码" }}
          </button>
        </form>

        <form
          v-else-if="!isLogin && !showForgotPassword && !showResetPassword"
          @submit.prevent="handleRegister"
          class="login-form"
        >
          <div class="form-group">
            <label>用户名</label>
            <div class="input-wrapper">
              <span class="input-icon">👤</span>
              <input
                v-model="registerForm.username"
                type="text"
                placeholder="请输入用户名"
              />
            </div>
          </div>

          <div class="form-group">
            <label>邮箱</label>
            <div class="input-wrapper">
              <span class="input-icon">📧</span>
              <input
                v-model="registerForm.email"
                type="email"
                placeholder="请输入邮箱"
              />
            </div>
          </div>

          <div class="form-group">
            <label>密码</label>
            <div class="input-wrapper">
              <span class="input-icon">🔒</span>
              <input
                v-model="registerForm.password"
                type="password"
                placeholder="请输入密码"
              />
            </div>
          </div>

          <div class="form-group">
            <label>确认密码</label>
            <div class="input-wrapper">
              <span class="input-icon">🔒</span>
              <input
                v-model="registerForm.confirmPassword"
                type="password"
                placeholder="请确认密码"
                @keyup.enter="handleRegister"
              />
            </div>
          </div>

          <button type="submit" class="submit-btn" :disabled="loading">
            {{ loading ? "注册中..." : "注册" }}
          </button>
        </form>
      </div>
    </div>
  </div>
</template>

<script setup>
import { forgotPasswordApi, registerApi, resetPasswordApi } from "@/api/auth";
import { useUserStore } from "@/stores/user";
import { ElMessage } from "element-plus";
import { reactive, ref } from "vue";
import { useRoute, useRouter } from "vue-router";

const router = useRouter();
const route = useRoute();
const userStore = useUserStore();

const isLogin = ref(route.path === "/register" ? false : true);
const loading = ref(false);
const showForgotPassword = ref(false);
const showResetPassword = ref(false);
const forgotSuccess = ref(false);

const loginForm = reactive({
  username: "",
  password: "",
});

const registerForm = reactive({
  username: "",
  email: "",
  password: "",
  confirmPassword: "",
});

const forgotForm = reactive({
  email: "",
});

const resetForm = reactive({
  email: "",
  code: "",
  newPassword: "",
  confirmPassword: "",
});

async function handleLogin() {
  if (!loginForm.username || !loginForm.password) {
    ElMessage.warning("请填写完整信息");
    return;
  }

  loading.value = true;
  try {
    await userStore.login({
      username: loginForm.username,
      password: loginForm.password,
    });
    ElMessage.success("登录成功");
    const redirect = route.query.redirect || "/home";
    router.push(redirect);
  } catch (error) {
    ElMessage.error(
      error?.response?.data?.detail || "登录失败，请检查用户名和密码",
    );
  } finally {
    loading.value = false;
  }
}

function goBack() {
  router.push("/");
}

function closeForgotPassword() {
  showForgotPassword.value = false;
  forgotSuccess.value = false;
  forgotForm.email = "";
}

function closeResetPassword() {
  showResetPassword.value = false;
  resetForm.email = "";
  resetForm.code = "";
  resetForm.newPassword = "";
  resetForm.confirmPassword = "";
}

function openResetPassword() {
  resetForm.email = forgotForm.email;
  resetForm.code = "";
  showForgotPassword.value = false;
  showResetPassword.value = true;
}

async function handleForgotPassword() {
  if (!forgotForm.email) {
    ElMessage.warning("请输入邮箱");
    return;
  }

  loading.value = true;
  try {
    await forgotPasswordApi({ email: forgotForm.email });
    forgotSuccess.value = true;
    ElMessage.success("验证码已发送，请检查邮箱");
  } catch (error) {
    ElMessage.error(
      error?.response?.data?.detail || "验证码发送失败，请检查邮箱",
    );
  } finally {
    loading.value = false;
  }
}

async function handleResetPassword() {
  if (!resetForm.email) {
    ElMessage.warning("请输入注册邮箱");
    return;
  }
  if (!/^\d{6}$/.test(resetForm.code)) {
    ElMessage.warning("请输入 6 位数字验证码");
    return;
  }
  if (!resetForm.newPassword || !resetForm.confirmPassword) {
    ElMessage.warning("请填写完整信息");
    return;
  }
  if (resetForm.newPassword !== resetForm.confirmPassword) {
    ElMessage.warning("两次密码不一致");
    return;
  }

  loading.value = true;
  try {
    await resetPasswordApi({
      email: resetForm.email,
      code: resetForm.code,
      new_password: resetForm.newPassword,
    });
    ElMessage.success("密码重置成功，请登录");
    closeResetPassword();
    forgotSuccess.value = false;
    forgotForm.email = "";
    isLogin.value = true;
  } catch (error) {
    ElMessage.error(
      error?.response?.data?.detail || "重置失败，验证码无效或已过期",
    );
  } finally {
    loading.value = false;
  }
}

async function handleRegister() {
  if (!registerForm.username || !registerForm.email || !registerForm.password) {
    ElMessage.warning("请填写完整信息");
    return;
  }
  if (registerForm.password !== registerForm.confirmPassword) {
    ElMessage.warning("两次密码不一致");
    return;
  }

  loading.value = true;
  try {
    await registerApi({
      username: registerForm.username,
      email: registerForm.email,
      password: registerForm.password,
    });
    ElMessage.success("注册成功，请登录");
    isLogin.value = true;
    registerForm.username = "";
    registerForm.email = "";
    registerForm.password = "";
    registerForm.confirmPassword = "";
  } catch (error) {
    ElMessage.error("注册失败");
  } finally {
    loading.value = false;
  }
}
</script>

<style lang="scss" scoped>
.login-page {
  min-height: 100vh;
  background: url("https://trae-api-cn.mchost.guru/api/ide/v1/text_to_image?prompt=fresh%20green%20corn%20leaves%2C%20agricultural%20field%2C%20natural%20light%2C%20soft%20focus%2C%20green%20background&image_size=landscape_16_9")
    no-repeat center center;
  background-size: cover;
  position: relative;
  display: flex;
  align-items: center;
  justify-content: center;
}

.background-overlay {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(255, 255, 255, 0.7);
}

.login-container {
  position: relative;
  z-index: 1;
  text-align: center;
}

.logo-section {
  margin-bottom: 40px;
}

.logo-icon {
  font-size: 64px;
  margin-bottom: 16px;
}

.logo-section h1 {
  font-size: 36px;
  font-weight: 700;
  color: #166534;
  margin-bottom: 8px;
}

.logo-section p {
  font-size: 16px;
  color: #6b7280;
}

.login-card {
  background: white;
  border-radius: 16px;
  padding: 40px;
  width: 400px;
  box-shadow: 0 20px 60px rgba(22, 163, 74, 0.15);
}

.tabs {
  display: flex;
  margin-bottom: 32px;
  background: #f3f4f6;
  border-radius: 10px;
  padding: 4px;
}

.tab-btn {
  flex: 1;
  padding: 12px;
  border: none;
  background: transparent;
  border-radius: 8px;
  font-size: 16px;
  font-weight: 600;
  color: #6b7280;
  cursor: pointer;
  transition: all 0.2s ease;

  &.active {
    background: white;
    color: #16a34a;
    box-shadow: 0 2px 8px rgba(22, 163, 74, 0.1);
  }

  &:hover:not(.active) {
    color: #16a34a;
  }
}

.login-form {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.form-group {
  text-align: left;
}

.form-group label {
  display: block;
  font-size: 14px;
  font-weight: 600;
  color: #374151;
  margin-bottom: 8px;
}

.input-wrapper {
  display: flex;
  align-items: center;
  background: #f9fafb;
  border-radius: 10px;
  padding: 0 16px;
  border: 1px solid #e5e7eb;
  transition: all 0.2s ease;

  &:focus-within {
    border-color: #16a34a;
    box-shadow: 0 0 0 3px rgba(22, 163, 74, 0.1);
  }
}

.input-icon {
  font-size: 18px;
  margin-right: 12px;
}

.input-wrapper input {
  flex: 1;
  padding: 14px 0;
  border: none;
  background: transparent;
  font-size: 14px;
  color: #374151;
  outline: none;

  &::placeholder {
    color: #9ca3af;
  }
}

.form-actions {
  display: flex;
  justify-content: flex-end;
}

.forgot-btn {
  padding: 8px 0;
  border: none;
  background: transparent;
  color: #16a34a;
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s ease;

  &:hover {
    text-decoration: underline;
  }
}

.back-btn {
  margin-bottom: 20px;
  padding: 10px 24px;
  border: 1px solid #16a34a;
  background: transparent;
  color: #16a34a;
  font-size: 14px;
  font-weight: 500;
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.2s ease;

  &:hover {
    background: rgba(22, 163, 74, 0.1);
  }
}

.submit-btn {
  width: 100%;
  padding: 14px;
  background: linear-gradient(135deg, #16a34a 0%, #15803d 100%);
  border: none;
  border-radius: 10px;
  color: white;
  font-size: 16px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s ease;

  &:hover:not(:disabled) {
    transform: translateY(-1px);
    box-shadow: 0 6px 16px rgba(22, 163, 74, 0.3);
  }

  &:disabled {
    opacity: 0.7;
    cursor: not-allowed;
  }
}

.form-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 24px;

  h3 {
    font-size: 20px;
    font-weight: 600;
    color: #166534;
    margin: 0;
  }
}

.close-btn {
  background: transparent;
  border: none;
  font-size: 24px;
  color: #9ca3af;
  cursor: pointer;
  transition: color 0.2s ease;

  &:hover {
    color: #374151;
  }
}

.success-message {
  background: #dcfce7;
  border: 1px solid #bbf7d0;
  border-radius: 10px;
  padding: 12px 16px;
  color: #166534;
  font-size: 14px;
  text-align: center;
}

</style>
