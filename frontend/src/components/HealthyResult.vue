<template>
  <article class="healthy-result-card">
    <div class="healthy-icon">✓</div>

    <div class="healthy-content">
      <span class="healthy-label">检测提示</span>

      <h3>未检测到明显病害</h3>

      <p>
        当前图像中未识别到病害目标。如果叶片存在遮挡、模糊或光照不足，
        可重新拍摄进行检测。
      </p>

      <div class="healthy-notice">
        检测结果仅针对当前图像，不代表植株一定完全健康。
      </div>

      <button type="button" class="redetect-button" @click="$emit('redetect')">
        <span>↻</span>
        重新检测
      </button>
    </div>
  </article>
</template>

<script setup>
defineEmits(['redetect'])
</script>

<style scoped>
.healthy-result-card {
  width: 100%;
  max-width: 620px;
  box-sizing: border-box;
  display: flex;
  align-items: flex-start;
  gap: 16px;
  padding: 22px;
  border: 1px solid #bbf7d0;
  border-radius: 20px;
  background: linear-gradient(145deg, #ffffff 0%, #f0fdf4 100%);
  box-shadow: 0 8px 24px rgba(22, 163, 74, 0.08);
}

.healthy-icon {
  width: 44px;
  height: 44px;
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 14px;
  background: #dcfce7;
  color: #15803d;
  font-size: 24px;
  font-weight: 700;
}

.healthy-content {
  min-width: 0;
  flex: 1;
}

.healthy-label {
  color: #15803d;
  font-size: 12px;
  font-weight: 700;
}

.healthy-content h3 {
  margin: 5px 0 8px;
  color: #17201b;
  font-size: 18px;
}

.healthy-content p {
  margin: 0;
  color: #4b5563;
  font-size: 14px;
  line-height: 1.75;
}

.healthy-notice {
  margin-top: 13px;
  padding: 10px 12px;
  border-radius: 10px;
  background: rgba(255, 255, 255, 0.75);
  color: #6b7280;
  font-size: 12px;
  line-height: 1.6;
}

.redetect-button {
  margin-top: 16px;
  padding: 9px 15px;
  display: inline-flex;
  align-items: center;
  gap: 7px;
  border: 0;
  border-radius: 10px;
  background: #16803f;
  color: #ffffff;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
}

.redetect-button:hover {
  background: #116b34;
}

@media (max-width: 520px) {
  .healthy-result-card {
    gap: 12px;
    padding: 18px;
  }

  .healthy-icon {
    width: 38px;
    height: 38px;
  }
}
</style>