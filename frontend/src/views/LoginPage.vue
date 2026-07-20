<template>
  <div class="login-page">
    <div class="background-overlay"></div>

    <div class="login-container">
      <div class="logo-section">
        <div class="logo-icon">🌿</div>
        <h1>AgriAgent</h1>
        <p>AI-powered crop health monitoring</p>
      </div>

      <button class="back-btn" @click="goBack">← Back to Home</button>

      <div class="login-card">
        <div v-if="!showForgotPassword && !showResetPassword" class="tabs">
          <button
            class="tab-btn"
            :class="{ active: isLogin }"
            @click="isLogin = true"
          >
            Login
          </button>
          <button
            class="tab-btn"
            :class="{ active: !isLogin }"
            @click="isLogin = false"
          >
            Sign Up
          </button>
        </div>

        <div v-if="showForgotPassword" class="form-header">
          <h3>Forgot Password</h3>
          <button class="close-btn" @click="closeForgotPassword">×</button>
        </div>

        <div v-if="showResetPassword" class="form-header">
          <h3>Reset Password</h3>
          <button class="close-btn" @click="closeResetPassword">×</button>
        </div>

        <form
          v-if="isLogin && !showForgotPassword && !showResetPassword"
          @submit.prevent="handleLogin"
          class="login-form"
        >
          <div class="form-group">
            <label>Username</label>
            <div class="input-wrapper">
              <span class="input-icon">👤</span>
              <input
                v-model="loginForm.username"
                type="text"
                placeholder="Enter your username"
              />
            </div>
          </div>

          <div class="form-group">
            <label>Password</label>
            <div class="input-wrapper">
              <span class="input-icon">🔒</span>
              <input
                v-model="loginForm.password"
                type="password"
                placeholder="Enter your password"
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
              Forgot Password?
            </button>
          </div>

          <button type="submit" class="submit-btn" :disabled="loading">
            {{ loading ? "Signing In..." : "Sign In" }}
          </button>
        </form>

        <form
          v-if="showForgotPassword"
          @submit.prevent="handleForgotPassword"
          class="login-form"
        >
          <div class="form-group">
            <label>Email</label>
            <div class="input-wrapper">
              <span class="input-icon">📧</span>
              <input
                v-model="forgotForm.email"
                type="email"
                placeholder="Enter your registered email"
                @keyup.enter="handleForgotPassword"
              />
            </div>
          </div>

          <div v-if="forgotSuccess" class="success-message">
            ✅ Reset token generated. Please copy the token below and proceed to
            reset your password.
          </div>

          <div v-if="forgotSuccess" class="token-display">
            <label>Reset Token:</label>
            <div class="token-content">
              {{ resetToken }}
              <button class="copy-btn" @click="copyToken">📋 Copy</button>
            </div>
          </div>

          <button
            v-if="forgotSuccess"
            type="button"
            class="submit-btn"
            @click="showResetPassword = true"
          >
            Reset Password
          </button>

          <button v-else type="submit" class="submit-btn" :disabled="loading">
            {{ loading ? "Generating..." : "Get Reset Token" }}
          </button>
        </form>

        <form
          v-if="showResetPassword"
          @submit.prevent="handleResetPassword"
          class="login-form"
        >
          <div class="form-group">
            <label>Reset Token</label>
            <div class="input-wrapper">
              <span class="input-icon">🔑</span>
              <input
                v-model="resetForm.token"
                type="text"
                placeholder="Enter your reset token"
              />
            </div>
          </div>

          <div class="form-group">
            <label>New Password</label>
            <div class="input-wrapper">
              <span class="input-icon">🔒</span>
              <input
                v-model="resetForm.newPassword"
                type="password"
                placeholder="Enter new password"
              />
            </div>
          </div>

          <div class="form-group">
            <label>Confirm New Password</label>
            <div class="input-wrapper">
              <span class="input-icon">🔒</span>
              <input
                v-model="resetForm.confirmPassword"
                type="password"
                placeholder="Confirm new password"
                @keyup.enter="handleResetPassword"
              />
            </div>
          </div>

          <button type="submit" class="submit-btn" :disabled="loading">
            {{ loading ? "Resetting..." : "Reset Password" }}
          </button>
        </form>

        <form
          v-else-if="!isLogin && !showForgotPassword && !showResetPassword"
          @submit.prevent="handleRegister"
          class="login-form"
        >
          <div class="form-group">
            <label>Username</label>
            <div class="input-wrapper">
              <span class="input-icon">👤</span>
              <input
                v-model="registerForm.username"
                type="text"
                placeholder="Enter your username"
              />
            </div>
          </div>

          <div class="form-group">
            <label>Email</label>
            <div class="input-wrapper">
              <span class="input-icon">📧</span>
              <input
                v-model="registerForm.email"
                type="email"
                placeholder="Enter your email"
              />
            </div>
          </div>

          <div class="form-group">
            <label>Password</label>
            <div class="input-wrapper">
              <span class="input-icon">🔒</span>
              <input
                v-model="registerForm.password"
                type="password"
                placeholder="Enter your password"
              />
            </div>
          </div>

          <div class="form-group">
            <label>Confirm Password</label>
            <div class="input-wrapper">
              <span class="input-icon">🔒</span>
              <input
                v-model="registerForm.confirmPassword"
                type="password"
                placeholder="Confirm your password"
                @keyup.enter="handleRegister"
              />
            </div>
          </div>

          <button type="submit" class="submit-btn" :disabled="loading">
            {{ loading ? "Signing Up..." : "Sign Up" }}
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
const resetToken = ref("");

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
  token: "",
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
    ElMessage.error("登录失败，请检查用户名和密码");
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
  resetToken.value = "";
}

