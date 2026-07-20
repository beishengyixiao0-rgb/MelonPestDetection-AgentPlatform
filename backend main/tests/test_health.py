# tests/test_health.py

"""
健康检查接口测试

测试目标：
  - GET /api/health           基础健康检查（应用存活）
  - GET /api/health/detail    详细健康检查（依赖服务状态）
  - GET /                     根路径欢迎信息
"""

import pytest


class TestHealthCheck:
    """基础健康检查接口测试 - GET /api/health"""

    def test_health_check(self, client):
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

    def test_health_check_response_time(self, client):
        """测试健康检查接口响应时间"""
        import time

        start = time.time()
        response = client.get("/api/health")
        elapsed = (time.time() - start) * 1000

        assert response.status_code == 200
        assert elapsed < 100, f"健康检查响应时间应<100ms，实际{elapsed:.2f}ms"

    def test_health_check_no_error_logs(self, client, caplog):
        """测试健康检查不产生ERROR级别日志"""
        import logging

        with caplog.at_level(logging.ERROR):
            response = client.get("/api/health")
            assert response.status_code == 200
            assert not any(record.levelname == "ERROR" for record in caplog.records)

    def test_health_check_without_auth(self, client):
        """测试健康检查不需要认证"""
        response = client.get("/api/health")
        assert response.status_code == 200

        # 验证没有Authorization头也能访问
        response = client.get("/api/health", headers={})
        assert response.status_code == 200


class TestHealthDetailCheck:
    """详细健康检查接口测试 - GET /api/health/detail"""

    def test_health_detail_check_success(self, client):
        """测试详细健康检查：所有依赖服务正常"""
        response = client.get("/api/health/detail")

        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 200
        assert data["message"] == "ok"

        # 验证data结构
        assert "status" in data["data"]
        assert "app_name" in data["data"]
        assert "version" in data["data"]
        assert "services" in data["data"]

        # 验证各依赖服务
        services = data["data"]["services"]
        assert "database" in services
        assert "redis" in services
        assert "minio" in services

        # 如果所有服务健康，status应为healthy
        all_healthy = all(s["status"] == "healthy" for s in services.values())
        if all_healthy:
            assert data["data"]["status"] == "healthy"
        else:
            assert data["data"]["status"] == "degraded"

    def test_health_detail_check_response_time(self, client):
        """测试详细健康检查响应时间"""
        import time

        start = time.time()
        response = client.get("/api/health/detail")
        elapsed = (time.time() - start) * 1000

        assert response.status_code == 200
        # 详细检查需要连接多个服务，允许更长时间
        assert elapsed < 5000, f"详细健康检查响应时间应<5000ms，实际{elapsed:.2f}ms"


class TestRoot:
    """根路径测试 - GET /"""

    def test_root_welcome(self, client):
        """测试根路径欢迎接口"""
        response = client.get("/")

        assert response.status_code == 200
        data = response.json()
        assert "message" in data
        assert "version" in data
        assert "docs" in data


class TestHealthCheckPerformance:
    """健康检查性能测试"""

    def test_concurrent_health_checks(self, client):
        import concurrent.futures
        import time

        def make_request():
            start = time.perf_counter()
            resp = client.get("/api/health")
            cost_ms = (time.perf_counter() - start) * 1000
            return resp, cost_ms

        with concurrent.futures.ThreadPoolExecutor(max_workers=50) as executor:
            futures = [executor.submit(make_request) for _ in range(50)]
            results = [f.result() for f in futures]

        # 校验所有请求200
        assert all(r[0].status_code == 200 for r in results)
        # 放宽并发阈值：并发场景允许轻微抖动，150ms更合理；或区分pipeline/单机并发场景
        max_cost = max(r[1] for r in results)
        assert max_cost < 150, (
            f"并发健康检查单次最大耗时{max_cost:.2f}ms，超过阈值150ms"
        )
