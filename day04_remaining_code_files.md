# Day04 剩余代码文件

说明：

- 本文件整理自 `6. Day04-基于YOLOv11的目标检测智能体平台-日志监控&单元测试.pdf`。
- 不包含已经新建过的文件：`backend/app/core/logger.py`、`backend/app/core/exceptions.py`、`backend/app/middleware/__init__.py`、`backend/app/middleware/request_logger.py`、`backend/app/api/health.py`、`backend/logs/.gitkeep`。
- 已将 PDF 提取出的异常中文兼容字形改成正常汉字。
- 必要修改：PDF 中部分代码因分页提取导致缩进或字符串换行断裂，这里按原意修正为可读、可运行的代码片段。

## backend/app/config/settings.py

```python
# 在 Settings 类中添加日志相关配置（已有 LOG_LEVEL，再补充文件配置）


    # ── 日志配置 ──────────────────────────────────────
    LOG_LEVEL: str = "INFO"              # 已有，日志级别
    LOG_DIR: str = "logs"                # 日志目录（相对于 backend/）
    LOG_MAX_BYTES: int = 10 * 1024 * 1024   # 单文件最大 10MB
    LOG_BACKUP_COUNT: int = 5            # 保留 5 份历史日志
```

## .gitignore

```gitignore
# 日志文件
logs/
*.log
```

## backend/main.py

```python
from app.core.exceptions import register_exception_handlers


# ... 创建 app 后 ...


# ── 注册全局异常处理器 ─────────────────────────────────
register_exception_handlers(app)
```

```python
from app.middleware.request_logger import RequestLogMiddleware


# ── 注册中间件（注意顺序）──────────────────────────────
# 中间件执行顺序：后添加的先执行（洋葱模型）
# 1. CORS 中间件（最先执行，处理跨域）
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# 2. 请求日志中间件（在 CORS 之后执行）
app.add_middleware(RequestLogMiddleware)
```

```python
from app.api.health import router as health_router


# 注册路由
app.include_router(auth_router)
app.include_router(health_router)
```

## frontend/src/utils/errorReporter.js

```javascript
/**
 * 前端全局错误监控与上报
 *
 * 职责：
 *     - 捕获 JavaScript 运行时错误
 *     - 捕获未处理的 Promise 异常
 *     - 捕获 Vue 组件渲染错误
 *     - 将错误信息上报到后端（用于分析和告警）
 *
 * 使用方式（在 main.js 中）：
 *     import { setupErrorReporting } from "@/utils/errorReporter";
 *     setupErrorReporting(app);
 */


import { ElMessage } from "element-plus";


// ── 错误上报地址 ──────────────────────────────────────
// Day 4 先上报到控制台 + 本地存储，Day 11 接入后端 API
const REPORT_TO_BACKEND = false; // 生产环境设为 true
const REPORT_API = "/api/errors/report";


/**
 * 上报错误信息
 * 当前实现：输出到控制台 + 存入 localStorage
 * 生产环境可发送到后端日志收集服务
 */
function reportError(errorInfo) {
     // 1. 控制台输出（开发调试）
     console.error("[ErrorReporter]", errorInfo);


     // 2. 存入本地存储（最近 50 条错误）
     try {
          const errors = JSON.parse(localStorage.getItem("error_logs") || "[]");
          errors.push({
              ...errorInfo,
              timestamp: new Date().toISOString(),
              url: window.location.href,
              userAgent: navigator.userAgent,
          });
          // 只保留最近 50 条
          if (errors.length > 50) {
              errors.splice(0, errors.length - 50);
          }
          localStorage.setItem("error_logs", JSON.stringify(errors));
     } catch (e) {
          // localStorage 写入失败不影响程序运行
          console.warn("ErrorReporter: localStorage 写入失败", e);
     }


     // 3. 上报到后端（生产环境启用）
     if (REPORT_TO_BACKEND) {
          fetch(REPORT_API, {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify(errorInfo),
          }).catch(() => {
              // 上报失败时静默处理，不能因为上报失败而再次报错
          });
     }
}


/**
    * 初始化全局错误监控
    * @param {import('vue').App} app - Vue 应用实例
    */
export function setupErrorReporting(app) {
     // ── 1. Vue 组件错误 ────────────────────────────────
     app.config.errorHandler = (err, instance, info) => {
          reportError({
              type: "vue_error",
              message: err.message,
              stack: err.stack,
              component: info, // 错误发生所在组件的生命周期钩子
          });


          // 给用户友好提示
          ElMessage.error("页面渲染出错，请刷新重试");
     };


     // ── 2. JavaScript 运行时错误 ────────────────────────
     window.onerror = (message, source, lineno, colno, error) => {
          reportError({
            type: "js_error",
            message: message,
            source: source,
            lineno: lineno,
            colno: colno,
            stack: error?.stack,
          });
     };


     // ── 3. 未捕获的 Promise 异常 ────────────────────────
     window.onunhandledrejection = (event) => {
          reportError({
            type: "promise_rejection",
            message: event.reason?.message || String(event.reason),
            stack: event.reason?.stack,
          });


          // 阻止默认的浏览器控制台输出（已自行处理）
          event.preventDefault();
     };


     console.log("[ErrorReporter] 全局错误监控已启用");
}
```