function closeResetPassword() {
  showResetPassword.value = false;
  resetForm.token = "";
  resetForm.newPassword = "";
  resetForm.confirmPassword = "";
}

async function handleForgotPassword() {
  if (!forgotForm.email) {
    ElMessage.warning("请输入邮箱");
    return;
  }

  loading.value = true;
  try {
    const response = await forgotPasswordApi({ email: forgotForm.email });
    resetToken.value = response.token;
    forgotSuccess.value = true;
    resetForm.token = response.token;
    ElMessage.success("重置令牌已生成");
  } catch (error) {
    ElMessage.error("邮箱未注册，请检查输入");
  } finally {
    loading.value = false;
  }
}

async function copyToken() {
  try {
    await navigator.clipboard.writeText(resetToken.value);
    ElMessage.success("令牌已复制到剪贴板");
  } catch (error) {
    ElMessage.warning("复制失败，请手动复制");
  }
}

async function handleResetPassword() {
  if (!resetForm.token) {
    ElMessage.warning("请输入重置令牌");
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
      token: resetForm.token,
      new_password: resetForm.newPassword,
    });
    ElMessage.success("密码重置成功，请登录");
    closeResetPassword();
    closeForgotPassword();
    isLogin.value = true;
  } catch (error) {
    ElMessage.error("重置失败，令牌无效或已过期");
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

.token-display {
  margin-top: 12px;

  label {
    display: block;
    font-size: 14px;
    font-weight: 600;
    color: #374151;
    margin-bottom: 8px;
  }

  .token-content {
    display: flex;
    align-items: center;
    gap: 8px;
    background: #f3f4f6;
    border-radius: 8px;
    padding: 12px 16px;
    word-break: break-all;
    font-family: monospace;
    font-size: 13px;
    color: #374151;
  }

  .copy-btn {
    flex-shrink: 0;
    padding: 6px 10px;
    background: #16a34a;
    color: white;
    border: none;
    border-radius: 6px;
    font-size: 12px;
    cursor: pointer;
    transition: background 0.2s ease;

    &:hover {
      background: #15803d;
    }
  }
}
</style>
