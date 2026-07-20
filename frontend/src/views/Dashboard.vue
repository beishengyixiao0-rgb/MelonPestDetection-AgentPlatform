 <template>
   <div class="dashboard-page">
     <el-container>
       <el-header class="header">
         <div class="logo">
           <el-icon :size="28"><Monitor /></el-icon>
           <span class="title">RSOD Agent Platform</span>
         </div>
         <el-menu mode="horizontal" :ellipsis="false" router :default-active="'/dashboard'">
           <el-menu-item index="/">首页</el-menu-item>
           <el-menu-item index="/detect">目标检测</el-menu-item>
           <el-menu-item index="/history">检测历史</el-menu-item>
           <el-menu-item index="/dashboard">数据看板</el-menu-item>
         </el-menu>
       </el-header>
       <el-main>
         <h2>数据看板</h2>
         <el-row :gutter="20">
           <el-col :span="8">
             <el-card>
               <template #header>检测总数</template>
               <div class="stat-value">--</div>
             </el-card>
           </el-col>
           <el-col :span="8">
             <el-card>
               <template #header>病害类型</template>
               <div class="stat-value">--</div>
             </el-card>
           </el-col>
           <el-col :span="8">
             <el-card>
               <template #header>准确率</template>
               <div class="stat-value">--</div>
             </el-card>
           </el-col>
         </el-row>
       </el-main>
     </el-container>
   </div>
 </template>
 
 <script setup>
 import { Monitor } from '@element-plus/icons-vue'
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
 .dashboard-page {
   min-height: 100vh;
   background: #f5f7fa;
 }
 .el-main {
   max-width: 1000px;
   margin: 0 auto;
   padding: 40px;
 }
 .stat-value {
   font-size: 32px;
   font-weight: 700;
   color: #409eff;
   text-align: center;
 }
 </style>
