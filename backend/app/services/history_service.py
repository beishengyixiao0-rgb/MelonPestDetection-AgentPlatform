"""
历史记录服务层
职责：
  - 检测任务分页查询
  - 任务详情查询（含结果列表）
  - 任务删除（级联删除结果）
  - 历史记录统计
  - 场景列表查询
架构：
  HistoryService 是无状态的纯服务，被 history.py API 层调用。
  所有数据库查询逻辑和会话管理集中在此层，API 层只负责参数校验和响应格式化。
"""

import html
import json
import re
from datetime import datetime
from io import BytesIO
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

import httpx
from sqlalchemy import desc, false, func, or_
from sqlalchemy.orm import joinedload

from app.config.detection import DetectionConfig
from app.config.settings import settings
from app.core.logger import get_logger
from app.database.session import SessionLocal
from app.entity.db_models import (
    DetectionResult,
    DetectionScene,
    DetectionTask,
    SeverityAssessment,
)
from app.entity.schemas import SeverityAssessmentResult

logger = get_logger(__name__)


class HistoryService:
    """历史记录服务"""

    RISK_LEVELS = [
        "low",
        "moderate",
        "high",
        "critical",
        "insufficient_information",
    ]
    TREATMENT_STATUSES = [
        "pending",
        "in_progress",
        "monitoring",
        "treated",
        "resolved",
    ]
    WEATHER_FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
    WEATHER_RISK_LEVELS = ["low", "moderate", "high", "critical", "unavailable"]
    CORE_RISK_LEVELS = ["low", "moderate", "high", "critical"]
    LLM_RESPONSE_PATTERN = re.compile(r"\{.*\}", re.DOTALL)
    QUESTION_DEFINITIONS = [
        {
            "key": "affected_area",
            "type": "single",
            "required": True,
            "label_zh": "目前出现症状的叶片大约占整株多少？",
            "label_en": "About what percentage of the plant leaves show symptoms?",
            "options_zh": ["少于 10%", "10%～30%", "30%～60%", "超过 60%", "不确定"],
            "options_en": ["Less than 10%", "10%-30%", "30%-60%", "More than 60%", "Unknown"],
        },
        {
            "key": "spread_speed",
            "type": "single",
            "required": True,
            "label_zh": "症状最近的发展速度如何？",
            "label_en": "How quickly have the symptoms developed recently?",
            "options_zh": ["刚刚发现，暂时没有扩大", "缓慢增加", "最近几天明显增加", "一两天内快速扩散", "不确定"],
            "options_en": ["Just noticed, no expansion yet", "Slowly increasing", "Clearly increased in recent days", "Rapidly spread within one or two days", "Unknown"],
        },
        {
            "key": "affected_plants",
            "type": "single",
            "required": True,
            "label_zh": "目前有多少植株出现类似症状？",
            "label_en": "How many plants currently show similar symptoms?",
            "options_zh": ["只有一株", "少量植株", "多株植株", "大面积出现", "不确定"],
            "options_en": ["Only one plant", "A small number of plants", "Multiple plants", "Large area affected", "Unknown"],
        },
        {
            "key": "functional_damage",
            "type": "multiple",
            "required": False,
            "label_zh": "是否出现以下严重症状？可多选",
            "label_en": "Are any of the following serious symptoms present?",
            "options_zh": ["明显萎蔫", "大量落叶", "果实受损", "茎部或根部受损", "植株停止生长", "暂无以上情况"],
            "options_en": ["Obvious wilting", "Heavy leaf drop", "Fruit damage", "Stem or root damage", "Plant stopped growing", "None of the above"],
        },
        {
            "key": "growth_stage",
            "type": "single",
            "required": False,
            "label_zh": "植株目前处于哪个阶段？",
            "label_en": "What growth stage is the plant currently in?",
            "options_zh": ["幼苗期", "生长期", "开花期", "结果期", "成熟期", "不确定"],
            "options_en": ["Seedling", "Vegetative growth", "Flowering", "Fruiting", "Maturity", "Unknown"],
        },
        {
            "key": "treatment",
            "type": "single",
            "required": False,
            "label_zh": "是否采取过处理措施？",
            "label_en": "Have any treatment measures been taken?",
            "options_zh": ["尚未处理", "已去除病叶", "已使用药剂", "已隔离植株", "处理过但仍在扩散"],
            "options_en": ["Not treated yet", "Diseased leaves removed", "Pesticide applied", "Plant isolated", "Treated but still spreading"],
        },
        {
            "key": "additional_notes",
            "type": "text",
            "required": False,
            "label_zh": "其他需要补充的情况",
            "label_en": "Additional notes",
            "options_zh": [],
            "options_en": [],
        },
    ]

    @staticmethod
    def get_severity_questions(display_language: str = "zh") -> dict:
        """返回前端可直接渲染的严重程度问卷配置，避免问题和评分规则前后端脱节。"""
        language = (display_language or "zh").lower()
        questions = []
        for item in HistoryService.QUESTION_DEFINITIONS:
            is_zh = language == "zh"
            questions.append(
                {
                    "key": item["key"],
                    "type": item["type"],
                    "required": item["required"],
                    "label": item["label_zh"] if is_zh else item["label_en"],
                    "options": item["options_zh"] if is_zh else item["options_en"],
                    "allow_unknown": item["type"] != "text",
                }
            )
        return {
            "questions": questions,
            "submit_endpoint": "/api/history/tasks/{task_id}/severity-assessment",
            "minimum_known_answers": 3,
        }

    @staticmethod
    def _parse_date(value: str | None, end_of_day: bool = False) -> datetime | None:
        """解析查询参数日期；非法日期不打断历史列表查询。"""
        if not value:
            return None
        try:
            parsed = datetime.strptime(value, "%Y-%m-%d")
        except ValueError:
            return None
        if end_of_day:
            return parsed.replace(hour=23, minute=59, second=59)
        return parsed

    @staticmethod
    def _is_unknown_answer(value) -> bool:
        """识别问卷中的“不确定/未填写”，避免信息不足时硬给风险等级。"""
        if value is None:
            return True
        if isinstance(value, str):
            return value.strip().lower() in {"", "不确定", "uncertain", "unknown"}
        if isinstance(value, list):
            return not value or all(HistoryService._is_unknown_answer(item) for item in value)
        return False

    @staticmethod
    def _configured_llm_model() -> str | None:
        """返回可用 LLM 模型名；测试占位 Key 不触发外部调用。"""
        qwen_key = getattr(settings, "QWEN_API_KEY", "").strip()
        qwen_model = getattr(settings, "QWEN_MODEL", "qwen3.7-plus")
        if qwen_key and qwen_key != "sk-your-qwen-api-key" and qwen_key != "test":
            return qwen_model

        openai_key = getattr(settings, "OPENAI_API_KEY", "").strip()
        openai_model = getattr(settings, "OPENAI_MODEL", "gpt-4o-mini")
        invalid_openai_keys = {"", "test", "sk-your-api-key-here"}
        if openai_key not in invalid_openai_keys:
            return openai_model
        return None

    @staticmethod
    def _extract_llm_json(response) -> dict | None:
        """从 LLM 响应中提取 JSON 对象，兼容 ```json 代码块。"""
        content = getattr(response, "content", response)
        if not isinstance(content, str):
            content = str(content)
        content = content.strip()
        if content.startswith("```"):
            content = re.sub(r"^```(?:json)?\s*", "", content)
            content = re.sub(r"\s*```$", "", content).strip()
        match = HistoryService.LLM_RESPONSE_PATTERN.search(content)
        if not match:
            return None
        try:
            payload = json.loads(match.group(0))
        except json.JSONDecodeError:
            return None
        return payload if isinstance(payload, dict) else None

    @staticmethod
    def _invoke_llm_json(prompt: str) -> tuple[dict | None, str | None]:
        """调用项目现有 LLM，要求返回 JSON；不可用或失败时返回空结果。"""
        model_name = HistoryService._configured_llm_model()
        if not model_name:
            return None, None
        try:
            from app.agent.base_agent import create_llm

            response = create_llm().invoke(prompt)
            return HistoryService._extract_llm_json(response), model_name
        except Exception as exc:
            logger.warning("历史风险 LLM 增强失败，已回退规则结果: %s", exc)
            return None, None

    @staticmethod
    def _merge_risk_level(rule_level: str, llm_level: str | None) -> str:
        """LLM 最多只能在规则等级基础上上下调整一级，避免极端跳变。"""
        if rule_level not in HistoryService.CORE_RISK_LEVELS:
            return rule_level
        if llm_level not in HistoryService.CORE_RISK_LEVELS:
            return rule_level
        rule_index = HistoryService.CORE_RISK_LEVELS.index(rule_level)
        llm_index = HistoryService.CORE_RISK_LEVELS.index(llm_level)
        bounded_index = max(rule_index - 1, min(rule_index + 1, llm_index))
        return HistoryService.CORE_RISK_LEVELS[bounded_index]

    @staticmethod
    def _clean_text_list(value, fallback: list[str], max_items: int = 6) -> list[str]:
        """清洗 LLM 返回的字符串列表，空结果使用规则建议兜底。"""
        if not isinstance(value, list):
            return fallback
        items = [str(item).strip() for item in value if str(item).strip()]
        return items[:max_items] if items else fallback

    @staticmethod
    def _format_result(result: DetectionResult, display_language: str, class_names_cn: dict | None = None) -> dict:
        """统一格式化单条检测结果，补充类别、植物和病害显示字段。"""
        display_info = DetectionConfig.class_display_info(
            result.class_name,
            class_names_cn=class_names_cn,
            display_language=display_language,
        )
        return {
            "id": result.id,
            **display_info,
            "class_name_cn": result.class_name_cn,
            "class_id": result.class_id,
            "confidence": round(result.confidence, 4),
            "bbox": result.bbox,
            "image_path": result.image_path,
            "annotated_image_url": result.annotated_image_url,
            "inference_time": round(result.inference_time, 2)
            if result.inference_time
            else None,
        }

    @staticmethod
    def _format_assessment(
        assessment: SeverityAssessment,
        task: DetectionTask,
        display_language: str,
    ) -> dict:
        """统一格式化严重程度评估，供详情、报告和前端补填状态判断复用。"""
        class_info = DetectionConfig.class_display_info(
            assessment.class_name,
            class_names_cn=task.scene.class_names_cn if task.scene else None,
            display_language=display_language,
        )
        return {
            "id": assessment.id,
            "task_id": assessment.task_id,
            "class_name": assessment.class_name,
            "class_name_display": class_info["class_name_display"],
            "risk_level": assessment.risk_level,
            "assessment_confidence": assessment.assessment_confidence,
            "summary": assessment.summary,
            "reasons": assessment.reasons or [],
            "uncertainties": assessment.uncertainties or [],
            "recommended_actions": assessment.recommended_actions or [],
            "answers": assessment.answers or {},
            "llm_model": assessment.llm_model,
            "created_at": assessment.created_at.isoformat()
            if assessment.created_at
            else None,
            "updated_at": assessment.updated_at.isoformat()
            if assessment.updated_at
            else None,
        }

    @staticmethod
    def _task_summary_fields(
        task: DetectionTask,
        results: list[DetectionResult],
        display_language: str,
    ) -> dict:
        """从任务检测结果中聚合历史列表需要直接展示的主要信息。"""
        class_names_cn = task.scene.class_names_cn if task.scene else None
        class_counts = {}
        class_counts_display = {}
        annotated_image_url = None
        primary = None

        for result in results:
            class_counts[result.class_name] = class_counts.get(result.class_name, 0) + 1
            display_info = DetectionConfig.class_display_info(
                result.class_name,
                class_names_cn=class_names_cn,
                display_language=display_language,
            )
            display_name = display_info["class_name_display"]
            class_counts_display[display_name] = class_counts_display.get(display_name, 0) + 1
            if not annotated_image_url and result.annotated_image_url:
                annotated_image_url = result.annotated_image_url
            if primary is None or result.confidence > primary.confidence:
                primary = result

        primary_info = (
            DetectionConfig.class_display_info(
                primary.class_name,
                class_names_cn=class_names_cn,
                display_language=display_language,
            )
            if primary
            else {}
        )

        return {
            "primary_class_name": primary.class_name if primary else None,
            "primary_class_name_display": primary_info.get("class_name_display"),
            "plant_name": primary_info.get("plant_name"),
            "plant_name_display": primary_info.get("plant_name_display"),
            "disease_name": primary_info.get("disease_name"),
            "disease_name_display": primary_info.get("disease_name_display"),
            "max_confidence": round(primary.confidence, 4) if primary else None,
            "class_counts": class_counts,
            "class_counts_display": class_counts_display,
            "annotated_image_url": annotated_image_url,
        }

    @staticmethod
    def list_tasks(
        user_id: int,
        page: int = 1,
        page_size: int = 10,
        task_type: Optional[str] = None,
        status: Optional[str] = None,
        scene_id: Optional[int] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        keyword: Optional[str] = None,
        risk_level: Optional[str] = None,
        treatment_status: Optional[str] = None,
        plant_name: Optional[str] = None,
        class_name: Optional[str] = None,
        display_language: str = "zh",
    ) -> dict:
        """
        分页查询用户的检测任务列表

        Args:
            user_id: 用户 ID
            page: 页码（从 1 开始）
            page_size: 每页数量
            task_type: 任务类型筛选
            status: 状态筛选
            scene_id: 场景 ID 筛选
            start_date: 起始日期（YYYY-MM-DD）
            end_date: 结束日期（YYYY-MM-DD）
            keyword: 任务、场景和检测类别关键词
            risk_level: 严重程度筛选
            treatment_status: 治疗状态筛选
            plant_name: 植物名称筛选（支持中英文）
            class_name: 检测类别筛选
            display_language: 当前用户显示语言

        Returns:
            包含分页信息和任务列表的字典
        """
        db = SessionLocal()
        try:
            query = (
                db.query(DetectionTask)
                .options(joinedload(DetectionTask.scene))
                .outerjoin(DetectionScene, DetectionTask.scene_id == DetectionScene.id)
                .outerjoin(DetectionResult, DetectionResult.task_id == DetectionTask.id)
                .filter(DetectionTask.user_id == user_id)
            )

            if task_type:
                query = query.filter(DetectionTask.task_type == task_type)
            if status:
                query = query.filter(DetectionTask.status == status)
            if scene_id:
                query = query.filter(DetectionTask.scene_id == scene_id)
            if risk_level:
                query = query.filter(DetectionTask.risk_level == risk_level)
            if treatment_status:
                query = query.filter(DetectionTask.treatment_status == treatment_status)
            parsed_start = HistoryService._parse_date(start_date)
            parsed_end = HistoryService._parse_date(end_date, end_of_day=True)
            if parsed_start:
                query = query.filter(DetectionTask.created_at >= parsed_start)
            if parsed_end:
                query = query.filter(DetectionTask.created_at <= parsed_end)
            if class_name:
                query = query.filter(DetectionResult.class_name.ilike(f"%{class_name}%"))
            if plant_name:
                plant_classes = DetectionConfig.class_names_for_plant(plant_name)
                query = (
                    query.filter(DetectionResult.class_name.in_(plant_classes))
                    if plant_classes
                    else query.filter(false())
                )
            if keyword:
                keyword_like = f"%{keyword.strip()}%"
                keyword_filters = [
                    DetectionResult.class_name.ilike(keyword_like),
                    DetectionResult.class_name_cn.ilike(keyword_like),
                    DetectionScene.name.ilike(keyword_like),
                    DetectionScene.display_name.ilike(keyword_like),
                ]
                if keyword.strip().isdigit():
                    keyword_filters.append(DetectionTask.id == int(keyword.strip()))
                query = query.filter(or_(*keyword_filters))

            total = query.with_entities(
                func.count(func.distinct(DetectionTask.id))
            ).scalar()
            total_pages = (total + page_size - 1) // page_size

            task_id_rows = (
                query.with_entities(DetectionTask.id, DetectionTask.created_at)
                .group_by(DetectionTask.id, DetectionTask.created_at)
                .order_by(desc(DetectionTask.created_at))
                .offset((page - 1) * page_size)
                .limit(page_size)
                .all()
            )
            task_ids = [row.id for row in task_id_rows]
            tasks = []
            if task_ids:
                tasks = (
                    db.query(DetectionTask)
                    .options(joinedload(DetectionTask.scene))
                    .filter(DetectionTask.id.in_(task_ids))
                    .order_by(desc(DetectionTask.created_at))
                    .all()
                )

            results_by_task: dict[int, list[DetectionResult]] = {task_id: [] for task_id in task_ids}
            if task_ids:
                page_results = (
                    db.query(DetectionResult)
                    .filter(DetectionResult.task_id.in_(task_ids))
                    .order_by(DetectionResult.confidence.desc())
                    .all()
                )
                for result in page_results:
                    results_by_task.setdefault(result.task_id, []).append(result)

            items = []
            for task in tasks:
                scene_name = task.scene.display_name if task.scene else None
                summary = HistoryService._task_summary_fields(
                    task,
                    results_by_task.get(task.id, []),
                    display_language,
                )
                items.append(
                    {
                        "id": task.id,
                        "task_type": task.task_type,
                        "status": task.status,
                        "scene_id": task.scene_id,
                        "scene_name": scene_name,
                        "total_images": task.total_images or 0,
                        "total_objects": task.total_objects or 0,
                        "total_inference_time": round(
                            task.total_inference_time or 0, 2
                        ),
                        "conf_threshold": task.conf_threshold,
                        "error_message": task.error_message,
                        "risk_level": task.risk_level,
                        "analyzed_at": task.analyzed_at.isoformat()
                        if task.analyzed_at
                        else None,
                        "treatment_status": task.treatment_status,
                        "treatment_note": task.treatment_note,
                        "treatment_updated_at": task.treatment_updated_at.isoformat()
                        if task.treatment_updated_at
                        else None,
                        "latitude": task.latitude,
                        "longitude": task.longitude,
                        "location_name": task.location_name,
                        "environment_risk_level": task.environment_risk_level,
                        "weather_summary": task.weather_summary,
                        "weather_updated_at": task.weather_updated_at.isoformat()
                        if task.weather_updated_at
                        else None,
                        **summary,
                        "created_at": task.created_at.isoformat()
                        if task.created_at
                        else None,
                        "completed_at": task.completed_at.isoformat()
                        if task.completed_at
                        else None,
                    }
                )

            return {
                "total": total,
                "page": page,
                "page_size": page_size,
                "total_pages": total_pages,
                "items": items,
            }
        finally:
            db.close()

    @staticmethod
    def get_task_detail(
        user_id: int, task_id: int, display_language: str = "zh"
    ) -> Optional[dict]:
        """
        获取检测任务详情，包含完整的结果列表

        Args:
            user_id: 用户 ID
            task_id: 任务 ID

        Returns:
            任务详情字典，如果任务不存在或无权访问则返回 None
        """
        db = SessionLocal()
        try:
            task = (
                db.query(DetectionTask)
                .options(joinedload(DetectionTask.scene))
                .filter(DetectionTask.id == task_id, DetectionTask.user_id == user_id)
                .first()
            )

            if not task:
                return None

            results = (
                db.query(DetectionResult)
                .filter(DetectionResult.task_id == task_id)
                .all()
            )

            class_counts = {}
            class_counts_display = {}
            class_names_cn = task.scene.class_names_cn if task.scene else None
            for r in results:
                class_counts[r.class_name] = class_counts.get(r.class_name, 0) + 1
                display_name = DetectionConfig.class_display_info(
                    r.class_name,
                    class_names_cn=class_names_cn,
                    display_language=display_language,
                )["class_name_display"]
                class_counts_display[display_name] = class_counts_display.get(display_name, 0) + 1

            result_items = [
                HistoryService._format_result(r, display_language, class_names_cn)
                for r in results
            ]
            assessments = (
                db.query(SeverityAssessment)
                .filter(SeverityAssessment.task_id == task_id)
                .order_by(SeverityAssessment.updated_at.desc())
                .all()
            )
            assessment_items = [
                HistoryService._format_assessment(a, task, display_language)
                for a in assessments
            ]

            return {
                "task": {
                    "id": task.id,
                    "task_type": task.task_type,
                    "status": task.status,
                    "scene_id": task.scene_id,
                    "scene_name": task.scene.display_name if task.scene else None,
                    "total_images": task.total_images or 0,
                    "total_objects": task.total_objects or 0,
                    "total_inference_time": round(task.total_inference_time or 0, 2),
                    "conf_threshold": task.conf_threshold,
                    "iou_threshold": task.iou_threshold,
                    "error_message": task.error_message,
                    "risk_level": task.risk_level,
                    "analysis_report": task.analysis_report,
                    "analysis_suggestion": task.analysis_suggestion,
                    "analyzed_at": task.analyzed_at.isoformat()
                    if task.analyzed_at
                    else None,
                    "treatment_status": task.treatment_status,
                    "treatment_note": task.treatment_note,
                    "treatment_updated_at": task.treatment_updated_at.isoformat()
                    if task.treatment_updated_at
                    else None,
                    "latitude": task.latitude,
                    "longitude": task.longitude,
                    "location_name": task.location_name,
                    "location_source": task.location_source,
                    "location_updated_at": task.location_updated_at.isoformat()
                    if task.location_updated_at
                    else None,
                    "environment_risk_level": task.environment_risk_level,
                    "weather_summary": task.weather_summary,
                    "weather_recommendations": task.weather_recommendations or [],
                    "weather_snapshot": task.weather_snapshot or {},
                    "weather_updated_at": task.weather_updated_at.isoformat()
                    if task.weather_updated_at
                    else None,
                    "created_at": task.created_at.isoformat()
                    if task.created_at
                    else None,
                    "completed_at": task.completed_at.isoformat()
                    if task.completed_at
                    else None,
                },
                "class_counts": class_counts,
                "class_counts_display": class_counts_display,
                "severity_assessments": assessment_items,
                "results": result_items,
            }
        finally:
            db.close()

    @staticmethod
    def _score_severity(answers: dict, result_count: int) -> dict:
        """
        用可解释规则评估严重程度。

        YOLO 置信度只代表模型分类把握，不代表病害严重程度；这里仅使用目标数量作为背景因素。
        """
        known_answers = [
            key
            for key in [
                "affected_area",
                "spread_speed",
                "affected_plants",
                "functional_damage",
                "growth_stage",
                "treatment",
            ]
            if not HistoryService._is_unknown_answer(answers.get(key))
        ]
        if len(known_answers) < 3:
            payload = {
                "risk_level": "insufficient_information",
                "assessment_confidence": "low",
                "summary": "当前问卷信息不足，无法可靠判断病害严重程度。",
                "reasons": ["受害范围、传播速度、受影响植株等关键信息不足。"],
                "uncertainties": ["请补充至少 3 项问卷信息后重新评估。"],
                "recommended_actions": ["先隔离疑似病株并持续观察，补充现场信息后再制定处理方案。"],
            }
            return SeverityAssessmentResult(**payload).model_dump()

        score = 0
        reasons = []
        uncertainties = []

        affected_area = str(answers.get("affected_area", ""))
        if "超过 60" in affected_area or ">60" in affected_area:
            score += 3
            reasons.append("受害范围超过 60%，说明病害影响面较大。")
        elif "30" in affected_area and "60" in affected_area:
            score += 2
            reasons.append("受害范围达到 30%-60%，需要尽快处理。")
        elif "10" in affected_area and "30" in affected_area:
            score += 1
            reasons.append("受害范围在 10%-30%，存在继续扩展风险。")

        spread_speed = str(answers.get("spread_speed", ""))
        if "一两天" in spread_speed or "快速" in spread_speed:
            score += 3
            reasons.append("病害在一两天内快速扩散。")
        elif "明显增加" in spread_speed or "recent" in spread_speed.lower():
            score += 2
            reasons.append("最近几天症状明显增加。")
        elif "缓慢" in spread_speed or "slow" in spread_speed.lower():
            score += 1
            reasons.append("症状仍在缓慢增加。")

        affected_plants = str(answers.get("affected_plants", ""))
        if "大面积" in affected_plants or "large" in affected_plants.lower():
            score += 3
            reasons.append("类似症状已经大面积出现。")
        elif "多株" in affected_plants or "multiple" in affected_plants.lower():
            score += 2
            reasons.append("已有多株植株受影响。")
        elif "少量" in affected_plants or "少数" in affected_plants:
            score += 1
            reasons.append("已有少量植株受影响。")

        damage = answers.get("functional_damage") or []
        if isinstance(damage, str):
            damage = [damage]
        severe_damage = {"茎部或根部受损", "植株停止生长"}
        notable_damage = {"明显萎蔫", "大量落叶", "果实受损"}
        if any(item in severe_damage for item in damage):
            score += 3
            reasons.append("已出现茎根受损或停止生长等严重功能损害。")
        elif any(item in notable_damage for item in damage):
            score += 2
            reasons.append("已出现萎蔫、落叶或果实受损等明显功能损害。")

        growth_stage = str(answers.get("growth_stage", ""))
        if growth_stage in {"幼苗期", "开花期", "结果期"}:
            score += 1
            reasons.append(f"病害发生在{growth_stage}，对产量或生长影响更敏感。")

        treatment = str(answers.get("treatment", ""))
        if "处理过但仍在扩散" in treatment:
            score += 2
            reasons.append("已处理但仍在扩散，说明现有措施可能不足。")
        elif "尚未处理" in treatment:
            score += 1
            reasons.append("尚未采取处理措施。")

        if result_count >= 10:
            score += 1
            reasons.append("该类别在本次检测中出现较多目标，建议提高巡查密度。")

        if score >= 12:
            risk_level = "critical"
        elif score >= 7:
            risk_level = "high"
        elif score >= 3:
            risk_level = "moderate"
        else:
            risk_level = "low"

        confidence = "high" if len(known_answers) >= 5 else "medium"
        risk_text = {
            "low": "当前信息显示病害风险较低，建议继续观察并做好基础防护。",
            "moderate": "当前病害为中等风险，需要及时处理并持续观察变化。",
            "high": "当前病害风险较高，建议尽快采取防治措施并扩大巡查范围。",
            "critical": "当前病害风险严重，建议立即处理并评估是否需要区域性防控。",
        }[risk_level]

        for key in ["affected_area", "spread_speed", "affected_plants"]:
            if HistoryService._is_unknown_answer(answers.get(key)):
                uncertainties.append(f"{key} 信息不明确。")

        actions = [
            "复核同类症状植株，记录病害扩散速度和受害比例。",
            "移除或隔离严重病叶/病株，减少传播源。",
            "结合当地农技建议选择合适药剂或绿色防控措施。",
        ]
        if risk_level in {"high", "critical"}:
            actions.insert(0, "优先处理高风险区域，并在 24-48 小时内复查。")

        payload = {
            "risk_level": risk_level,
            "assessment_confidence": confidence,
            "summary": risk_text,
            "reasons": reasons or ["当前未发现明显高危信号。"],
            "uncertainties": uncertainties,
            "recommended_actions": actions,
        }
        return SeverityAssessmentResult(**payload).model_dump()

    @staticmethod
    def _enhance_severity_with_llm(
        rule_result: dict,
        class_name: str,
        answers: dict,
        result_count: int,
    ) -> tuple[dict, str]:
        """用 LLM 增强严重程度评估；失败时返回规则结果。"""
        if rule_result.get("risk_level") == "insufficient_information":
            return rule_result, "rule-based"

        prompt = f"""
你是果蔬病虫害风险评估助手。请基于检测结果、用户问卷和规则评分，输出更贴近现场的严重程度评估。

要求：
1. 只返回一个 JSON 对象，不要 Markdown，不要额外解释。
2. risk_level 只能是 low、moderate、high、critical。
3. assessment_confidence 只能是 low、medium、high。
4. risk_level 应尊重规则评分，除非问卷信息明显支持调整。
5. summary、reasons、uncertainties、recommended_actions 用中文，建议具体、可执行。

输入：
{json.dumps({
    "class_name": class_name,
    "detected_object_count": result_count,
    "answers": answers,
    "rule_result": rule_result,
}, ensure_ascii=False)}

返回 JSON 格式：
{{
  "risk_level": "high",
  "assessment_confidence": "high",
  "summary": "一句话评估摘要",
  "reasons": ["原因1", "原因2"],
  "uncertainties": ["仍不确定的信息"],
  "recommended_actions": ["建议1", "建议2"]
}}
"""
        llm_payload, model_name = HistoryService._invoke_llm_json(prompt)
        if not llm_payload:
            return rule_result, "rule-based"

        merged_payload = {
            "risk_level": HistoryService._merge_risk_level(
                rule_result["risk_level"],
                str(llm_payload.get("risk_level", "")).strip(),
            ),
            "assessment_confidence": str(
                llm_payload.get(
                    "assessment_confidence",
                    rule_result["assessment_confidence"],
                )
            ).strip(),
            "summary": str(llm_payload.get("summary") or rule_result["summary"]).strip(),
            "reasons": HistoryService._clean_text_list(
                llm_payload.get("reasons"),
                rule_result["reasons"],
            ),
            "uncertainties": HistoryService._clean_text_list(
                llm_payload.get("uncertainties"),
                rule_result["uncertainties"],
            ),
            "recommended_actions": HistoryService._clean_text_list(
                llm_payload.get("recommended_actions"),
                rule_result["recommended_actions"],
            ),
        }
        if merged_payload["assessment_confidence"] not in {"low", "medium", "high"}:
            merged_payload["assessment_confidence"] = rule_result["assessment_confidence"]
        try:
            return SeverityAssessmentResult(**merged_payload).model_dump(), (
                model_name or "rule-based"
            )
        except Exception as exc:
            logger.warning("LLM 严重程度结果结构无效，已回退规则结果: %s", exc)
            return rule_result, "rule-based"

    @staticmethod
    def create_severity_assessment(
        user_id: int,
        task_id: int,
        class_name: str,
        answers: dict,
        additional_notes: str | None = None,
        display_language: str = "zh",
    ) -> dict | None:
        """创建或更新当前用户某个检测任务、某个类别的严重程度评估。"""
        db = SessionLocal()
        try:
            task = (
                db.query(DetectionTask)
                .options(joinedload(DetectionTask.scene))
                .filter(DetectionTask.id == task_id, DetectionTask.user_id == user_id)
                .first()
            )
            if not task:
                return None

            results = (
                db.query(DetectionResult)
                .filter(
                    DetectionResult.task_id == task_id,
                    DetectionResult.class_name == class_name,
                )
                .all()
            )
            if not results:
                return {"error": "该任务中没有指定类别的检测结果", "status_code": 400}

            assessment_answers = dict(answers or {})
            if additional_notes:
                assessment_answers["additional_notes"] = additional_notes
            scored = HistoryService._score_severity(assessment_answers, len(results))
            scored, scored_model = HistoryService._enhance_severity_with_llm(
                scored,
                class_name=class_name,
                answers=assessment_answers,
                result_count=len(results),
            )

            assessment = (
                db.query(SeverityAssessment)
                .filter(
                    SeverityAssessment.task_id == task_id,
                    SeverityAssessment.class_name == class_name,
                )
                .first()
            )
            if assessment is None:
                assessment = SeverityAssessment(task_id=task_id, class_name=class_name)
                db.add(assessment)

            assessment.answers = assessment_answers
            assessment.risk_level = scored["risk_level"]
            assessment.assessment_confidence = scored["assessment_confidence"]
            assessment.summary = scored["summary"]
            assessment.reasons = scored["reasons"]
            assessment.uncertainties = scored["uncertainties"]
            assessment.recommended_actions = scored["recommended_actions"]
            assessment.llm_model = scored_model
            assessment.updated_at = datetime.now()

            task.risk_level = assessment.risk_level
            task.analysis_report = assessment.summary
            task.analysis_suggestion = "\n".join(assessment.recommended_actions)
            task.analyzed_at = datetime.now()

            db.commit()
            db.refresh(assessment)

            class_info = DetectionConfig.class_display_info(
                class_name,
                class_names_cn=task.scene.class_names_cn if task.scene else None,
                display_language=display_language,
            )
            return {
                "id": assessment.id,
                "task_id": task_id,
                "class_name": class_name,
                "class_name_display": class_info["class_name_display"],
                "risk_level": assessment.risk_level,
                "assessment_confidence": assessment.assessment_confidence,
                "summary": assessment.summary,
                "reasons": assessment.reasons or [],
                "uncertainties": assessment.uncertainties or [],
                "recommended_actions": assessment.recommended_actions or [],
                "llm_model": assessment.llm_model or "rule-based",
                "created_at": assessment.created_at.isoformat()
                if assessment.created_at
                else None,
            }
        finally:
            db.close()

    @staticmethod
    def update_treatment_status(
        user_id: int, task_id: int, status: str, note: str | None = None
    ) -> dict | None:
        """更新当前用户自己的检测任务治疗状态。"""
        db = SessionLocal()
        try:
            task = (
                db.query(DetectionTask)
                .filter(DetectionTask.id == task_id, DetectionTask.user_id == user_id)
                .first()
            )
            if not task:
                return None

            task.treatment_status = status
            task.treatment_note = note
            task.treatment_updated_at = datetime.now()
            db.commit()
            db.refresh(task)
            return {
                "task_id": task.id,
                "treatment_status": task.treatment_status,
                "treatment_note": task.treatment_note,
                "treatment_updated_at": task.treatment_updated_at.isoformat()
                if task.treatment_updated_at
                else None,
            }
        finally:
            db.close()

    @staticmethod
    def update_task_location(
        user_id: int,
        task_id: int,
        latitude: float,
        longitude: float,
        location_name: str | None = None,
        location_source: str = "manual",
    ) -> dict | None:
        """保存检测任务位置；位置必须来自前端授权、EXIF 或用户手动输入。"""
        db = SessionLocal()
        try:
            task = (
                db.query(DetectionTask)
                .filter(DetectionTask.id == task_id, DetectionTask.user_id == user_id)
                .first()
            )
            if not task:
                return None

            task.latitude = latitude
            task.longitude = longitude
            task.location_name = location_name
            task.location_source = location_source
            task.location_updated_at = datetime.now()
            db.commit()
            db.refresh(task)
            return {
                "task_id": task.id,
                "latitude": task.latitude,
                "longitude": task.longitude,
                "location_name": task.location_name,
                "location_source": task.location_source,
                "location_updated_at": task.location_updated_at.isoformat()
                if task.location_updated_at
                else None,
            }
        finally:
            db.close()

    @staticmethod
    def _average(values: list) -> float | None:
        """计算天气数组平均值，忽略接口可能返回的 None。"""
        numbers = [float(value) for value in values if value is not None]
        return round(sum(numbers) / len(numbers), 2) if numbers else None

    @staticmethod
    def _fetch_weather(latitude: float, longitude: float) -> dict:
        """调用 Open-Meteo 获取未来 3 天天气；该接口无需 API Key。"""
        response = httpx.get(
            HistoryService.WEATHER_FORECAST_URL,
            params={
                "latitude": latitude,
                "longitude": longitude,
                "hourly": "temperature_2m,relative_humidity_2m,precipitation,precipitation_probability",
                "daily": "precipitation_sum,temperature_2m_max,temperature_2m_min",
                "forecast_days": 3,
                "timezone": "auto",
            },
            timeout=10,
        )
        response.raise_for_status()
        return response.json()

    @staticmethod
    def _weather_metrics(snapshot: dict) -> dict:
        """从天气接口原始快照里提取风险评估需要的稳定指标。"""
        hourly = snapshot.get("hourly") or {}
        daily = snapshot.get("daily") or {}
        humidity = hourly.get("relative_humidity_2m") or []
        precipitation = hourly.get("precipitation") or []
        precipitation_probability = hourly.get("precipitation_probability") or []
        temperature = hourly.get("temperature_2m") or []
        daily_precipitation = daily.get("precipitation_sum") or []

        return {
            "avg_humidity": HistoryService._average(humidity[:72]),
            "avg_temperature": HistoryService._average(temperature[:72]),
            "max_precipitation_probability": max(precipitation_probability[:72])
            if precipitation_probability
            else None,
            "total_precipitation": round(
                sum(float(value) for value in precipitation[:72] if value is not None),
                2,
            ),
            "daily_precipitation_sum": daily_precipitation,
        }

    @staticmethod
    def _enhance_weather_risk_with_llm(
        rule_risk: dict,
        task: DetectionTask,
        results: list[DetectionResult],
    ) -> dict:
        """用 LLM 增强天气风险分析；失败时返回规则结果。"""
        if rule_risk.get("environment_risk_level") == "unavailable":
            return rule_risk

        detection_summary = {}
        for result in results:
            detection_summary[result.class_name] = (
                detection_summary.get(result.class_name, 0) + 1
            )

        prompt = f"""
你是果蔬病虫害环境风险分析助手。请基于天气指标、检测类别、问卷严重程度和规则评分，输出未来 3 天病害扩散环境风险。

要求：
1. 只返回一个 JSON 对象，不要 Markdown，不要额外解释。
2. environment_risk_level 只能是 low、moderate、high、critical。
3. environment_risk_level 应尊重规则评分，除非检测类别或已有问卷严重程度明显支持调整。
4. summary 和 recommendations 用中文，建议应具体、可执行，避免泛泛而谈。

输入：
{json.dumps({
    "detection_summary": detection_summary,
    "task_risk_level_from_questionnaire": task.risk_level,
    "weather_metrics": rule_risk.get("weather_metrics", {}),
    "rule_environment_risk_level": rule_risk.get("environment_risk_level"),
    "rule_summary": rule_risk.get("weather_summary"),
    "rule_recommendations": rule_risk.get("weather_recommendations", []),
    "rule_reasons": rule_risk.get("reasons", []),
}, ensure_ascii=False)}

返回 JSON 格式：
{{
  "environment_risk_level": "high",
  "summary": "一句话天气风险摘要",
  "recommendations": ["建议1", "建议2"],
  "reasons": ["判断依据1", "判断依据2"]
}}
"""
        llm_payload, model_name = HistoryService._invoke_llm_json(prompt)
        if not llm_payload:
            return rule_risk

        enhanced = dict(rule_risk)
        enhanced["environment_risk_level"] = HistoryService._merge_risk_level(
            rule_risk["environment_risk_level"],
            str(llm_payload.get("environment_risk_level", "")).strip(),
        )
        summary = str(llm_payload.get("summary") or "").strip()
        if summary:
            enhanced["weather_summary"] = summary
        enhanced["weather_recommendations"] = HistoryService._clean_text_list(
            llm_payload.get("recommendations"),
            rule_risk["weather_recommendations"],
        )
        enhanced["reasons"] = HistoryService._clean_text_list(
            llm_payload.get("reasons"),
            rule_risk.get("reasons", []),
        )
        if model_name:
            enhanced["llm_model"] = model_name
        return enhanced

    @staticmethod
    def _score_weather_risk(
        task: DetectionTask,
        results: list[DetectionResult],
        weather_snapshot: dict | None,
        weather_error: str | None = None,
    ) -> dict:
        """按天气、病害类型和已有严重程度给出环境扩散风险，不覆盖问卷严重程度。"""
        if weather_error:
            return {
                "environment_risk_level": "unavailable",
                "weather_summary": f"天气数据暂不可用：{weather_error}",
                "weather_recommendations": ["请稍后重试天气风险分析，或根据现场湿度、降雨和病害扩散情况人工判断。"],
                "weather_metrics": {},
            }

        metrics = HistoryService._weather_metrics(weather_snapshot or {})
        score = 0
        reasons = []
        recommendations = []
        class_names = {result.class_name.lower() for result in results}
        disease_text = " ".join(class_names)

        humidity = metrics["avg_humidity"]
        if humidity is not None and humidity >= 85:
            score += 2
            reasons.append("未来 3 天平均湿度较高，叶部病害扩散风险上升。")
            recommendations.append("加强通风降湿，避免傍晚或夜间浇水造成叶面长时间潮湿。")
        elif humidity is not None and humidity >= 75:
            score += 1
            reasons.append("未来 3 天湿度偏高，需要持续观察病斑变化。")

        precipitation = metrics["total_precipitation"] or 0
        precipitation_probability = metrics["max_precipitation_probability"]
        if precipitation >= 20:
            score += 3
            reasons.append("未来 3 天累计降雨量较高，可能促进病害传播。")
            recommendations.append("雨前雨后重点巡查叶片背面、近地叶片和密植区域。")
        elif precipitation >= 5 or (precipitation_probability is not None and precipitation_probability >= 60):
            score += 2
            reasons.append("未来 3 天存在明显降雨概率，需防范湿度升高后的扩散。")

        temperature = metrics["avg_temperature"]
        if temperature is not None and 15 <= temperature <= 30:
            score += 1
            reasons.append("未来温度处于多种叶部病害适宜活动区间。")

        if any(keyword in disease_text for keyword in ["late blight", "mildew", "leaf spot", "blight", "rot"]):
            score += 1
            reasons.append("当前检测类别属于易受湿度和降雨影响的叶部病害。")

        if task.risk_level in {"high", "critical"}:
            score += 2
            reasons.append("当前问卷评估已为高风险，环境条件将进一步放大病害压力。")

        if score >= 8:
            environment_risk_level = "critical"
        elif score >= 5:
            environment_risk_level = "high"
        elif score >= 2:
            environment_risk_level = "moderate"
        else:
            environment_risk_level = "low"

        risk_text = {
            "low": "未来 3 天天气条件对病害扩散影响较小，可维持现有管理措施。",
            "moderate": "未来 3 天天气条件可能促进病害发展，建议加强监测频率。",
            "high": "未来 3 天天气条件利于病害扩散，建议采取预防性措施并密切观察。",
            "critical": "未来 3 天天气条件非常有利于病害爆发，建议立即采取防控措施。",
        }[environment_risk_level]

        if environment_risk_level in {"high", "critical"}:
            recommendations.insert(0, "建议在未来 24-48 小时内复查病害发展情况。")

        return {
            "environment_risk_level": environment_risk_level,
            "weather_summary": risk_text,
            "weather_recommendations": recommendations or ["建议继续观察天气变化和病害发展趋势。"],
            "weather_metrics": metrics,
            "reasons": reasons or ["当前未发现明显环境风险信号。"],
        }

    @staticmethod
    def refresh_weather_risk(user_id: int, task_id: int) -> dict | None:
        """刷新检测任务的天气环境风险评估。"""
        db = SessionLocal()
        try:
            task = (
                db.query(DetectionTask)
                .filter(DetectionTask.id == task_id, DetectionTask.user_id == user_id)
                .first()
            )
            if not task:
                return None

            if task.latitude is None or task.longitude is None:
                return {"error": "请先设置检测任务的地理位置", "status_code": 400}

            results = (
                db.query(DetectionResult)
                .filter(DetectionResult.task_id == task_id)
                .all()
            )

            weather_error = None
            weather_snapshot = None
            try:
                weather_snapshot = HistoryService._fetch_weather(task.latitude, task.longitude)
            except Exception as exc:
                weather_error = str(exc)

            scored = HistoryService._score_weather_risk(task, results, weather_snapshot, weather_error)
            if scored["environment_risk_level"] != "unavailable":
                scored = HistoryService._enhance_weather_risk_with_llm(scored, task, results)

            task.environment_risk_level = scored["environment_risk_level"]
            task.weather_summary = scored["weather_summary"]
            task.weather_recommendations = scored["weather_recommendations"]
            task.weather_snapshot = weather_snapshot
            task.weather_updated_at = datetime.now()
            db.commit()
            db.refresh(task)

            return {
                "task_id": task.id,
                "environment_risk_level": task.environment_risk_level,
                "weather_summary": task.weather_summary,
                "weather_recommendations": task.weather_recommendations or [],
                "weather_metrics": scored.get("weather_metrics"),
                "reasons": scored.get("reasons"),
                "weather_updated_at": task.weather_updated_at.isoformat()
                if task.weather_updated_at
                else None,
                "llm_model": scored.get("llm_model"),
            }
        finally:
            db.close()

    @staticmethod
    def _build_report_html(task: DetectionTask, results: list[DetectionResult], display_language: str) -> str:
        """生成检测报告 HTML 内容。"""
        class_names_cn = task.scene.class_names_cn if task.scene else None
        class_counts = {}
        for r in results:
            class_counts[r.class_name] = class_counts.get(r.class_name, 0) + 1

        report_title = "农作物病害检测报告" if display_language == "zh" else "Crop Disease Detection Report"
        summary_section = {
            "zh": {
                "title": "检测摘要",
                "task_id": f"任务编号: #{task.id}",
                "time": f"检测时间: {task.created_at.strftime('%Y-%m-%d %H:%M:%S')}" if task.created_at else "",
                "total_images": f"检测图像: {task.total_images or 0} 张",
                "total_objects": f"检测目标: {task.total_objects or 0} 个",
                "risk_level": f"风险等级: {task.risk_level or '未评估'}",
            },
            "en": {
                "title": "Detection Summary",
                "task_id": f"Task ID: #{task.id}",
                "time": f"Detection Time: {task.created_at.strftime('%Y-%m-%d %H:%M:%S')}" if task.created_at else "",
                "total_images": f"Images: {task.total_images or 0}",
                "total_objects": f"Objects: {task.total_objects or 0}",
                "risk_level": f"Risk Level: {task.risk_level or 'Not evaluated'}",
            },
        }[display_language]

        class_counts_html = ""
        for class_name, count in class_counts.items():
            display_name = DetectionConfig.class_display_info(
                class_name,
                class_names_cn=class_names_cn,
                display_language=display_language,
            )["class_name_display"]
            class_counts_html += f"<tr><td>{html.escape(display_name)}</td><td>{count}</td></tr>"

        results_html = ""
        for result in results:
            display_info = DetectionConfig.class_display_info(
                result.class_name,
                class_names_cn=class_names_cn,
                display_language=display_language,
            )
            bbox = result.bbox or []
            bbox_str = f"{bbox[0]:.1f}, {bbox[1]:.1f}, {bbox[2]:.1f}, {bbox[3]:.1f}" if len(bbox) == 4 else "-"
            results_html += f"""
<tr>
    <td>{html.escape(display_info.get("class_name_display", result.class_name))}</td>
    <td>{html.escape(display_info.get("disease_name_display", "-"))}</td>
    <td>{html.escape(display_info.get("plant_name_display", "-"))}</td>
    <td>{result.confidence:.4f}</td>
    <td>{bbox_str}</td>
</tr>"""

        html_content = f"""<!DOCTYPE html>
<html lang="{display_language}">
<head>
    <meta charset="UTF-8">
    <title>{report_title}</title>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; max-width: 800px; margin: 0 auto; padding: 40px 20px; }}
        h1 {{ text-align: center; color: #1a1a2e; }}
        .summary {{ background: #f8f9fa; padding: 20px; border-radius: 8px; margin-bottom: 30px; }}
        .summary h2 {{ color: #2c3e50; margin-top: 0; }}
        .summary p {{ margin: 8px 0; color: #4a4a4a; }}
        table {{ width: 100%; border-collapse: collapse; margin-bottom: 30px; }}
        th, td {{ border: 1px solid #dee2e6; padding: 12px; text-align: left; }}
        th {{ background: #e9ecef; font-weight: 600; }}
        .footer {{ text-align: center; color: #888; margin-top: 40px; }}
    </style>
</head>
<body>
    <h1>{report_title}</h1>
    <div class="summary">
        <h2>{summary_section['title']}</h2>
        <p>{summary_section['task_id']}</p>
        <p>{summary_section['time']}</p>
        <p>{summary_section['total_images']}</p>
        <p>{summary_section['total_objects']}</p>
        <p>{summary_section['risk_level']}</p>
    </div>
    <h2>{'类别统计' if display_language == 'zh' else 'Class Statistics'}</h2>
    <table>
        <tr><th>{'类别' if display_language == 'zh' else 'Class'}</th><th>{'数量' if display_language == 'zh' else 'Count'}</th></tr>
        {class_counts_html}
    </table>
    <h2>{'检测结果详情' if display_language == 'zh' else 'Detection Details'}</h2>
    <table>
        <tr>
            <th>{'类别' if display_language == 'zh' else 'Class'}</th>
            <th>{'病害' if display_language == 'zh' else 'Disease'}</th>
            <th>{'植物' if display_language == 'zh' else 'Plant'}</th>
            <th>{'置信度' if display_language == 'zh' else 'Confidence'}</th>
            <th>{'边界框' if display_language == 'zh' else 'BBox'}</th>
        </tr>
        {results_html}
    </table>
    <div class="footer">
        <p>{'报告生成时间: ' if display_language == 'zh' else 'Generated at: '}{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
        <p>{'RSOD Agent Platform'}</p>
    </div>
</body>
</html>"""
        return html_content

    @staticmethod
    def get_task_report(user_id: int, task_id: int, display_language: str = "zh") -> dict | None:
        """返回检测报告预览数据。"""
        db = SessionLocal()
        try:
            task = (
                db.query(DetectionTask)
                .options(joinedload(DetectionTask.scene))
                .filter(DetectionTask.id == task_id, DetectionTask.user_id == user_id)
                .first()
            )
            if not task:
                return None

            results = (
                db.query(DetectionResult)
                .filter(DetectionResult.task_id == task_id)
                .all()
            )

            class_names_cn = task.scene.class_names_cn if task.scene else None
            class_counts = {}
            for r in results:
                class_counts[r.class_name] = class_counts.get(r.class_name, 0) + 1

            report_data = {
                "task_id": task.id,
                "report_title": "农作物病害检测报告" if display_language == "zh" else "Crop Disease Detection Report",
                "generated_at": datetime.now().isoformat(),
                "summary": {
                    "task_id": task.id,
                    "total_images": task.total_images or 0,
                    "total_objects": task.total_objects or 0,
                    "risk_level": task.risk_level or "未评估",
                    "treatment_status": task.treatment_status,
                },
                "class_counts": {
                    DetectionConfig.class_display_info(
                        name, class_names_cn=class_names_cn, display_language=display_language
                    )["class_name_display"]: count
                    for name, count in class_counts.items()
                },
                "results_count": len(results),
            }
            return report_data
        finally:
            db.close()

    @staticmethod
    def export_task_report(
        user_id: int, task_id: int, report_format: str = "pdf", display_language: str = "zh"
    ) -> dict | None:
        """导出检测报告为 HTML 或 PDF。"""
        db = SessionLocal()
        try:
            task = (
                db.query(DetectionTask)
                .options(joinedload(DetectionTask.scene))
                .filter(DetectionTask.id == task_id, DetectionTask.user_id == user_id)
                .first()
            )
            if not task:
                return None

            results = (
                db.query(DetectionResult)
                .filter(DetectionResult.task_id == task_id)
                .all()
            )

            html_content = HistoryService._build_report_html(task, results, display_language)

            if report_format == "html":
                return {
                    "content": html_content.encode("utf-8"),
                    "media_type": "text/html",
                    "filename": f"detection_report_{task_id}.html",
                }

            try:
                from weasyprint import HTML
                from weasyprint.document import Document
            except ImportError:
                raise RuntimeError("PDF 导出需要安装 weasyprint")

            document: Document = HTML(string=html_content).render()
            pdf_bytes = document.write_pdf()
            return {
                "content": pdf_bytes,
                "media_type": "application/pdf",
                "filename": f"detection_report_{task_id}.pdf",
            }
        finally:
            db.close()

    @staticmethod
    def delete_task(user_id: int, task_id: int) -> bool:
        """
        删除检测任务及其关联的检测结果

        Args:
            user_id: 用户 ID
            task_id: 任务 ID

        Returns:
            删除成功返回 True，否则返回 False
        """
        db = SessionLocal()
        try:
            task = (
                db.query(DetectionTask)
                .filter(DetectionTask.id == task_id, DetectionTask.user_id == user_id)
                .first()
            )

            if not task:
                return False

            db.delete(task)
            db.commit()
            return True
        finally:
            db.close()

    @staticmethod
    def get_summary(user_id: int) -> dict:
        """
        获取用户检测历史的快速统计摘要

        Args:
            user_id: 用户 ID

        Returns:
            统计数据字典
        """
        db = SessionLocal()
        try:
            total_tasks = (
                db.query(func.count(DetectionTask.id))
                .filter(DetectionTask.user_id == user_id)
                .scalar()
            )

            today = datetime.now().date()
            today_tasks = (
                db.query(func.count(DetectionTask.id))
                .filter(
                    DetectionTask.user_id == user_id,
                    func.date(DetectionTask.created_at) == today,
                )
                .scalar()
            )

            status_counts = (
                db.query(
                    DetectionTask.status,
                    func.count(DetectionTask.id).label("count"),
                )
                .filter(DetectionTask.user_id == user_id)
                .group_by(DetectionTask.status)
                .all()
            )

            return {
                "total_tasks": total_tasks or 0,
                "today_tasks": today_tasks or 0,
                "status_counts": {status: count for status, count in status_counts},
            }
        finally:
            db.close()

    @staticmethod
    def list_scenes() -> list[dict]:
        """
        获取所有可用的检测场景

        Returns:
            场景列表
        """
        db = SessionLocal()
        try:
            scenes = (
                db.query(DetectionScene)
                .filter(DetectionScene.is_active == True)
                .order_by(DetectionScene.name)
                .all()
            )
            return [
                {
                    "id": scene.id,
                    "name": scene.name,
                    "display_name": scene.display_name,
                    "description": scene.description,
                    "category": scene.category,
                    "class_names": scene.class_names,
                    "class_names_cn": scene.class_names_cn,
                }
                for scene in scenes
            ]
        finally:
            db.close()


history_service = HistoryService()