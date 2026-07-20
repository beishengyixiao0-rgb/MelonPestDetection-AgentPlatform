 <template>
   <div class="history-page">
     <el-container>
       <el-header class="header">
         <div class="logo">
           <el-icon :size="28"><Monitor /></el-icon>
           <span class="title">RSOD Agent Platform</span>
         </div>
         <el-menu mode="horizontal" :ellipsis="false" router :default-active="'/history'">
           <el-menu-item index="/">首页</el-menu-item>
           <el-menu-item index="/detect">目标检测</el-menu-item>
           <el-menu-item index="/history">检测历史</el-menu-item>
           <el-menu-item index="/dashboard">数据看板</el-menu-item>
         </el-menu>
       </el-header>
       <el-main>
         <h2>检测历史</h2>
         <el-table :data="records" style="width: 100%">
           <el-table-column prop="id" label="ID" width="80" />
           <el-table-column prop="image" label="图片" width="120" />
           <el-table-column prop="result" label="检测结果" />
           <el-table-column prop="time" label="检测时间" width="180" />
         </el-table>
       </el-main>
     </el-container>
   </div>
 </template>
 
 <script setup>
 import { ref } from 'vue'
 import { Monitor } from '@element-plus/icons-vue'
 
 const records = ref([])
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
 .history-page {
   min-height: 100vh;
   background: #f5f7fa;
 }
 .el-main {
   max-width: 1000px;
   margin: 0 auto;
   padding: 40px;
 }
 </style>
