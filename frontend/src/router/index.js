/**
 * Vue Router 路由配置
 * - 登录/注册页面无需认证
 * - 其他页面需要登录后才能访问
 * - 路由守卫自动检查登录状态
 */
import { useUserStore } from "@/stores/user";
import { createRouter, createWebHistory } from "vue-router";

// ── 路由定义 ────────────────────────────────────────
const routes = [
  {
    path: "/",
    name: "Web",
    component: () => import("@/views/WebPage.vue"),
    meta: { title: "AgriAgent", requiresAuth: false },
  },
  {
    path: "/login",
    name: "Login",
    component: () => import("@/views/LoginPage.vue"),
    meta: { title: "登录", requiresAuth: false },
  },
  {
    path: "/register",
    name: "Register",
    component: () => import("@/views/LoginPage.vue"),
    meta: { title: "注册", requiresAuth: false },
  },
  {
    path: "/home",
    name: "Home",
    component: () => import("@/views/HomePage.vue"),
    meta: {
      title: "Home",
      requiresAuth: true,
    },
  },

  // ── AgriAgent 页面 ───────────────────────
  {
    path: "/ai-chat",
    name: "AIChat",
    component: () => import("@/views/ChatPage.vue"),
    meta: {
      title: "AI Agent",
      requiresAuth: true,
    },
  },

  {
    path: "/data-analysis",
    name: "DataAnalysis",
    component: () => import("@/views/AnalyticsPage.vue"),
    meta: {
      title: "Analytics",
      requiresAuth: true,
    },
  },

  {
    path: "/history",
    name: "History",
    component: () => import("@/views/HistoryPage.vue"),
    meta: {
      title: "History",
      requiresAuth: true,
    },
  },

  {
    path: "/training",
    name: "Training",
    component: () => import("@/views/TrainingPage.vue"),
    meta: {
      title: "Training",
      requiresAuth: true,
    },
  },

  // ── 404 页面 ─────────────────────────────────────
  {
    path: "/:pathMatch(.*)*",
    redirect: "/login",
  },
];

// ── 创建路由实例 ──────────────────────────────────────
const router = createRouter({
  history: createWebHistory(),
  routes,
});

// ── 路由守卫 ────────────────────────────────────────
router.beforeEach((to, from, next) => {
  // 设置页面标题
  document.title = to.meta.title ? `${to.meta.title} - AgriAgent` : "AgriAgent";

  const token = localStorage.getItem("rsod_token");
  const requiresAuth = to.matched.some(
    (record) => record.meta.requiresAuth !== false,
  );
  const userStore = useUserStore();

  if (requiresAuth && !token) {
    next({ path: "/login", query: { redirect: to.fullPath } });
  } else {
    next();
  }
});

export default router;
