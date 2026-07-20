 <template>
   <div class="home">
     <el-container>
       <el-header class="header">
         <div class="logo">
           <el-icon :size="28"><Monitor /></el-icon>
           <span class="title">RSOD Agent Platform</span>
         </div>
         <el-menu mode="horizontal" :ellipsis="false" router>
           <el-menu-item index="/">首页</el-menu-item>
           <el-menu-item index="/detect">目标检测</el-menu-item>
           <el-menu-item index="/history">检测历史</el-menu-item>
           <el-menu-item index="/dashboard">数据看板</el-menu-item>
         </el-menu>
         <div class="user-area">
           <el-button type="primary" @click="$router.push('/login')">登录</el-button>
         </div>
       </el-header>
 
       <el-main class="main">
         <div class="hero">
           <h1>基于 YOLO11n 的目标检测智能体平台</h1>
           <p class="subtitle">RSOD Agent Platform — 智能化作物病虫害检测与管理</p>
           <div class="actions">
             <el-button type="primary" size="large" @click="$router.push('/detect')">
               开始检测
             </el-button>
             <el-button size="large" @click="$router.push('/dashboard')">
               查看数据
             </el-button>
           </div>
         </div>
       </el-main>
     </el-container>
   </div>
 </template>
 
 <script setup>
 import { Monitor } from '@element-plus/icons-vue'
 </script>
 
 <style scoped>
 .home {
   height: 100vh;
   display: flex;
   flex-direction: column;
 }
 .header {
   display: flex;
   align-items: center;
   justify-content: space-between;
   background: #fff;
   border-bottom: 1px solid #e4e7ed;
   padding: 0 20px;
 }
 .logo {
   display: flex;
   align-items: center;
   gap: 10px;
 }
 .logo .title {
   font-size: 18px;
   font-weight: 600;
   color: #303133;
 }
 .main {
   flex: 1;
   display: flex;
   align-items: center;
   justify-content: center;
   background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
 }
 .hero {
   text-align: center;
   color: #fff;
 }
 .hero h1 {
   font-size: 36px;
   margin-bottom: 16px;
 }
 .hero .subtitle {
   font-size: 18px;
   opacity: 0.9;
   margin-bottom: 32px;
 }
 .actions {
   display: flex;
   gap: 16px;
   justify-content: center;
 }
 </style>