## frontend/src/main.js

```javascript
import { setupErrorReporting } from "@/utils/errorReporter";


// ── 创建并配置应用 ────────────────────────────────────
const app = createApp(App);


// 注册全局错误监控（在其他插件之前注册）
setupErrorReporting(app);


// 注册插件
app.use(pinia);
app.use(router);
app.use(ElementPlus, { locale: zhCn });


// 挂载到 DOM
app.mount("#app");
```

## backend/requirements.txt

```txt
# ── 测试 ──────────────────────────────────────────────
pytest==8.0.0
pytest-asyncio==0.23.0
httpx==0.27.0
```

## backend/pytest.ini

```ini
# pytest 配置文件
# 文档：https://docs.pytest.org/en/stable/reference/customize.html


[pytest]
# 测试文件搜索模式
testpaths = tests


# 异步测试模式
asyncio_mode = auto


# 输出格式：-v 显示每个测试名，-s 允许 print 输出
addopts = -v --tb=short


# 过滤警告（减少无关信息）
filterwarnings =
      ignore::DeprecationWarning
      ignore::UserWarning
```

## backend/tests/conftest.py

```python
"""
pytest 全局 Fixtures

Fixtures 是 pytest 的核心概念，用于：
    - 创建测试所需的前置条件（如数据库连接、测试客户端）
    - 在所有测试用例间共享资源
    - 自动清理测试产生的数据

conftest.py 中的 fixtures 对所有测试文件可用，无需显式导入。
"""


import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


from app.database.session import Base, get_db


# ── 测试数据库 ────────────────────────────────────────
# 使用 SQLite 内存数据库进行测试，避免依赖 PostgreSQL
# 优点：速度快、隔离性好、无需清理
# 注意：SQLite 不支持 PostgreSQL 特有功能（如 JSON 字段），
# 但对于基础 CRUD 测试足够
TEST_DATABASE_URL = "sqlite:///./test.db"


test_engine = create_engine(
      TEST_DATABASE_URL,
      connect_args={"check_same_thread": False},   # SQLite 特有参数
)


TestSessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=test_engine,
)


def override_get_db():
    """覆盖 FastAPI 的 get_db 依赖，使用测试数据库"""
    db = TestSessionLocal()
    try:
           yield db
    finally:
           db.close()


# ── 导入所有模型（确保 Base.metadata 包含所有表定义）───
from app.entity import db_models        # noqa: E402, F401
from main import app     # noqa: E402


# 覆盖依赖
app.dependency_overrides[get_db] = override_get_db


@pytest.fixture(scope="session", autouse=True)
def setup_test_database():
    """
    创建测试数据库表（所有测试共享）

    scope="session"：整个测试会话只执行一次
    autouse=True：自动应用，无需在测试函数中显式引用
    """
    Base.metadata.create_all(bind=test_engine)
    yield
    # 测试结束后清理
    Base.metadata.drop_all(bind=test_engine)
    # 删除 SQLite 文件
    import os
    if os.path.exists("./test.db"):
           os.remove("./test.db")


@pytest.fixture
def client():
    """
    提供 FastAPI 测试客户端

    用法：
           def test_health(client):
               response = client.get("/api/health")
               assert response.status_code == 200
    """
    return TestClient(app)


@pytest.fixture
def db_session():
      """
      提供独立的数据库会话（每个测试用独立事务）

      用法：
             def test_create_user(db_session):
                 user = User(username="test", ...)
                 db_session.add(user)
                 db_session.commit()
      """
      session = TestSessionLocal()
      try:
             yield session
      finally:
             session.rollback()
             session.close()
```

## backend/tests/test_health.py

```python
"""
健康检查接口测试

测试目标：
  - GET /api/health 返回正确的状态和格式
  - GET / 返回欢迎信息
"""


def test_health_check(client):
      """测试基础健康检查接口"""
      response = client.get("/api/health")


      # 验证状态码
      assert response.status_code == 200


      # 验证响应格式
      data = response.json()
      assert data["code"] == 200
      assert data["message"] == "ok"
      assert data["data"]["status"] == "healthy"
      assert data["data"]["app_name"] == "RSOD Agent Platform"
      assert "version" in data["data"]


def test_root(client):
      """测试根路径欢迎接口"""
      response = client.get("/")


      assert response.status_code == 200
      data = response.json()
      assert "message" in data
      assert "version" in data
      assert "docs" in data
```

