 <template>
   <div class="detect-page">
     <el-container>
       <el-header class="header">
         <div class="logo">
           <el-icon :size="28"><Monitor /></el-icon>
           <span class="title">RSOD Agent Platform</span>
         </div>
         <el-menu mode="horizontal" :ellipsis="false" router :default-active="'/detect'">
           <el-menu-item index="/">首页</el-menu-item>
           <el-menu-item index="/detect">目标检测</el-menu-item>
           <el-menu-item index="/history">检测历史</el-menu-item>
           <el-menu-item index="/dashboard">数据看板</el-menu-item>
         </el-menu>
       </el-header>
       <el-main>
         <h2>目标检测</h2>
         <p>上传图片进行 YOLO11n 目标检测</p>
         <el-upload
           drag
           action="/api/detect"
           multiple
           :show-file-list="true">
           <el-icon class="el-icon--upload"><upload-filled /></el-icon>
           <div class="el-upload__text">
             拖拽文件到此处或 <em>点击上传</em>
           </div>
         </el-upload>
       </el-main>
     </el-container>
   </div>
 </template>
 
 <script setup>
 import { Monitor, UploadFilled } from '@element-plus/icons-vue'
 </script>
 
 <style scoped>
 .header {
   display: flex;
   align-items: center;
   gap: 40px;
   background: #fff;
   border-bottom: 1px solid #e4e7ed;
 }
 .logo {
   display: flex;
   align-items: center;
   gap: 10px;
 }
 .logo .title {
   font-size: 18px;
   font-weight: 600;
 }
 .detect-page {
   min-height: 100vh;
   background: #f5f7fa;
 }
 .el-main {
   max-width: 800px;
   margin: 0 auto;
   padding: 40px;
 }
 </style>
