<template>
  <aside class="app-sidebar">
    <el-menu
      :default-active="activeMenu"
      :router="true"
      background-color="#304156"
      text-color="#bfcbd9"
      active-text-color="#409eff"
    >
      <el-menu-item
        v-for="item in menuItems"
        :key="item.path"
        :index="item.path"
      >
        <el-icon>
          <component :is="item.icon" />
        </el-icon>
        <span>{{ item.title }}</span>
      </el-menu-item>
    </el-menu>
  </aside>
</template>

<script setup>
import {
  ChatDotRound,
  Clock,
  Cpu,
  DataAnalysis,
  House,
} from "@element-plus/icons-vue";
import { computed } from "vue";
import { useRoute } from "vue-router";

const route = useRoute();

/** 当前激活的菜单项 */
const activeMenu = computed(() => {
  return "/" + route.path.split("/")[1];
});

/** 侧边栏菜单配置 */
const menuItems = [
  { path: "/", title: "Home", icon: House },
  { path: "/ai-chat", title: "AI Agent", icon: ChatDotRound },
  { path: "/data-analysis", title: "Analytics", icon: DataAnalysis },
  { path: "/history", title: "History", icon: Clock },
  { path: "/training", title: "Training", icon: Cpu },
];
</script>

<style lang="scss" scoped>
.app-sidebar {
  width: $sidebar-width;
  height: 100%;
  background: $sidebar-bg;
  overflow-y: auto;

  .el-menu {
    border-right: none;
    height: 100%;
  }

  .el-menu-item {
    height: 50px;
    line-height: 50px;

    &.is-active {
      background-color: rgba(64, 158, 255, 0.15) !important;
    }

    &:hover {
      background-color: rgba(255, 255, 255, 0.05) !important;
    }
  }
}
</style>
