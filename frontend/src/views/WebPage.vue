<template>
  <div class="web-page">
    <nav class="navbar">
      <div class="nav-container">
        <div class="nav-logo">
          <span class="logo-icon">🌿</span>
          <span class="logo-text">AgriAgent</span>
        </div>
        <div class="nav-links">
          <a href="#features" class="nav-link">功能特性</a>
          <a href="#diseases" class="nav-link">病害识别</a>
          <a href="#about" class="nav-link">关于我们</a>
        </div>
      </div>
    </nav>

    <section class="hero-section">
      <div class="hero-content">
        <div class="hero-text">
          <h1>用 AI 赋能农业，</h1>
          <h1>守护每一寸农田</h1>
          <p>
            集作物病虫害检测、土壤分析、天气预测与产量优化于一体的
            智能化农业综合服务平台，让种植更科学、管理更高效。
          </p>
          <div class="hero-buttons">
            <router-link to="/login" class="primary-btn">开始使用</router-link>
          </div>
        </div>
        <div class="hero-carousel">
          <el-carousel :interval="4000" type="card" height="500px">
            <el-carousel-item
              v-for="(item, index) in carouselImages"
              :key="index"
            >
              <div class="carousel-item">
                <img :src="item.url" :alt="item.title" class="carousel-image" />
                <div class="carousel-overlay">
                  <h3>{{ item.title }}</h3>
                  <p>{{ item.description }}</p>
                </div>
              </div>
            </el-carousel-item>
          </el-carousel>
        </div>
      </div>
    </section>

    <section id="features" class="features-section">
      <div class="section-header">
        <h2>智能农业核心功能</h2>
        <p>基于 AI 技术的现代农业综合解决方案</p>
      </div>
      <div class="features-grid">
        <div
          v-for="feature in features"
          :key="feature.title"
          class="feature-card"
        >
          <span class="feature-icon">{{ feature.icon }}</span>
          <h3>{{ feature.title }}</h3>
          <p>{{ feature.description }}</p>
        </div>
      </div>
    </section>

    <section id="diseases" class="diseases-section">
      <div class="section-header">
        <h2>常见农业病害</h2>
        <p>AI精准识别各类农作物病害，提供专业防治建议</p>
      </div>
      <div class="disease-cards">
        <div
          v-for="disease in diseaseInfo"
          :key="disease.name"
          class="disease-card"
        >
          <img :src="disease.image" :alt="disease.name" class="disease-image" />
          <div class="disease-content">
            <h4>{{ disease.name }}</h4>
            <p>{{ disease.description }}</p>
          </div>
        </div>
      </div>
    </section>

    <footer class="footer">
      <div class="footer-content">
        <div class="footer-logo">
          <span class="logo-icon">🌿</span>
          <span class="logo-text">AgriAgent</span>
        </div>
        <div class="footer-links">
          <div class="footer-link-group">
            <h4>产品</h4>
            <a href="#features">功能特性</a>
            <a href="#diseases">病害识别</a>
          </div>
          <div class="footer-link-group">
            <h4>资源</h4>
            <a href="#">帮助中心</a>
            <a href="#">文档</a>
            <a href="#">API</a>
          </div>
          <div class="footer-link-group">
            <h4>公司</h4>
            <a href="#about">关于我们</a>
            <a href="#">联系我们</a>
            <a href="#">加入我们</a>
          </div>
        </div>
        <div class="footer-copyright">
          <p>© 2026 AgriAgent. All rights reserved.</p>
        </div>
      </div>
    </footer>
  </div>
</template>

<script setup>
const features = [
  {
    icon: "🔍",
    title: "AI病害检测",
    description:
      "基于深度学习的计算机视觉技术，快速准确识别200+种农作物病虫害，准确率高达98%。",
  },
  {
    icon: "💬",
    title: "智能对话助手",
    description:
      "与AI助手实时对话，获取专业的病害防治建议、种植技术指导和农业知识问答。",
  },
  {
    icon: "📊",
    title: "数据分析",
    description:
      "可视化展示检测数据和统计分析，帮助您了解作物健康趋势，做出科学决策。",
  },
  {
    icon: "📜",
    title: "历史记录",
    description:
      "完整保存所有检测记录和对话历史，支持随时查看、搜索和导出数据。",
  },
  {
    icon: "🧠",
    title: "模型训练",
    description:
      "支持自定义数据集训练模型，不断优化检测准确度，适应不同地区和作物需求。",
  },
  {
    icon: "🏠",
    title: "数据仪表盘",
    description:
      "直观展示农场整体健康状况、检测统计和关键指标，一目了然掌控全局。",
  },
];