## backend/tests/test_auth.py

```python
"""
认证接口测试

测试目标：
  - 用户注册：正常注册、重复用户名、参数验证
  - 用户登录：正常登录、错误密码、不存在的用户
  - 获取当前用户：有 Token、无 Token、无效 Token

测试策略：
  - 每个测试用例独立，不依赖其他测试的执行顺序
  - 使用唯一的用户名避免测试间冲突
"""


import pytest


class TestRegister:
      """用户注册测试"""

      def test_register_success(self, client):
          """正常注册"""
          response = client.post(
              "/api/auth/register",
              json={
                   "username": "test_register_user",
                   "email": "test_register@example.com",
                   "password": "123456",
              },
          )
          assert response.status_code == 201
          data = response.json()
          assert data["username"] == "test_register_user"
          assert data["email"] == "test_register@example.com"
          # 确保不返回密码字段
          assert "hashed_password" not in data
          assert "password" not in data

      def test_register_duplicate_username(self, client):
          """重复用户名注册"""
          # 先注册一个用户
          client.post(
              "/api/auth/register",
              json={
                   "username": "dup_user",
                   "email": "dup1@example.com",
                   "password": "123456",
              },
          )
          # 用相同用户名再注册
          response = client.post(
              "/api/auth/register",
              json={
                   "username": "dup_user",
                   "email": "dup2@example.com",
                   "password": "123456",
              },
          )
          assert response.status_code == 400

      def test_register_short_username(self, client):
          """用户名过短（少于 3 字符）"""
          response = client.post(
              "/api/auth/register",
              json={
                   "username": "ab",
                   "email": "short@example.com",
                   "password": "123456",
              },
          )
          assert response.status_code == 422

      def test_register_short_password(self, client):
          """密码过短（少于 6 位）"""
          response = client.post(
              "/api/auth/register",
              json={
                   "username": "short_pwd_user",
                   "email": "shortpwd@example.com",
                   "password": "123",
              },
          )
          assert response.status_code == 422

      def test_register_missing_fields(self, client):
          """缺少必填字段"""
          response = client.post(
              "/api/auth/register",
              json={"username": "no_email_user"},
          )
          assert response.status_code == 422


class TestLogin:
    """用户登录测试"""

    def test_login_success(self, client):
        """正常登录"""
        # 先注册
        client.post(
            "/api/auth/register",
            json={
                   "username": "login_user",
                   "email": "login@example.com",
                   "password": "123456",
            },
        )
        # 再登录
        response = client.post(
            "/api/auth/login",
            json={
                   "username": "login_user",
                   "password": "123456",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"
        assert data["user"]["username"] == "login_user"

    def test_login_wrong_password(self, client):
        """密码错误"""
        # 先注册
        client.post(
            "/api/auth/register",
            json={
                   "username": "wrong_pwd_user",
                   "email": "wrongpwd@example.com",
                   "password": "123456",
            },
        )
        # 用错误密码登录
        response = client.post(
            "/api/auth/login",
            json={
                 "username": "wrong_pwd_user",
                 "password": "wrongpassword",
            },
        )
        assert response.status_code == 401

    def test_login_nonexistent_user(self, client):
        """不存在的用户"""
        response = client.post(
            "/api/auth/login",
            json={
                 "username": "no_such_user_12345",
                 "password": "123456",
            },
        )
        assert response.status_code == 401


class TestGetCurrentUser:
    """获取当前用户测试"""

    def test_get_me_with_valid_token(self, client):
        """使用有效 Token 获取用户信息"""
        # 注册并登录
        client.post(
            "/api/auth/register",
            json={
                 "username": "me_user",
                 "email": "me@example.com",
                 "password": "123456",
            },
        )
        login_response = client.post(
            "/api/auth/login",
            json={
                 "username": "me_user",
                 "password": "123456",
            },
        )
        token = login_response.json()["access_token"]


        # 使用 Token 获取用户信息
        response = client.get(
            "/api/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["username"] == "me_user"
        assert data["email"] == "me@example.com"

    def test_get_me_without_token(self, client):
        """不带 Token 访问受保护接口"""
        response = client.get("/api/auth/me")
        assert response.status_code == 401

    def test_get_me_with_invalid_token(self, client):
        """使用无效 Token"""
        response = client.get(
             "/api/auth/me",
             headers={"Authorization": "Bearer invalid_token_here"},
        )
        assert response.status_code == 401
```

## frontend/vite.config.js

