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
            集作物病害检测、土壤分析、天气预测与产量优化于一体的
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
      <div class="disease-carousel-wrapper">
        <div class="disease-cards">
          <div
            v-for="disease in visibleDiseases"
            :key="disease.name"
            class="disease-card"
          >
            <img
              :src="disease.image"
              :alt="disease.name"
              class="disease-image"
            />
            <div class="disease-content">
              <h4>{{ disease.name }}</h4>
              <div class="disease-detail">
                <p><strong>症状：</strong>{{ disease.symptoms }}</p>
                <p><strong>发病规律：</strong>{{ disease.occurrence }}</p>
                <p><strong>防治措施：</strong>{{ disease.control }}</p>
              </div>
            </div>
          </div>
        </div>
        <div class="carousel-indicators">
          <button
            v-for="(_, index) in totalPages"
            :key="index"
            class="indicator-btn"
            :class="{ active: currentPage === index }"
            @click="goToPage(index)"
          ></button>
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
import { computed, onMounted, onUnmounted, ref } from "vue";

const features = [
  {
    icon: "🔍",
    title: "AI病害检测",
    description:
      "基于深度学习的计算机视觉技术，快速准确识别多种农作物病虫害，可识别35种病害。",
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
    icon: "🏠",
    title: "数据仪表盘",
    description:
      "直观展示农场整体健康状况、检测统计和关键指标，一目了然掌控全局。",
  },
  {
    icon: "···",
    title: "更多功能",
    description: "更多功能正在开发，敬请期待",
  },
];