const carouselImages = [
  {
    url: "https://trae-api-cn.mchost.guru/api/ide/v1/text_to_image?prompt=healthy%20green%20crops%20in%20agricultural%20field%20with%20sunlight%2C%20modern%20farming%2C%20natural%20environment&image_size=landscape_16_9",
    title: "健康作物",
    description: "实时监测作物健康状况，AI智能预警病虫害风险",
  },
  {
    url: "https://trae-api-cn.mchost.guru/api/ide/v1/text_to_image?prompt=AI%20plant%20disease%20diagnosis%20with%20green%20leaves%2C%20technology%20interface%2C%20smart%20agriculture&image_size=landscape_16_9",
    title: "智能诊断",
    description: "AI精准识别植物病害，提供专业防治方案",
  },
  {
    url: "https://trae-api-cn.mchost.guru/api/ide/v1/text_to_image?prompt=aerial%20view%20of%20agricultural%20farmland%2C%20modern%20agriculture%2C%20green%20vegetables%2C%20smart%20farming&image_size=landscape_16_9",
    title: "现代农业",
    description: "科技赋能智慧农业，助力乡村振兴发展",
  },
];

const diseaseInfo = [
  {
    image:
      "https://trae-api-cn.mchost.guru/api/ide/v1/text_to_image?prompt=tomato%20late%20blight%20disease%20on%20green%20leaves%2C%20dark%20green%20water-soaked%20spots%2C%20plant%20disease%20symptoms&image_size=square",
    name: "番茄晚疫病",
    description:
      "由疫霉菌引起的毁灭性病害。叶片出现暗绿色水渍状斑点，逐渐变为褐色坏死斑，边缘有白色霉层。",
  },
  {
    image:
      "https://trae-api-cn.mchost.guru/api/ide/v1/text_to_image?prompt=apple%20tree%20canker%20disease%2C%20rotten%20bark%20on%20tree%20trunk%2C%20brown%20decayed%20wood%2C%20plant%20disease&image_size=square",
    name: "苹果腐烂病",
    description:
      "俗称烂皮病，是苹果树枝干的重要病害。病菌侵染枝干皮层，导致皮层腐烂坏死。",
  },
  {
    image:
      "https://trae-api-cn.mchost.guru/api/ide/v1/text_to_image?prompt=wheat%20rust%20disease%2C%20orange%20rust%20spores%20on%20wheat%20leaves%2C%20cereal%20crop%20disease&image_size=square",
    name: "小麦锈病",
    description:
      "包括条锈病、叶锈病和秆锈病三种。叶片和茎秆上出现铁锈色孢子堆，严重影响光合作用。",
  },
  {
    image:
      "https://trae-api-cn.mchost.guru/api/ide/v1/text_to_image?prompt=cucumber%20downy%20mildew%20disease%2C%20yellow%20angular%20spots%20on%20leaves%2C%20purple%20gray%20mold%2C%20vegetable%20disease&image_size=square",
    name: "黄瓜霜霉病",
    description:
      "黄瓜最常见的叶部病害之一。叶片正面出现黄色多角形病斑，背面产生紫灰色霉层。",
  },
];
</script>

<style lang="scss" scoped>
.web-page {
  min-height: 100vh;
  background: #ffffff;
}

.navbar {
  position: sticky;
  top: 0;
  z-index: 1000;
  background: rgba(255, 255, 255, 0.95);
  backdrop-filter: blur(10px);
  border-bottom: 1px solid #e5e7eb;
}

.nav-container {
  max-width: 1400px;
  margin: 0 auto;
  padding: 0 40px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  height: 70px;
}

.nav-logo {
  display: flex;
  align-items: center;
  gap: 12px;
}

.logo-icon {
  font-size: 28px;
}

.logo-text {
  font-size: 22px;
  font-weight: 700;
  color: #16a34a;
}

.nav-links {
  display: flex;
  gap: 32px;
}

.nav-link {
  text-decoration: none;
  color: #374151;
  font-weight: 500;
  transition: color 0.2s ease;

  &:hover {
    color: #16a34a;
  }
}

