"""
检测历史记录 API 测试 - 精简版（只测试API行为，不依赖数据创建）
"""

import pytest
import base64
from datetime import datetime
from app.core.security import create_access_token
from app.entity.db_models import DetectionResult, DetectionScene, DetectionTask, User


@pytest.fixture(autouse=True)
def use_history_test_db(monkeypatch):
    """HistoryService 直接创建 SessionLocal，这里替换为测试库会话以保持 API 测试隔离。"""
    from app.services import history_service as history_service_module
    from tests.conftest import TestSessionLocal

    monkeypatch.setattr(history_service_module, "SessionLocal", TestSessionLocal)


def _create_user(db_session, username: str) -> User:
    import time

    unique_suffix = int(time.time() * 1000) % 100000
    user = User(
        username=username,
        email=f"{username}_{unique_suffix}@example.com",
        hashed_password="test-password",
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def _get_user_id(user: User) -> int:
    user_id = getattr(user, "id")
    if user_id is None:
        raise ValueError("User ID is None")
    return user_id


def _get_token(user_id: int) -> str:
    return create_access_token({"sub": str(user_id)})


def _get_headers(user_id: int) -> dict:
    return {"Authorization": f"Bearer {_get_token(user_id)}"}


def _create_history_task(
    db_session,
    user_id: int,
    class_name: str = "Tomato leaf late blight",
    class_name_cn: str = "番茄晚疫病",
) -> DetectionTask:
    """创建一条带检测结果的历史任务，避免测试依赖真实 YOLO 推理。"""
    scene = DetectionScene(
        name=f"history_scene_{user_id}_{class_name.replace(' ', '_')[:20]}",
        display_name="农业病害检测",
        category="agriculture",
        class_names=[class_name],
        class_names_cn={class_name: class_name_cn},
        is_active=True,
        created_by=user_id,
    )
    db_session.add(scene)
    db_session.flush()

    task = DetectionTask(
        user_id=user_id,
        scene_id=scene.id,
        task_type="single",
        status="completed",
        total_images=1,
        total_objects=2,
        total_inference_time=33.2,
        treatment_status="pending",
    )
    db_session.add(task)
    db_session.flush()

    db_session.add_all(
        [
            DetectionResult(
                task_id=task.id,
                image_path="leaf-a.jpg",
                annotated_image_url="http://minio/result-a.jpg",
                class_name=class_name,
                class_name_cn=class_name_cn,
                class_id=23,
                confidence=0.91,
                bbox=[1, 2, 3, 4],
            ),
            DetectionResult(
                task_id=task.id,
                image_path="leaf-b.jpg",
                annotated_image_url="http://minio/result-b.jpg",
                class_name=class_name,
                class_name_cn=class_name_cn,
                class_id=23,
                confidence=0.83,
                bbox=[5, 6, 7, 8],
            ),
        ]
    )
    db_session.commit()
    db_session.refresh(task)
    return task


# ============================================================
# 认证拦截测试
# ============================================================


def test_list_tasks_authentication_required(client):
    """GET /api/history/tasks 需要认证。"""
    response = client.get("/api/history/tasks")
    assert response.status_code == 401


def test_detail_authentication_required(client):
    """GET /api/history/tasks/{id} 需要认证。"""
    response = client.get("/api/history/tasks/1")
    assert response.status_code == 401


def test_delete_authentication_required(client):
    """DELETE /api/history/tasks/{id} 需要认证。"""
    response = client.delete("/api/history/tasks/1")
    assert response.status_code == 401


def test_summary_authentication_required(client):
    """GET /api/history/summary 需要认证。"""
    response = client.get("/api/history/summary")
    assert response.status_code == 401


def test_scenes_authentication_required(client):
    """GET /api/history/scenes 需要认证。"""
    response = client.get("/api/history/scenes")
    assert response.status_code == 401


# ============================================================
# 空数据测试（新用户没有任何数据）
# ============================================================


def test_list_tasks_empty(client, db_session):
    """新用户任务列表为空。"""
    user = _create_user(db_session, "history_empty_user")
    user_id = _get_user_id(user)
    headers = _get_headers(user_id)

    response = client.get("/api/history/tasks", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 0
    assert data["items"] == []
    assert data["total_pages"] == 0


def test_summary_empty(client, db_session):
    """新用户统计为空。"""
    user = _create_user(db_session, "history_summary_empty_user")
    user_id = _get_user_id(user)
    headers = _get_headers(user_id)

    response = client.get("/api/history/summary", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["total_tasks"] == 0
    assert data["today_tasks"] == 0
    assert data["status_counts"]["completed"] == 0
    assert data["status_counts"]["processing"] == 0
    assert data["status_counts"]["failed"] == 0
    assert data["status_counts"]["pending"] == 0
    assert data["risk_counts"]["unassessed"] == 0
    assert data["treatment_counts"]["pending"] == 0


def test_list_tasks_keyword_returns_primary_detection_fields(client, db_session):
    """历史列表应支持关键词搜索，并直接返回主要病害和显示字段。"""
    user = _create_user(db_session, "history_keyword_user")
    task = _create_history_task(db_session, _get_user_id(user))
    headers = {**_get_headers(_get_user_id(user)), "X-Display-Language": "zh"}

    response = client.get("/api/history/tasks?keyword=晚疫病", headers=headers)

    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    item = data["items"][0]
    assert item["id"] == task.id
    assert item["primary_class_name"] == "Tomato leaf late blight"
    assert item["primary_class_name_display"] == "番茄晚疫病"
    assert item["plant_name"] == "Tomato"
    assert item["plant_name_display"] == "番茄"
    assert item["disease_name_display"] == "晚疫病"
    assert item["max_confidence"] == 0.91
    assert item["class_counts_display"] == {"番茄晚疫病": 2}
    assert item["annotated_image_url"] == "http://minio/result-a.jpg"


def test_list_tasks_filters_by_multi_word_plant_name(client, db_session):
    """植物筛选使用明确映射，Bell pepper 这类多词植物不能按空格硬拆。"""
    user = _create_user(db_session, "history_plant_filter_user")
    _create_history_task(
        db_session,
        _get_user_id(user),
        class_name="Bell pepper leaf spot",
        class_name_cn="甜椒叶斑病",
    )
    headers = _get_headers(_get_user_id(user))

    response = client.get("/api/history/tasks?plant_name=Bell pepper", headers=headers)

    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert data["items"][0]["plant_name"] == "Bell pepper"
    assert data["items"][0]["disease_name"] == "Leaf spot"


def test_update_treatment_status_and_summary(client, db_session):
    """治疗状态由用户维护，并在 summary 中按业务状态统计。"""
    user = _create_user(db_session, "history_treatment_user")
    task = _create_history_task(db_session, _get_user_id(user))
    headers = _get_headers(_get_user_id(user))

    response = client.patch(
        f"/api/history/tasks/{task.id}/treatment-status",
        headers=headers,
        json={"status": "monitoring", "note": "已去除病叶，继续观察三天"},
    )

    assert response.status_code == 200
    assert response.json()["treatment_status"] == "monitoring"
    summary = client.get("/api/history/summary", headers=headers).json()
    assert summary["treatment_counts"]["monitoring"] == 1
    assert summary["treatment_counts"]["treated"] == 0


def test_create_severity_assessment_high_risk(client, db_session):
    """严重程度由问卷规则评估，YOLO confidence 不直接决定风险等级。"""
    user = _create_user(db_session, "history_severity_user")
    task = _create_history_task(db_session, _get_user_id(user))
    headers = _get_headers(_get_user_id(user))

    response = client.post(
        f"/api/history/tasks/{task.id}/severity-assessment",
        headers=headers,
        json={
            "class_name": "Tomato leaf late blight",
            "answers": {
                "affected_area": "30%～60%",
                "spread_speed": "最近几天明显增加",
                "affected_plants": "多株植株",
                "functional_damage": ["明显萎蔫", "大量落叶"],
                "growth_stage": "结果期",
                "treatment": "尚未处理",
            },
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["risk_level"] == "high"
    assert data["assessment_confidence"] == "high"
    assert data["class_name_display"] == "番茄晚疫病"
    assert data["reasons"]

    detail = client.get(f"/api/history/tasks/{task.id}", headers=headers).json()
    assert detail["task"]["risk_level"] == "high"


def test_create_severity_assessment_uses_llm_enhancement(
    client, db_session, monkeypatch
):
    """配置 LLM 时，严重程度摘要和建议可由大模型增强，等级仍受规则限幅。"""
    from app.services.history_service import HistoryService

    user = _create_user(db_session, "history_severity_llm_user")
    task = _create_history_task(db_session, _get_user_id(user))
    headers = _get_headers(_get_user_id(user))

    def fake_llm_json(_prompt):
        return (
            {
                "risk_level": "critical",
                "assessment_confidence": "high",
                "summary": "LLM 综合问卷和检测结果后认为需要立即处理。",
                "reasons": ["扩散速度快", "受影响植株较多"],
                "uncertainties": ["尚未确认是否已传播到相邻地块"],
                "recommended_actions": ["24 小时内处理重症叶片", "48 小时后复查"],
            },
            "qwen-test",
        )

    monkeypatch.setattr(HistoryService, "_invoke_llm_json", staticmethod(fake_llm_json))

    response = client.post(
        f"/api/history/tasks/{task.id}/severity-assessment",
        headers=headers,
        json={
            "class_name": "Tomato leaf late blight",
            "answers": {
                "affected_area": "10%～30%",
                "spread_speed": "最近几天明显增加",
                "affected_plants": "少量植株",
                "functional_damage": ["暂无以上情况"],
                "growth_stage": "结果期",
                "treatment": "尚未处理",
            },
        },
    )

    assert response.status_code == 200
    data = response.json()
    # 规则结果约为 moderate，LLM 请求 critical 时最多上调一级到 high。
    assert data["risk_level"] == "high"
    assert data["summary"].startswith("LLM 综合问卷")
    assert "24 小时内处理重症叶片" in data["recommended_actions"]

    detail = client.get(f"/api/history/tasks/{task.id}", headers=headers).json()
    assessment = detail["severity_assessments"][0]
    assert assessment["llm_model"] == "qwen-test"


def test_create_severity_assessment_insufficient_information(client, db_session):
    """关键信息不足时必须返回 insufficient_information。"""
    user = _create_user(db_session, "history_severity_empty_user")
    task = _create_history_task(db_session, _get_user_id(user))
    headers = _get_headers(_get_user_id(user))

    response = client.post(
        f"/api/history/tasks/{task.id}/severity-assessment",
        headers=headers,
        json={
            "class_name": "Tomato leaf late blight",
            "answers": {
                "affected_area": "不确定",
                "spread_speed": "不确定",
            },
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["risk_level"] == "insufficient_information"
    assert data["llm_model"] == "rule-based"

    detail = client.get(f"/api/history/tasks/{task.id}", headers=headers).json()
    assert detail["task"]["risk_level"] == "insufficient_information"


def test_detection_task_risk_level_column_accepts_all_severity_values():
    """任务摘要风险字段必须能容纳最长的严重程度枚举值。"""
    from app.entity.db_models import DetectionTask

    max_risk_level_length = max(
        len(level)
        for level in [
            "low",
            "moderate",
            "high",
            "critical",
            "insufficient_information",
        ]
    )

    assert DetectionTask.risk_level.type.length >= max_risk_level_length


def test_get_severity_questions(client, db_session):
    """前端从后端获取问卷问题和选项，避免硬编码字段含义。"""
    user = _create_user(db_session, "history_questions_user")
    headers = {**_get_headers(_get_user_id(user)), "X-Display-Language": "zh"}

    response = client.get("/api/history/severity-questions", headers=headers)

    assert response.status_code == 200
    data = response.json()
    keys = [item["key"] for item in data["questions"]]
    assert "affected_area" in keys
    assert "spread_speed" in keys
    assert "additional_notes" in keys
    assert data["minimum_known_answers"] == 3


def test_update_location_refreshes_weather_risk_by_default(client, db_session, monkeypatch):
    """补充位置默认会同步生成天气环境风险并保存到任务。"""
    user = _create_user(db_session, "history_weather_user")
    task = _create_history_task(db_session, _get_user_id(user))
    headers = _get_headers(_get_user_id(user))

    class FakeWeatherResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "hourly": {
                    "temperature_2m": [24] * 72,
                    "relative_humidity_2m": [88] * 72,
                    "precipitation": [0.4] * 72,
                    "precipitation_probability": [75] * 72,
                },
                "daily": {
                    "precipitation_sum": [8, 12, 9],
                    "temperature_2m_max": [28, 27, 26],
                    "temperature_2m_min": [20, 21, 20],
                },
            }

    def fake_get(*_args, **_kwargs):
        return FakeWeatherResponse()

    from app.services import history_service as history_service_module

    monkeypatch.setattr(history_service_module.httpx, "get", fake_get)

    location_response = client.patch(
        f"/api/history/tasks/{task.id}/location",
        headers=headers,
        json={
            "latitude": 30.52,
            "longitude": 114.31,
            "location_name": "试验田 A 区",
            "location_source": "browser",
        },
    )
    assert location_response.status_code == 200
    data = location_response.json()
    assert data["location_source"] == "browser"
    assert data["environment_risk_level"] in {"high", "critical"}
    assert data["weather_recommendations"]

    detail = client.get(f"/api/history/tasks/{task.id}", headers=headers).json()
    assert detail["task"]["location_name"] == "试验田 A 区"
    assert detail["task"]["environment_risk_level"] in {"high", "critical"}


def test_update_location_can_skip_weather_refresh(client, db_session, monkeypatch):
    """前端可关闭自动天气分析，只保存位置。"""
    user = _create_user(db_session, "history_location_only_user")
    task = _create_history_task(db_session, _get_user_id(user))
    headers = _get_headers(_get_user_id(user))

    from app.services import history_service as history_service_module

    def fail_if_called(*_args, **_kwargs):
        raise AssertionError("weather service should not be called")

    monkeypatch.setattr(history_service_module.httpx, "get", fail_if_called)

    response = client.patch(
        f"/api/history/tasks/{task.id}/location?refresh_weather=false",
        headers=headers,
        json={
            "latitude": 30.52,
            "longitude": 114.31,
            "location_name": "试验田 A 区",
            "location_source": "manual",
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["location_source"] == "manual"
    assert "environment_risk_level" not in data

    detail = client.get(f"/api/history/tasks/{task.id}", headers=headers).json()
    assert detail["task"]["location_name"] == "试验田 A 区"
    assert detail["task"]["environment_risk_level"] is None


def test_update_location_weather_risk_uses_llm_enhancement(
    client, db_session, monkeypatch
):
    """默认天气分析可采用 LLM 摘要和建议，风险等级仍受规则限幅。"""
    from app.services.history_service import HistoryService

    user = _create_user(db_session, "history_weather_llm_user")
    task = _create_history_task(db_session, _get_user_id(user))
    headers = _get_headers(_get_user_id(user))

    class FakeWeatherResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "hourly": {
                    "temperature_2m": [24] * 72,
                    "relative_humidity_2m": [76] * 72,
                    "precipitation": [0] * 72,
                    "precipitation_probability": [10] * 72,
                },
                "daily": {
                    "precipitation_sum": [0, 0, 0],
                    "temperature_2m_max": [28, 27, 26],
                    "temperature_2m_min": [20, 21, 20],
                },
            }

    def fake_get(*_args, **_kwargs):
        return FakeWeatherResponse()

    def fake_llm_json(_prompt):
        return (
            {
                "environment_risk_level": "critical",
                "summary": "LLM 认为未来三天仍需重点防范叶部病害扩散。",
                "recommendations": ["控制棚内湿度", "雨后或浇水后 48 小时复查"],
                "reasons": ["湿度偏高", "检测类别对湿度敏感"],
            },
            "qwen-test",
        )

    from app.services import history_service as history_service_module

    monkeypatch.setattr(history_service_module.httpx, "get", fake_get)
    monkeypatch.setattr(HistoryService, "_invoke_llm_json", staticmethod(fake_llm_json))

    response = client.patch(
        f"/api/history/tasks/{task.id}/location",
        headers=headers,
        json={
            "latitude": 30.52,
            "longitude": 114.31,
            "location_name": "试验田 A 区",
            "location_source": "browser",
        },
    )

    assert response.status_code == 200
    data = response.json()
    # 规则结果约为 moderate，LLM 请求 critical 时最多上调一级到 high。
    assert data["environment_risk_level"] == "high"
    assert data["weather_summary"].startswith("LLM 认为")
    assert "控制棚内湿度" in data["weather_recommendations"]
    assert data["llm_model"] == "qwen-test"

    detail = client.get(f"/api/history/tasks/{task.id}", headers=headers).json()
    assert detail["task"]["environment_risk_level"] == "high"
    assert detail["task"]["weather_summary"].startswith("LLM 认为")


def test_refresh_weather_risk_requires_location(client, db_session):
    """没有位置时不能调用天气分析，前端应先提示用户授权定位或手动填写地点。"""
    user = _create_user(db_session, "history_weather_no_location_user")
    task = _create_history_task(db_session, _get_user_id(user))
    headers = _get_headers(_get_user_id(user))

    response = client.get(f"/api/history/tasks/{task.id}/weather-risk", headers=headers)

    assert response.status_code == 400
    assert "地理位置" in response.text


def test_report_preview_and_html_download(client, db_session):
    """报告预览返回 JSON，HTML 下载返回附件内容。"""
    user = _create_user(db_session, "history_report_user")
    task = _create_history_task(db_session, _get_user_id(user))
    headers = _get_headers(_get_user_id(user))
    client.post(
        f"/api/history/tasks/{task.id}/severity-assessment",
        headers=headers,
        json={
            "class_name": "Tomato leaf late blight",
            "answers": {
                "affected_area": "10%～30%",
                "spread_speed": "缓慢增加",
                "affected_plants": "少量植株",
            },
        },
    )
    task.latitude = 30.52
    task.longitude = 114.31
    task.location_name = "试验田 A 区"
    task.environment_risk_level = "high"
    task.weather_summary = "未来三天湿度偏高，需要重点观察。"
    task.weather_recommendations = ["控制棚内湿度", "雨后 48 小时复查"]
    task.weather_snapshot = {
        "hourly": {
            "temperature_2m": [24] * 72,
            "relative_humidity_2m": [88] * 72,
            "precipitation": [0.2] * 72,
            "precipitation_probability": [65] * 72,
        },
        "daily": {"precipitation_sum": [3, 4, 5]},
    }
    task.weather_updated_at = datetime.now()
    task.treatment_note = "已去除部分病叶"
    db_session.commit()

    preview = client.get(f"/api/history/tasks/{task.id}/report", headers=headers)
    assert preview.status_code == 200
    preview_data = preview.json()
    assert preview_data["task"]["id"] == task.id
    assert preview_data["severity_assessments"][0]["risk_level"] == "moderate"
    assert preview_data["inspection_images"][0]["annotated_image_url"] == "http://minio/result-a.jpg"
    assert preview_data["question_answers"][0]["label"] == "目前出现症状的叶片大约占整株多少？"
    assert preview_data["weather_metrics"]["avg_humidity"] == 88.0
    assert "番茄晚疫病" in preview_data["integrated_conclusion"]
    assert "天气环境风险为 high" in preview_data["integrated_conclusion"]
    assert "控制棚内湿度" in preview_data["action_items"]
    assert preview_data["data_sources"]["weather_source"] == "Open-Meteo"
    assert "复查日期：" in preview_data["follow_up_template"]

    download = client.get(
        f"/api/history/tasks/{task.id}/report/download?format=html",
        headers=headers,
    )
    assert download.status_code == 200
    assert "text/html" in download.headers["content-type"]
    assert "attachment" in download.headers["content-disposition"]
    assert "农作物病害检测报告" in download.text
    assert "综合结论" in download.text
    assert "检测图片" in download.text
    assert "问卷答案" in download.text
    assert "未来 3 天平均湿度" in download.text
    assert "数据来源说明" in download.text
    assert "复查记录" in download.text


def test_report_download_defaults_to_pdf(client, db_session, tmp_path):
    """不传 format 时默认导出 PDF，并可嵌入本地原图和标注图。"""
    user = _create_user(db_session, "history_pdf_report_user")
    task = _create_history_task(db_session, _get_user_id(user))
    headers = _get_headers(_get_user_id(user))
    image_bytes = base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAIAAACQd1PeAAAADUlEQVR4nGP4z8AAAAMBAQDJ/pLvAAAAAElFTkSuQmCC"
    )
    source_image = tmp_path / "source.png"
    annotated_image = tmp_path / "annotated.png"
    source_image.write_bytes(image_bytes)
    annotated_image.write_bytes(image_bytes)
    for result in db_session.query(DetectionResult).filter(DetectionResult.task_id == task.id):
        result.image_path = str(source_image)
        result.annotated_image_url = str(annotated_image)
    db_session.commit()

    response = client.get(f"/api/history/tasks/{task.id}/report/download", headers=headers)

    assert response.status_code in {200, 503}
    if response.status_code == 200:
        assert response.headers["content-type"] == "application/pdf"
        assert response.content.startswith(b"%PDF")
    else:
        assert "reportlab" in response.text


def test_video_report_samples_skip_unembeddable_frames(tmp_path):
    """视频 PDF 只选择可嵌入的关键帧，避免显示不可嵌入占位。"""
    from app.services.history_service import HistoryService

    image_path = tmp_path / "frame.png"
    image_path.write_bytes(
        base64.b64decode(
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAIAAACQd1PeAAAADUlEQVR4nGP4z8AAAAMBAQDJ/pLvAAAAAElFTkSuQmCC"
        )
    )

    samples = HistoryService._select_report_image_samples(
        {
            "task": {"task_type": "video"},
            "inspection_images": [
                {
                    "image_path": "frame_1.jpg",
                    "annotated_image_url": str(image_path),
                    "classes": ["马铃薯晚疫病"],
                },
                {
                    "image_path": "frame_2.jpg",
                    "annotated_image_url": None,
                    "classes": ["马铃薯晚疫病"],
                },
                {
                    "image_path": "frame_3.jpg",
                    "annotated_image_url": "http://minio/missing.jpg",
                    "classes": ["马铃薯晚疫病"],
                },
            ],
        }
    )

    assert len(samples) == 1
    assert samples[0]["annotated"] == str(image_path)


# ============================================================
# 无效ID测试（返回404）
# ============================================================


def test_detail_invalid(client, db_session):
    """无效任务ID返回404。"""
    user = _create_user(db_session, "history_detail_invalid_user")
    user_id = _get_user_id(user)
    headers = _get_headers(user_id)

    response = client.get("/api/history/tasks/99999", headers=headers)
    assert response.status_code == 404
    assert "任务不存在" in response.json()["error"]


def test_delete_invalid(client, db_session):
    """删除不存在的任务返回404。"""
    user = _create_user(db_session, "history_delete_invalid_user")
    user_id = _get_user_id(user)
    headers = _get_headers(user_id)

    response = client.delete("/api/history/tasks/99999", headers=headers)
    assert response.status_code == 404
    assert "任务不存在" in response.json()["error"]


# ============================================================
# 场景列表测试
# ============================================================


def test_scenes_basic(client, db_session):
    """获取场景列表。"""
    user = _create_user(db_session, "history_scenes_user")
    user_id = _get_user_id(user)
    headers = _get_headers(user_id)

    response = client.get("/api/history/scenes", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert "scenes" in data