const carouselImages = [
  {
    url: "https://trae-api-cn.mchost.guru/api/ide/v1/text_to_image?prompt=healthy%20green%20crops%20in%20agricultural%20field%20with%20sunlight%2C%20modern%20farming%2C%20natural%20environment&image_size=landscape_16_9",
    title: "健康作物",
    description: "实时监测作物健康状况，AI智能预警病害风险",
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
      "https://trae-api-cn.mchost.guru/api/ide/v1/text_to_image?prompt=apple%20scab%20disease%20on%20green%20leaves%2C%20dark%20olive%20green%20scab-like%20spots%2C%20circular%20lesions%2C%20apple%20tree%20disease&image_size=square",
    name: "苹果疮痂病",
    symptoms:
      "叶片正面出现圆形或不规则的橄榄绿色疮痂状斑点，边缘清晰，直径3-6毫米。病斑逐渐变为褐色或黑色，表面粗糙呈痂状隆起。严重时病斑连片，导致叶片畸形、扭曲或早期脱落。果实表面出现褐色圆形病斑，影响品质和商品价值。",
    occurrence:
      "病菌以菌丝体在病叶、病果上越冬，次年春季产生分生孢子，通过风雨传播。气温10-20℃、相对湿度70%以上时易发病。苹果谢花后至幼果期是侵染高峰期，降雨频繁的年份发病严重。",
    control:
      "选用抗病品种；冬季彻底清除落叶病果，集中烧毁；加强果园通风透光；谢花后及时喷药保护，可选用波尔多液、代森锰锌、三唑类杀菌剂等，每隔10-15天喷一次。",
  },
  {
    image:
      "https://trae-api-cn.mchost.guru/api/ide/v1/text_to_image?prompt=corn%20gray%20leaf%20spot%20disease%2C%20small%20oval%20gray%20lesions%20on%20corn%20leaves%2C%20brown%20border%2C%20maize%20disease&image_size=square",
    name: "玉米灰斑病",
    symptoms:
      "叶片上出现椭圆形或长方形的灰色病斑，长2-5厘米，宽1-2厘米，边缘褐色，病斑中央灰色或浅褐色。病斑多先出现在下部叶片，逐渐向上蔓延，严重时病斑汇合导致叶片干枯死亡，影响光合作用和籽粒灌浆。",
    occurrence:
      "病菌以菌丝体在病残体上越冬，次年产生分生孢子，通过风雨传播。高温高湿条件下发病重，气温25-30℃、相对湿度80%以上时易暴发流行。连作田、种植密度过大的田块发病严重。",
    control:
      "种植抗病品种；实行轮作倒茬，避免连作；收获后及时清除病残体；合理密植，加强田间通风；发病初期及时喷药，可选用苯醚甲环唑、吡唑醚菌酯等药剂喷雾防治。",
  },
  {
    image:
      "https://trae-api-cn.mchost.guru/api/ide/v1/text_to_image?prompt=potato%20late%20blight%20disease%20on%20potato%20leaves%2C%20dark%20green%20water-soaked%20lesions%2C%20white%20mold%20on%20underside%2C%20Phytophthora%20infestans&image_size=square",
    name: "马铃薯晚疫病",
    symptoms:
      "叶片出现暗绿色水渍状病斑，边缘不明显，病斑迅速扩大。湿度大时，叶背产生白色霉层。茎秆和叶柄上出现褐色长条状病斑。块茎表面出现褐色或紫褐色不规则病斑，内部组织腐烂发臭，短时间内可导致全田毁灭。",
    occurrence:
      "病菌以菌丝体在种薯内或病残体中越冬，通过风雨传播。低温高湿是发病的关键条件，气温10-22℃、相对湿度95%以上时易发病。马铃薯开花期前后是发病高峰期，连绵阴雨会导致病害迅速蔓延。",
    control:
      "选用抗病品种和无病种薯；实行轮作，避免与茄科作物连作；加强田间排水，降低湿度；发病初期及时喷药，可选用甲霜灵锰锌、霜脲锰锌、氟啶胺等药剂，每隔7-10天喷一次。",
  },
  {
    image:
      "https://trae-api-cn.mchost.guru/api/ide/v1/text_to_image?prompt=pumpkin%20powdery%20mildew%20disease%2C%20white%20powdery%20fungal%20growth%20on%20pumpkin%20leaves%2C%20cucurbit%20disease&image_size=square",
    name: "南瓜白粉病",
    symptoms:
      "叶片表面产生白色粉状物，逐渐蔓延至整个叶片。后期白粉变为灰白色，叶片变黄、干枯、脱落。叶柄和茎蔓也可受害，严重时整株早衰，影响结瓜。病害多从下部叶片开始，向上部蔓延。",
    occurrence:
      "病菌以闭囊壳在病残体上越冬，次年产生子囊孢子，通过气流传播。温暖干燥的气候条件易发病，气温20-25℃、相对湿度60%-80%时发病最重。植株生长衰弱、通风不良的田块发病严重。",
    control:
      "选用抗病品种；加强田间管理，合理密植，及时整枝打杈；发病初期及时喷药，可选用硫磺制剂、三唑酮、醚菌酯、戊唑醇等药剂喷雾防治，注意药剂交替使用。",
  },
  {
    image:
      "https://trae-api-cn.mchost.guru/api/ide/v1/text_to_image?prompt=tomato%20septoria%20leaf%20spot%20disease%2C%20small%20dark%20brown%20circular%20spots%20with%20yellow%20halo%20on%20tomato%20leaves&image_size=square",
    name: "番茄斑枯病",
    symptoms:
      "叶片上出现圆形或近圆形的褐色小斑点，直径2-4毫米，边缘褐色，中央灰白色，病斑周围有黄色晕圈。病斑上产生黑色小颗粒。严重时叶片布满病斑，导致叶片干枯脱落。病害多在番茄结果期发生，下部叶片先发病。",
    occurrence:
      "病菌以分生孢子器在病残体上越冬，次年产生分生孢子，通过风雨传播。高温高湿条件下发病重，气温20-25℃、相对湿度85%以上时易发病。番茄结果期是发病高峰期，连作田、管理粗放的田块发病严重。",
    control:
      "选用抗病品种；实行轮作，避免与茄科作物连作；及时清除病叶，减少菌源；发病初期及时喷药，可选用代森锰锌、百菌清、苯醚甲环唑、嘧菌酯等药剂喷雾防治。",
  },
  {
    image:
      "https://trae-api-cn.mchost.guru/api/ide/v1/text_to_image?prompt=grape%20black%20rot%20disease%2C%20brown%20circular%20spots%20on%20grape%20leaves%2C%20black%20pycnidia%20dots%2C%20vine%20disease&image_size=square",
    name: "葡萄黑腐病",
    symptoms:
      "叶片上出现圆形褐色病斑，直径2-5厘米，病斑中央有黑色小颗粒。果实受害后变为黑色僵果，表面布满黑色小颗粒。新梢和叶柄上出现褐色椭圆形病斑，严重时导致枝蔓枯死。",
    occurrence:
      "病菌以分生孢子器或子囊壳在病残体上越冬，次年产生孢子，通过风雨传播。高温高湿条件下发病重，气温24-28℃、相对湿度80%以上时易发病。葡萄开花后至果实成熟期是发病高峰期。",
    control:
      "选用抗病品种；冬季彻底清除病残体，集中烧毁；加强果园通风透光，合理修剪；发病初期及时喷药，可选用波尔多液、代森锰锌、苯醚甲环唑、嘧菌酯等药剂喷雾防治，重点保护幼果。",
  },
];

const currentPage = ref(0);
const itemsPerPage = 3;

const totalPages = computed(() => {
  return Math.ceil(diseaseInfo.length / itemsPerPage);
});

const visibleDiseases = computed(() => {
  const start = currentPage.value * itemsPerPage;
  return diseaseInfo.slice(start, start + itemsPerPage);
});

function goToPage(page) {
  currentPage.value = page;
}

let carouselInterval = null;

function startCarousel() {
  carouselInterval = setInterval(() => {
    currentPage.value = (currentPage.value + 1) % totalPages.value;
  }, 5000);
}

function stopCarousel() {
  if (carouselInterval) {
    clearInterval(carouselInterval);
    carouselInterval = null;
  }
}

onMounted(() => {
  startCarousel();
});

onUnmounted(() => {
  stopCarousel();
});
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
  grid-template-columns: repeat(3, 1fr);
  gap: 32px;
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
  height: 220px;
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

.disease-carousel-wrapper {
  position: relative;
}

.carousel-indicators {
  display: flex;
  justify-content: center;
  gap: 12px;
  margin-top: 32px;
}

.indicator-btn {
  width: 12px;
  height: 12px;
  border: none;
  border-radius: 50%;
  background: #d1d5db;
  cursor: pointer;
  transition: all 0.3s ease;

  &.active {
    width: 32px;
    border-radius: 6px;
    background: #16a34a;
  }

  &:hover:not(.active) {
    background: #9ca3af;
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