.hero-section {
  background: linear-gradient(135deg, #f0fdf4 0%, #dcfce7 100%);
  padding: 80px 40px;
}

.hero-content {
  max-width: 1400px;
  margin: 0 auto;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 60px;
}

.hero-text {
  flex: 1;
}

.hero-text h1 {
  font-size: 64px;
  font-weight: 700;
  color: #166534;
  line-height: 1.2;
  margin-bottom: 20px;
}

.hero-text p {
  font-size: 18px;
  color: #6b7280;
  line-height: 1.6;
  margin-bottom: 32px;
}

.hero-buttons {
  margin-bottom: 48px;
}

.primary-btn {
  display: inline-block;
  text-decoration: none;
  color: white;
  font-weight: 600;
  padding: 16px 36px;
  font-size: 20px;
  background: linear-gradient(135deg, #16a34a 0%, #15803d 100%);
  border-radius: 12px;
  transition: all 0.2s ease;

  &:hover {
    transform: translateY(-2px);
    box-shadow: 0 8px 20px rgba(22, 163, 74, 0.3);
  }
}

.hero-stats {
  display: flex;
  gap: 48px;
}

.stat-item {
  display: flex;
  flex-direction: column;
}

.stat-value {
  font-size: 32px;
  font-weight: 700;
  color: #166534;
}

.stat-label {
  font-size: 14px;
  color: #6b7280;
  margin-top: 4px;
}

.hero-carousel {
  flex: 1;
  width: 600px;
}

.carousel-item {
  position: relative;
  width: 100%;
  height: 100%;
  border-radius: 20px;
  overflow: hidden;
}

.carousel-image {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.carousel-overlay {
  position: absolute;
  bottom: 0;
  left: 0;
  right: 0;
  padding: 32px;
  background: linear-gradient(transparent, rgba(0, 0, 0, 0.7));
  color: white;
}

.carousel-overlay h3 {
  font-size: 24px;
  font-weight: 600;
  margin-bottom: 12px;
}

.carousel-overlay p {
  font-size: 16px;
  opacity: 0.9;
}

.features-section {
  padding: 80px 40px;
  background: white;
}

.section-header {
  text-align: center;
  margin-bottom: 60px;
}

.section-header h2 {
  font-size: 36px;
  font-weight: 700;
  color: #166534;
  margin-bottom: 12px;
}

.section-header p {
  font-size: 16px;
  color: #6b7280;
}

.features-grid {
  max-width: 1400px;
  margin: 0 auto;
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 32px;
}

.feature-card {
  background: white;
  padding: 32px;
  border-radius: 16px;
  border: 1px solid #e5e7eb;
  transition: all 0.3s ease;

  &:hover {
    transform: translateY(-4px);
    box-shadow: 0 10px 30px rgba(22, 163, 74, 0.1);
    border-color: #bbf7d0;
  }
}

.feature-icon {
  font-size: 40px;
  margin-bottom: 16px;
}

.feature-card h3 {
  font-size: 18px;
  font-weight: 600;
  color: #166534;
  margin-bottom: 8px;
}

.feature-card p {
  font-size: 14px;
  color: #6b7280;
  line-height: 1.6;
}

.diseases-section {
  padding: 80px 40px;
  background: #f9fafb;
}

.disease-cards {
  max-width: 1400px;
  margin: 0 auto;
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 24px;
}

.disease-card {
  background: white;
  border-radius: 16px;
  overflow: hidden;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.05);
  transition: all 0.3s ease;

  &:hover {
    transform: translateY(-4px);
    box-shadow: 0 10px 25px rgba(22, 163, 74, 0.15);
  }
}

.disease-image {
  width: 100%;
  height: 180px;
  object-fit: cover;
}

.disease-content {
  padding: 20px;
}

.disease-content h4 {
  font-size: 16px;
  font-weight: 600;
  color: #166534;
  margin-bottom: 8px;
}

.disease-content p {
  font-size: 13px;
  color: #6b7280;
  line-height: 1.6;
}

.cta-section {
  padding: 80px 40px;
  background: linear-gradient(135deg, #16a34a 0%, #15803d 100%);
  text-align: center;
}

.cta-content h2 {
  font-size: 36px;
  font-weight: 700;
  color: white;
  margin-bottom: 16px;
}

.cta-content p {
  font-size: 18px;
  color: rgba(255, 255, 255, 0.8);
  margin-bottom: 32px;
}

.cta-btn {
  text-decoration: none;
  color: #166534;
  font-weight: 600;
  padding: 14px 40px;
  background: white;
  border-radius: 12px;
  transition: all 0.2s ease;

  &:hover {
    transform: translateY(-2px);
    box-shadow: 0 8px 20px rgba(0, 0, 0, 0.2);
  }
}

.footer {
  padding: 60px 40px;
  background: #1f2937;
}

.footer-content {
  max-width: 1400px;
  margin: 0 auto;
}

.footer-logo {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 40px;
}

.footer .logo-icon {
  font-size: 28px;
}

.footer .logo-text {
  font-size: 22px;
  font-weight: 700;
  color: #bbf7d0;
}

.footer-links {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 32px;
  margin-bottom: 40px;
}

.footer-link-group h4 {
  font-size: 14px;
  font-weight: 600;
  color: white;
  margin-bottom: 16px;
}

.footer-link-group a {
  display: block;
  text-decoration: none;
  color: #9ca3af;
  font-size: 14px;
  margin-bottom: 8px;
  transition: color 0.2s ease;

  &:hover {
    color: #bbf7d0;
  }
}

.footer-copyright {
  padding-top: 20px;
  border-top: 1px solid #374151;
}

.footer-copyright p {
  font-size: 13px;
  color: #6b7280;
}

@media (max-width: 1024px) {
  .hero-content {
    flex-direction: column;
    text-align: center;
  }

  .hero-text h1 {
    font-size: 36px;
  }

  .hero-carousel {
    width: 100%;
    max-width: 500px;
  }

  .hero-stats {
    justify-content: center;
  }

  .features-grid {
    grid-template-columns: repeat(2, 1fr);
  }

  .disease-cards {
    grid-template-columns: repeat(2, 1fr);
  }
}

@media (max-width: 640px) {
  .nav-links {
    display: none;
  }

  .hero-text h1 {
    font-size: 28px;
  }

  .features-grid {
    grid-template-columns: 1fr;
  }

  .disease-cards {
    grid-template-columns: 1fr;
  }
}

:deep(.el-carousel__item--card) {
  background: transparent;
}

:deep(.el-carousel__indicators--card button) {
  background: #16a34a;
  opacity: 0.5;
}

:deep(.el-carousel__indicators--card button.is-active) {
  opacity: 1;
}
</style>