```javascript
import vue from "@vitejs/plugin-vue";
import { defineConfig } from "vite";
import path from "path";
import { fileURLToPath } from "url";


const __dirname = path.dirname(fileURLToPath(import.meta.url));


export default defineConfig({
  plugins: [vue()],
  resolve: {
       alias: {
            "@": path.resolve(__dirname, "src"),
       },
  },


  // ── CSS 预处理器配置 ──────────────────────────────
  css: {
       preprocessorOptions: {
            scss: {
                 additionalData: `@use "@/assets/styles/variables.scss" as *;`,
            },
       },
  },


  // ── 开发服务器配置 ────────────────────────────────
  server: {
       port: 5173,
       open: true,
       proxy: {
            "/api": {
                 target: "http://localhost:8000",
                 changeOrigin: true,
            },
       },
  },


  // ── Vitest 测试配置 ───────────────────────────────
  test: {
       // 使用 happy-dom 模拟浏览器环境
       environment: "happy-dom",
       // 全局 setup 文件
       setupFiles: ["./tests/setup.js"],
       // 测试文件匹配模式
       include: ["tests/**/*.{test,spec}.{js,ts}"],
       // 覆盖率（可选）
       coverage: {
            provider: "v8",
            reporter: ["text", "html"],
       },
  },
});
```

## frontend/tests/setup.js

```javascript
/**
    * Vitest 全局 setup
    * 在每个测试文件执行前自动运行
    */


// 模拟 localStorage（happy-dom 已内置）
// 如需额外 mock，在此添加


// 模拟 Element Plus 的 ElMessage（避免测试中弹出消息框）
import { vi } from "vitest";


vi.mock("element-plus", async () => {
        const actual = await vi.importActual("element-plus");
        return {
             ...actual,
             ElMessage: {
                  success: vi.fn(),
                  error: vi.fn(),
                  warning: vi.fn(),
                  info: vi.fn(),
             },
        };
});
```

## frontend/package.json

```json
{
        "scripts": {
             "dev": "vite",
             "build": "vite build",
             "preview": "vite preview",
             "test": "vitest",
             "test:run": "vitest run",
             "test:coverage": "vitest run --coverage"
        }
}
```

## frontend/tests/utils/request.test.js

```javascript
/**
    * Axios 请求封装测试
    *
    * 测试目标：
    *         - Axios 实例创建正确
    *         - 请求拦截器正常注入 Token
    *         - 响应拦截器正确处理错误
    */


import { describe, it, expect, vi, beforeEach } from "vitest";


describe("Axios 请求封装", () => {
  beforeEach(() => {
      // 每个测试前清除 mock
      vi.clearAllMocks();
      // 清除 localStorage
      localStorage.clear();
  });


  it("应该正确创建 axios 实例", async () => {
      const { default: request } = await import("@/utils/request");
      expect(request).toBeDefined();
      expect(request.defaults.baseURL).toBe("/api");
      expect(request.defaults.timeout).toBe(30000);
  });


  it("请求拦截器应该设置 Content-Type", async () => {
      const { default: request } = await import("@/utils/request");
      expect(request.defaults.headers["Content-Type"]).toBe("application/json");
  });
});


describe("错误上报模块", () => {
  it("应该正确初始化错误上报", async () => {
      const { setupErrorReporting } = await import("@/utils/errorReporter");
      expect(setupErrorReporting).toBeDefined();
      expect(typeof setupErrorReporting).toBe("function");
  });


  it("错误信息应该存入 localStorage", () => {
      // 模拟错误上报
      const errorInfo = {
           type: "test_error",
           message: "测试错误",
      };


      // 手动触发上报逻辑
      const errors = JSON.parse(localStorage.getItem("error_logs") || "[]");
      errors.push({ ...errorInfo, timestamp: new Date().toISOString() });
      localStorage.setItem("error_logs", JSON.stringify(errors));


      // 验证
      const stored = JSON.parse(localStorage.getItem("error_logs"));
      expect(stored).toHaveLength(1);
      expect(stored[0].type).toBe("test_error");
  });
});
```

## frontend/tests/components/AppHeader.test.js

```javascript
/**
 * AppHeader 组件测试（示例）
 *
 * 注意：组件测试需要完整模拟 Element Plus 和 Router，
 * Day 4 只展示基础写法，后续 Days 会完善更多组件测试。
 */


import { describe, it, expect, vi } from "vitest";


// Day 4 先测试工具函数，组件测试在后续 Day 中完善
describe("AppHeader 组件", () => {
     it("组件文件应该存在", async () => {
       // 验证组件文件可被导入
       const module = await import("@/components/layout/AppHeader.vue");
       expect(module.default).toBeDefined();
     });
});
```
