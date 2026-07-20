 import { createRouter, createWebHistory } from 'vue-router'
 
 const routes = [
   {
     path: '/',
     name: 'home',
     component: () => import('@/views/Home.vue'),
     meta: { title: '首页' },
   },
   {
     path: '/login',
     name: 'login',
     component: () => import('@/views/Login.vue'),
     meta: { title: '登录' },
   },
   {
     path: '/detect',
     name: 'detect',
     component: () => import('@/views/Detect.vue'),
     meta: { title: '目标检测' },
   },
   {
     path: '/history',
     name: 'history',
     component: () => import('@/views/History.vue'),
     meta: { title: '检测历史' },
   },
   {
     path: '/dashboard',
     name: 'dashboard',
     component: () => import('@/views/Dashboard.vue'),
     meta: { title: '数据看板' },
   },
 ]
 
 const router = createRouter({
   history: createWebHistory(),
   routes,
 })
 
 export default router
