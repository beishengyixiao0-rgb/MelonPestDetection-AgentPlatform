<template>
  <aside class="sidebar">
    <router-link to="/" class="brand">
      🌿 AgriAgent
    </router-link>

    <button
      class="new-chat"
      @click="$emit('new-diagnosis')"
    >
      + New Diagnosis
    </button>

    <div class="sidebar-section-title">Recent Diagnoses</div>

    <div class="session-list">
      <div
        v-for="(session, index) in sessions"
        :key="index"
        class="session-item"
      >
        {{ session }}
      </div>
    </div>

    <div class="sidebar-bottom">
      <div class="sidebar-section-title">Navigation</div>

      <router-link to="/ai-chat" class="nav-item" active-class="nav-item-active">
        🤖 AI Diagnosis
      </router-link>

      <router-link to="/data-analysis" class="nav-item" active-class="nav-item-active">
        📊 Data Analysis
      </router-link>

      <router-link to="/history" class="nav-item" active-class="nav-item-active">
        🕒 History Analysis
      </router-link>
    </div>
  </aside>
</template>

<script setup>
defineProps({
  sessions: {
    type: Array,
    default: () => [],
  },
})

defineEmits(['new-diagnosis'])
</script>

<style scoped>
.sidebar {
  width: 260px;
  background: white;
  border-right: 1px solid #e5e7eb;
  padding: 20px;
  display: flex;
  flex-direction: column;
  height: 100vh;
  box-shadow: 2px 0 12px rgba(0, 0, 0, 0.04);
}

.brand {
  font-size: 20px;
  font-weight: 700;
  color: #16a34a;
  margin-bottom: 24px;
  text-decoration: none;
  display: block;
}

.new-chat {
  background: #16a34a;
  color: white;
  border: none;
  border-radius: 10px;
  padding: 12px;
  cursor: pointer;
  margin-bottom: 24px;
  font-weight: 600;
  transition: all 0.2s ease;
}

.new-chat:hover {
  transform: translateY(-1px);
  box-shadow: 0 6px 18px rgba(22, 163, 74, 0.25);
}

.session-list {
  margin-top: 8px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.session-item {
  border: 1px solid #e5e7eb;
  border-radius: 12px;
  padding: 14px;
  margin-bottom: 12px;
  cursor: pointer;
  transition: all 0.2s ease;
  background: #ffffff;
}

.session-item:hover {
  background: #f9fafb;
  border-color: #16a34a;
}

.sidebar-bottom {
  margin-top: auto;
  padding-top: 24px;
  border-top: 1px solid #e5e7eb;
}

.sidebar-section-title {
  font-size: 12px;
  font-weight: 700;
  color: #9ca3af;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  margin-bottom: 12px;
}

.nav-item {
  display: block;
  text-decoration: none;
  padding: 12px 14px;
  border-radius: 10px;
  color: #374151;
  margin-bottom: 8px;
  transition: all 0.2s ease;
  font-weight: 500;
}

.nav-item:hover {
  background: #f3f4f6;
}

.nav-item-active {
  background: #ecfdf5;
  color: #16a34a;
  font-weight: 600;
  border: 1px solid #bbf7d0;
}
</style>
