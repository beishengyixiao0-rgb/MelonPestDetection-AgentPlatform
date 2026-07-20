 <template>
   <div class="login-page">
     <el-card class="login-card">
       <h2>登录</h2>
       <el-form>
         <el-form-item label="用户名">
           <el-input v-model="username" placeholder="请输入用户名" />
         </el-form-item>
         <el-form-item label="密码">
           <el-input v-model="password" type="password" placeholder="请输入密码" />
         </el-form-item>
         <el-form-item>
           <el-button type="primary" @click="handleLogin">登录</el-button>
         </el-form-item>
       </el-form>
     </el-card>
   </div>
 </template>
 
 <script setup>
 import { ref } from 'vue'
 import { ElMessage } from 'element-plus'
 
 const username = ref('')
 const password = ref('')
 
 function handleLogin() {
   ElMessage.info('登录功能待接入后端')
 }
 </script>
 
 <style scoped>
 .login-page {
   height: 100vh;
   display: flex;
   align-items: center;
   justify-content: center;
   background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
 }
 .login-card {
   width: 400px;
 }
 </style>
