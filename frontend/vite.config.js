import vue from "@vitejs/plugin-vue";
import path from "path";
import { fileURLToPath } from "url";
import { defineConfig } from "vite";

const __dirname = path.dirname(fileURLToPath(import.meta.url));

export default defineConfig({
  plugins: [vue()],

  resolve: {
    alias: {
      "@": fileURLToPath(
        new URL("./src", import.meta.url)
      ),
    },
  },

  // 为所有 SCSS 文件注入主题变量，组件中可直接使用 $spacing-lg 等变量。
  css: {
    preprocessorOptions: {
      scss: {
        additionalData: `@use "@/assets/styles/variables.scss" as *;`,
      },
    },
  },

  server: {
    port: 5173,

    proxy: {
      /**
       * REST API 代理
       * 前端请求:
       *   /api/**
       *
       * 实际转发:
       *   http://localhost:8000/api/**
       */
      "/api": {
        target: "http://localhost:8000",
        changeOrigin: true,
        ws: true,
      },

      /**
       * WebSocket 代理
       * 摄像头实时检测
       */
      "/api/detection/camera": {
        target: "ws://localhost:8000",
        ws: true,
        changeOrigin: true,
      },
    },
  },

  test: {
    environment: "happy-dom",
    setupFiles: ["./tests/setup.js"],
    include: ["tests/**/*.{test,spec}.{js,ts}"],
    coverage: {
      provider: "v8",
      reporter: ["text", "html"],
    },
  },
});
