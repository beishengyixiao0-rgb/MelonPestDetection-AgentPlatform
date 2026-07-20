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
                    # 没有匹配植物时显式生成 SQL false 条件，避免依赖 Python bool 被 ORM 隐式解释。
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

            # PostgreSQL 的 json 类型没有默认 equality operator，不能对整行任务做 SELECT DISTINCT。
            # 这里先分页取去重任务 ID，再按 ID 加载任务详情，避免 join 多结果重复且兼容 JSON 字段。
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
            # 保存前统一用 Pydantic 校验结构，后续替换为 LLM 输出时也复用这条入口。
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

        # critical 只留给“范围大、扩散快、功能损害严重”同时出现的场景。
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
        # 规则评估和未来 LLM 评估都必须输出同一结构，避免非法枚举或空摘要入库。
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

            # 任务层保留最新一次评估摘要，方便历史列表和统计快速读取。
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
                # 直接返回模型来源，方便前端和接口测试判断是否经过 LLM 增强。
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
            reasons.append("当前问卷严重程度已经偏高，天气因素可能进一步放大风险。")
        elif task.risk_level == "moderate":
            score += 1
            reasons.append("当前问卷严重程度为中等，建议结合天气继续跟踪。")

        if score >= 7:
            level = "critical"
            summary = "未来天气条件叠加当前检测结果，病害扩散风险很高。"
        elif score >= 5:
            level = "high"
            summary = "未来天气条件可能促进病害扩散，建议尽快处理并复查。"
        elif score >= 3:
            level = "moderate"
            summary = "未来天气存在一定诱发或扩散风险，需要持续观察。"
        else:
            level = "low"
            summary = "未来天气暂未显示明显高风险信号，建议保持常规巡查。"

        recommendations.extend(
            [
                "结合检测结果和问卷严重程度确定处理优先级。",
                "记录处理日期和复查结果，必要时在历史记录中更新治疗状态。",
            ]
        )
        rule_risk = {
            "environment_risk_level": level,
            "weather_summary": summary,
            "weather_recommendations": recommendations,
            "weather_metrics": metrics,
            "reasons": reasons or ["当前天气指标未触发明显高风险规则。"],
        }
        return HistoryService._enhance_weather_risk_with_llm(rule_risk, task, results)

    @staticmethod
    def refresh_weather_risk(user_id: int, task_id: int) -> dict | None:
        """根据任务位置刷新天气风险，并把天气快照保存到任务上供报告复现。"""
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
            if task.latitude is None or task.longitude is None:
                return {"error": "请先为该检测任务补充地理位置", "status_code": 400}

            results = db.query(DetectionResult).filter(DetectionResult.task_id == task_id).all()
            weather_error = None
            snapshot = None
            try:
                snapshot = HistoryService._fetch_weather(task.latitude, task.longitude)
            except Exception as exc:  # 天气接口不可用时不影响历史记录主流程。
                weather_error = str(exc)

            risk = HistoryService._score_weather_risk(task, results, snapshot, weather_error)
            task.environment_risk_level = risk["environment_risk_level"]
            task.weather_summary = risk["weather_summary"]
            task.weather_recommendations = risk["weather_recommendations"]
            task.weather_snapshot = snapshot
            task.weather_updated_at = datetime.now()
            db.commit()
            return {
                "task_id": task.id,
                "latitude": task.latitude,
                "longitude": task.longitude,
                "location_name": task.location_name,
                **risk,
                "weather_updated_at": task.weather_updated_at.isoformat()
                if task.weather_updated_at
                else None,
            }
        finally:
            db.close()

    @staticmethod
    def _report_question_answers(assessments: list[dict]) -> list[dict]:
        """把问卷答案转换成带问题标签的列表，便于报告直接展示。"""
        question_map = {item["key"]: item for item in HistoryService.QUESTION_DEFINITIONS}
        answer_items = []
        for assessment in assessments:
            answers = assessment.get("answers") or {}
            for key, value in answers.items():
                question = question_map.get(key)
                label = question["label_zh"] if question else key
                answer_items.append(
                    {
                        "class_name_display": assessment.get("class_name_display"),
                        "key": key,
                        "label": label,
                        "answer": value,
                    }
                )
        return answer_items

    @staticmethod
    def _report_images(results: list[dict]) -> list[dict]:
        """按图片路径聚合原图和标注图，避免报告中同一图片重复展示过多。"""
        images = {}
        for item in results:
            image_path = item.get("image_path") or "unknown"
            current = images.setdefault(
                image_path,
                {
                    "image_path": item.get("image_path"),
                    "annotated_image_url": item.get("annotated_image_url"),
                    "classes": [],
                },
            )
            class_name = item.get("class_name_display") or item.get("class_name")
            if class_name and class_name not in current["classes"]:
                current["classes"].append(class_name)
            if not current.get("annotated_image_url") and item.get("annotated_image_url"):
                current["annotated_image_url"] = item.get("annotated_image_url")
        return list(images.values())

    @staticmethod
    def _report_weather_metrics(task: dict) -> dict:
        """从已保存天气快照提取报告指标；没有快照时返回空指标。"""
        snapshot = task.get("weather_snapshot") or {}
        return HistoryService._weather_metrics(snapshot) if snapshot else {}

    @staticmethod
    def _dedupe_keep_order(items: list[str]) -> list[str]:
        """保持顺序去重，用于合并严重程度建议和天气建议。"""
        seen = set()
        result = []
        for item in items:
            text = str(item).strip()
            if text and text not in seen:
                seen.add(text)
                result.append(text)
        return result

    @staticmethod
    def _report_action_items(task: dict, assessments: list[dict]) -> list[str]:
        """生成报告行动清单，优先包含高风险处理和复查动作。"""
        actions = []
        risk_level = task.get("risk_level")
        environment_level = task.get("environment_risk_level")
        if risk_level in {"high", "critical"} or environment_level in {"high", "critical"}:
            actions.append("优先处理高风险区域，并在 24-48 小时内复查。")
        for item in assessments:
            actions.extend(item.get("recommended_actions") or [])
        actions.extend(task.get("weather_recommendations") or [])
        actions.extend(
            [
                "记录处理日期、处理方式和复查结果，便于后续对比病害变化。",
                "如病害继续扩散或出现大面积萎蔫、落叶，应咨询当地农技人员。",
            ]
        )
        return HistoryService._dedupe_keep_order(actions)

    @staticmethod
    def _report_conclusion(task: dict, results: list[dict], action_items: list[str]) -> str:
        """生成报告综合结论，突出主要病害、严重程度、天气风险和下一步动作。"""
        primary = results[0] if results else {}
        disease = primary.get("class_name_display") or primary.get("class_name") or "未识别到明确病害"
        risk_level = task.get("risk_level") or "unassessed"
        environment_level = task.get("environment_risk_level") or "unavailable"
        treatment_status = task.get("treatment_status") or "pending"
        next_action = action_items[0] if action_items else "建议持续观察并补充现场信息。"
        return (
            f"本次检测主要结果为 {disease}，严重程度为 {risk_level}，"
            f"天气环境风险为 {environment_level}，当前处理状态为 {treatment_status}。"
            f"{next_action}"
        )

    @staticmethod
    def _report_value(value) -> str:
        """把列表、字典和空值转换为报告中可读的文本。"""
        if value is None:
            return ""
        if isinstance(value, list):
            return "、".join(str(item) for item in value)
        if isinstance(value, dict):
            return json.dumps(value, ensure_ascii=False)
        return str(value)

    @staticmethod
    def _is_report_image_reference(value: str | None) -> bool:
        """判断路径或 URL 是否可能被后端读取并嵌入 PDF。"""
        if not value:
            return False
        parsed = urlparse(value)
        if parsed.scheme in {"http", "https"}:
            # 测试数据中常见的 http://minio/... 不是可直连地址；真实 URL 会继续尝试下载。
            return parsed.hostname != "minio"
        return Path(value).is_file()

    @staticmethod
    def _load_report_image_bytes(reference: str | None) -> bytes | None:
        """读取本地图片或 MinIO 预签名 URL；失败时返回 None，不阻断报告导出。"""
        if not HistoryService._is_report_image_reference(reference):
            return None
        parsed = urlparse(reference or "")
        try:
            if parsed.scheme in {"http", "https"}:
                response = httpx.get(reference, timeout=5, follow_redirects=True)
                response.raise_for_status()
                content_type = response.headers.get("content-type", "")
                if content_type and "image" not in content_type:
                    return None
                return response.content
            return Path(reference or "").read_bytes()
        except Exception as exc:
            logger.warning("报告图片读取失败，已跳过嵌入: %s", exc)
            return None

    @staticmethod
    def _select_report_image_samples(report: dict) -> list[dict]:
        """按任务类型选择 PDF 中嵌入的图片数量。"""
        task_type = (report.get("task") or {}).get("task_type")
        images = report.get("inspection_images") or []
        if task_type == "video":
            limit = 6
            # 视频历史可能只有部分帧保存了关键帧图；PDF 只展示可嵌入帧，避免输出占位提示。
            images = [
                item
                for item in images
                if HistoryService._is_report_image_reference(item.get("annotated_image_url"))
            ]
        elif task_type == "batch":
            limit = len(images) if len(images) <= 4 else 4
        else:
            limit = 1
        samples = []
        for item in images[:limit]:
            samples.append(
                {
                    "title": HistoryService._report_value(item.get("classes")) or "检测图片",
                    "source": item.get("image_path") if task_type != "video" else None,
                    "annotated": item.get("annotated_image_url"),
                    "image_path": item.get("image_path"),
                }
            )
        return samples

    @staticmethod
    def _report_data(user_id: int, task_id: int, display_language: str = "zh") -> dict | None:
        """聚合报告需要的检测、评估、治疗、位置和天气信息。"""
        detail = HistoryService.get_task_detail(user_id, task_id, display_language)
        if not detail:
            return None
        task = detail["task"]
        results = detail["results"]
        assessments = detail.get("severity_assessments", [])
        action_items = HistoryService._report_action_items(task, assessments)
        weather_metrics = HistoryService._report_weather_metrics(task)
        return {
            "generated_at": datetime.now().isoformat(),
            "task": task,
            "class_counts": detail["class_counts"],
            "class_counts_display": detail["class_counts_display"],
            "results": results,
            "inspection_images": HistoryService._report_images(results),
            "severity_assessments": assessments,
            "question_answers": HistoryService._report_question_answers(assessments),
            "weather_metrics": weather_metrics,
            "integrated_conclusion": HistoryService._report_conclusion(
                task,
                results,
                action_items,
            ),
            "action_items": action_items,
            "data_sources": {
                "detection_model": "YOLO",
                "weather_source": "Open-Meteo",
                "severity_source": "rule-based + optional LLM enhancement",
                "generated_by": "RSOD Agent Platform",
                "disclaimer": "AI 检测、天气风险和建议仅作辅助决策，最终处理应结合现场情况和当地农技意见。",
            },
            "follow_up_template": [
                "复查日期：",
                "复查结果：",
                "是否继续扩散：",
                "已采取处理措施：",
                "后续备注：",
            ],
            "report_summary": {
                "risk_level": task.get("risk_level") or "unassessed",
                "treatment_status": task.get("treatment_status") or "pending",
                "environment_risk_level": task.get("environment_risk_level") or "unavailable",
            },
        }

    @staticmethod
    def _render_report_html(report: dict) -> str:
        """生成可下载 HTML 报告；浏览器可直接打开并打印为 PDF。"""
        task = report["task"]
        results = report["results"]
        assessments = report["severity_assessments"]

        def esc(value) -> str:
            return html.escape("" if value is None else str(value))

        def fmt(value) -> str:
            return esc(HistoryService._report_value(value))

        result_rows = "\n".join(
            f"<tr><td>{esc(item.get('class_name_display'))}</td><td>{esc(item.get('plant_name_display'))}</td>"
            f"<td>{esc(item.get('disease_name_display'))}</td><td>{esc(item.get('confidence'))}</td>"
            f"<td>{fmt(item.get('bbox'))}</td><td>{esc(item.get('annotated_image_url'))}</td></tr>"
            for item in results
        )
        image_rows = "\n".join(
            f"<tr><td>{esc(item.get('image_path'))}</td><td>{esc(item.get('annotated_image_url'))}</td>"
            f"<td>{fmt(item.get('classes'))}</td></tr>"
            for item in report.get("inspection_images", [])
        )
        assessment_blocks = "\n".join(
            "<section><h3>"
            + esc(item.get("class_name_display"))
            + "</h3><p>严重程度："
            + esc(item.get("risk_level"))
            + "，可信度："
            + esc(item.get("assessment_confidence"))
            + "</p><p>"
            + esc(item.get("summary"))
            + "</p><ul>"
            + "".join(f"<li>{esc(action)}</li>" for action in item.get("recommended_actions", []))
            + "</ul></section>"
            for item in assessments
        )
        if not assessment_blocks:
            assessment_blocks = "<p>暂未填写严重程度问卷。</p>"
        question_rows = "\n".join(
            f"<tr><td>{esc(item.get('class_name_display'))}</td><td>{esc(item.get('label'))}</td>"
            f"<td>{fmt(item.get('answer'))}</td></tr>"
            for item in report.get("question_answers", [])
        )
        weather_metrics = report.get("weather_metrics") or {}
        weather_rows = "\n".join(
            f"<tr><th>{esc(label)}</th><td>{fmt(value)}</td></tr>"
            for label, value in [
                ("未来 3 天平均湿度", weather_metrics.get("avg_humidity")),
                ("未来 3 天平均温度", weather_metrics.get("avg_temperature")),
                ("最大降雨概率", weather_metrics.get("max_precipitation_probability")),
                ("累计降雨量", weather_metrics.get("total_precipitation")),
                ("逐日降雨量", weather_metrics.get("daily_precipitation_sum")),
            ]
        )
        action_items = "".join(
            f"<li>{esc(item)}</li>" for item in report.get("action_items", [])
        )
        sources = report.get("data_sources") or {}
        source_rows = "\n".join(
            f"<tr><th>{esc(label)}</th><td>{esc(value)}</td></tr>"
            for label, value in [
                ("目标检测模型", sources.get("detection_model")),
                ("天气数据来源", sources.get("weather_source")),
                ("严重程度来源", sources.get("severity_source")),
                ("报告生成系统", sources.get("generated_by")),
                ("使用说明", sources.get("disclaimer")),
            ]
        )
        follow_up_items = "".join(
            f"<li>{esc(item)}</li>" for item in report.get("follow_up_template", [])
        )

        return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <title>检测报告 #{esc(task.get("id"))}</title>
  <style>
    body {{ font-family: Arial, "Microsoft YaHei", sans-serif; line-height: 1.6; color: #1f2937; }}
    main {{ max-width: 960px; margin: 24px auto; padding: 0 24px; }}
    h1, h2, h3 {{ color: #111827; }}
    table {{ width: 100%; border-collapse: collapse; margin: 12px 0 24px; }}
    th, td {{ border: 1px solid #d1d5db; padding: 8px; text-align: left; word-break: break-word; }}
    th {{ background: #f3f4f6; }}
    .muted {{ color: #6b7280; }}
  </style>
</head>
<body>
<main>
  <h1>农作物病害检测报告</h1>
  <p class="muted">生成时间：{esc(report.get("generated_at"))}</p>

  <h2>综合结论</h2>
  <p>{esc(report.get("integrated_conclusion"))}</p>

  <h2>任务信息</h2>
  <table>
    <tr><th>任务 ID</th><td>{esc(task.get("id"))}</td></tr>
    <tr><th>检测场景</th><td>{esc(task.get("scene_name"))}</td></tr>
    <tr><th>检测时间</th><td>{esc(task.get("created_at"))}</td></tr>
    <tr><th>检测类型</th><td>{esc(task.get("task_type"))}</td></tr>
    <tr><th>图片数量</th><td>{esc(task.get("total_images"))}</td></tr>
    <tr><th>目标数量</th><td>{esc(task.get("total_objects"))}</td></tr>
    <tr><th>严重程度</th><td>{esc(task.get("risk_level") or "unassessed")}</td></tr>
    <tr><th>治疗状态</th><td>{esc(task.get("treatment_status"))}</td></tr>
    <tr><th>处理备注</th><td>{esc(task.get("treatment_note"))}</td></tr>
  </table>

  <h2>检测图片</h2>
  <table>
    <tr><th>原图路径</th><th>标注图 URL</th><th>识别类别</th></tr>
    {image_rows}
  </table>

  <h2>检测结果</h2>
  <table>
    <tr><th>类别</th><th>植物</th><th>病害</th><th>置信度</th><th>检测框</th><th>标注图 URL</th></tr>
    {result_rows}
  </table>

  <h2>严重程度评估</h2>
  {assessment_blocks}

  <h2>问卷答案</h2>
  <table>
    <tr><th>评估类别</th><th>问题</th><th>答案</th></tr>
    {question_rows}
  </table>

  <h2>天气与环境风险</h2>
  <table>
    <tr><th>地点</th><td>{esc(task.get("location_name"))}</td></tr>
    <tr><th>经纬度</th><td>{esc(task.get("latitude"))}, {esc(task.get("longitude"))}</td></tr>
    <tr><th>环境风险</th><td>{esc(task.get("environment_risk_level"))}</td></tr>
    <tr><th>天气摘要</th><td>{esc(task.get("weather_summary"))}</td></tr>
    <tr><th>更新时间</th><td>{esc(task.get("weather_updated_at"))}</td></tr>
    {weather_rows}
  </table>
  <ul>
    {"".join(f"<li>{esc(item)}</li>" for item in task.get("weather_recommendations", []))}
  </ul>

  <h2>后续行动清单</h2>
  <ul>{action_items}</ul>

  <h2>数据来源说明</h2>
  <table>{source_rows}</table>

  <h2>复查记录</h2>
  <ul>{follow_up_items}</ul>
</main>
</body>
</html>"""

    @staticmethod
    def _render_report_pdf(report: dict) -> bytes:
        """生成 PDF 报告；依赖 reportlab，部署前需安装 requirements.txt。"""
        try:
            from reportlab.lib import colors
            from reportlab.lib.pagesizes import A4
            from reportlab.lib.styles import getSampleStyleSheet
            from reportlab.lib.units import mm
            from reportlab.pdfbase import pdfmetrics
            from reportlab.pdfbase.ttfonts import TTFont
            from reportlab.platypus import Image, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
        except ImportError as exc:
            raise RuntimeError("PDF 导出依赖 reportlab 未安装，请先执行 pip install -r requirements.txt") from exc

        font_name = "Helvetica"
        for font_path in [r"C:\Windows\Fonts\msyh.ttc", r"C:\Windows\Fonts\simsun.ttc"]:
            try:
                pdfmetrics.registerFont(TTFont("ChineseFont", font_path))
                font_name = "ChineseFont"
                break
            except Exception:
                continue

        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4, leftMargin=16 * mm, rightMargin=16 * mm)
        styles = getSampleStyleSheet()
        for style in styles.byName.values():
            style.fontName = font_name
            style.leading = max(getattr(style, "leading", 12), getattr(style, "fontSize", 10) + 3)
        styles["Title"].textColor = colors.HexColor("#166534")
        styles["Heading2"].textColor = colors.HexColor("#14532d")
        styles["Heading3"].textColor = colors.HexColor("#1f2937")

        def p(value, style_name: str = "Normal"):
            return Paragraph(html.escape(HistoryService._report_value(value)), styles[style_name])

        def apply_table_style(table: Table) -> Table:
            table.setStyle(
                TableStyle(
                    [
                        ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#cbd5e1")),
                        ("FONT", (0, 0), (-1, -1), font_name),
                        ("VALIGN", (0, 0), (-1, -1), "TOP"),
                        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#dcfce7")),
                        ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#14532d")),
                        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f8fafc")]),
                        ("LEFTPADDING", (0, 0), (-1, -1), 6),
                        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                        ("TOPPADDING", (0, 0), (-1, -1), 5),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                    ]
                )
            )
            return table

        def image_flowable(reference: str | None, max_width: float, max_height: float):
            image_bytes = HistoryService._load_report_image_bytes(reference)
            if not image_bytes:
                return p("图片暂不可嵌入，保留路径/URL。")
            flowable = Image(BytesIO(image_bytes))
            ratio = min(max_width / flowable.imageWidth, max_height / flowable.imageHeight)
            ratio = min(ratio, 1)
            flowable.drawWidth = flowable.imageWidth * ratio
            flowable.drawHeight = flowable.imageHeight * ratio
            return flowable

        task = report["task"]
        story = [
            Paragraph("农作物病害检测报告", styles["Title"]),
            Paragraph(f"生成时间：{report.get('generated_at')}", styles["Normal"]),
            Spacer(1, 8),
            Paragraph("综合结论", styles["Heading2"]),
            p(report.get("integrated_conclusion")),
            Spacer(1, 8),
            Paragraph("任务信息", styles["Heading2"]),
        ]
        task_table = Table(
            [
                [p("任务 ID"), p(task.get("id"))],
                [p("检测场景"), p(task.get("scene_name"))],
                [p("检测时间"), p(task.get("created_at"))],
                [p("检测类型"), p(task.get("task_type"))],
                [p("图片数量"), p(task.get("total_images") or 0)],
                [p("目标数量"), p(task.get("total_objects") or 0)],
                [p("严重程度"), p(task.get("risk_level") or "unassessed")],
                [p("治疗状态"), p(task.get("treatment_status") or "pending")],
                [p("环境风险"), p(task.get("environment_risk_level") or "unavailable")],
                [p("处理备注"), p(task.get("treatment_note"))],
            ],
            colWidths=[36 * mm, 120 * mm],
        )
        story.extend([apply_table_style(task_table), Spacer(1, 8)])

        story.append(Paragraph("图片预览", styles["Heading2"]))
        samples = HistoryService._select_report_image_samples(report)
        if not samples:
            story.append(p("暂无可嵌入报告的图片。"))
        for index, sample in enumerate(samples, start=1):
            story.append(p(f"样本 {index}：{sample.get('title')}", "Heading3"))
            source_ref = sample.get("source")
            annotated_ref = sample.get("annotated")
            if source_ref and annotated_ref:
                image_table = Table(
                    [
                        [p("原图"), p("标注图")],
                        [
                            image_flowable(source_ref, 72 * mm, 54 * mm),
                            image_flowable(annotated_ref, 72 * mm, 54 * mm),
                        ],
                    ],
                    colWidths=[78 * mm, 78 * mm],
                )
            else:
                display_ref = annotated_ref or source_ref or sample.get("image_path")
                image_table = Table(
                    [
                        [p("关键帧/检测图")],
                        [image_flowable(display_ref, 150 * mm, 78 * mm)],
                    ],
                    colWidths=[156 * mm],
                )
            story.extend([apply_table_style(image_table), Spacer(1, 6)])

        story.extend([Spacer(1, 8), Paragraph("检测结果", styles["Heading2"])])

        rows = [[p("类别"), p("植物"), p("病害"), p("置信度"), p("检测框")]]
        for item in report["results"]:
            rows.append([
                p(item.get("class_name_display")),
                p(item.get("plant_name_display")),
                p(item.get("disease_name_display")),
                p(item.get("confidence")),
                p(item.get("bbox")),
            ])
        result_table = Table(rows, colWidths=[40 * mm, 28 * mm, 34 * mm, 20 * mm, 34 * mm])
        story.append(apply_table_style(result_table))

        story.extend([Spacer(1, 8), Paragraph("严重程度评估", styles["Heading2"])])
        if report["severity_assessments"]:
            for item in report["severity_assessments"]:
                story.append(p(item.get("class_name_display"), "Heading3"))
                story.append(p(f"严重程度：{item.get('risk_level')}，可信度：{item.get('assessment_confidence')}，模型：{item.get('llm_model')}"))
                story.append(p(item.get("summary")))
                for reason in item.get("reasons", []):
                    story.append(p(f"- {reason}"))
        else:
            story.append(p("暂未填写严重程度问卷。"))

        story.extend([Spacer(1, 8), Paragraph("问卷答案", styles["Heading2"])])
        question_rows = [[p("评估类别"), p("问题"), p("答案")]]
        for item in report.get("question_answers", []):
            question_rows.append(
                [p(item.get("class_name_display")), p(item.get("label")), p(item.get("answer"))]
            )
        question_table = Table(question_rows, colWidths=[36 * mm, 76 * mm, 44 * mm])
        story.append(apply_table_style(question_table))

        story.extend([Spacer(1, 8), Paragraph("天气与环境风险", styles["Heading2"])])
        metrics = report.get("weather_metrics") or {}
        weather_rows = [
            [p("地点"), p(task.get("location_name"))],
            [p("经纬度"), p(f"{task.get('latitude')}, {task.get('longitude')}")],
            [p("环境风险"), p(task.get("environment_risk_level") or "unavailable")],
            [p("天气摘要"), p(task.get("weather_summary"))],
            [p("平均湿度"), p(metrics.get("avg_humidity"))],
            [p("平均温度"), p(metrics.get("avg_temperature"))],
            [p("最大降雨概率"), p(metrics.get("max_precipitation_probability"))],
            [p("累计降雨量"), p(metrics.get("total_precipitation"))],
            [p("逐日降雨量"), p(metrics.get("daily_precipitation_sum"))],
        ]
        weather_table = Table(weather_rows, colWidths=[42 * mm, 114 * mm])
        story.append(apply_table_style(weather_table))

        story.extend([Spacer(1, 8), Paragraph("后续行动清单", styles["Heading2"])])
        for action in report.get("action_items", []) or ["暂未生成建议。"]:
            story.append(p(f"- {action}"))

        story.extend([Spacer(1, 8), Paragraph("数据来源说明", styles["Heading2"])])
        sources = report.get("data_sources") or {}
        source_table = Table(
            [
                [p("目标检测模型"), p(sources.get("detection_model"))],
                [p("天气数据来源"), p(sources.get("weather_source"))],
                [p("严重程度来源"), p(sources.get("severity_source"))],
                [p("报告生成系统"), p(sources.get("generated_by"))],
                [p("使用说明"), p(sources.get("disclaimer"))],
            ],
            colWidths=[42 * mm, 114 * mm],
        )
        story.append(apply_table_style(source_table))

        story.extend([Spacer(1, 8), Paragraph("复查记录", styles["Heading2"])])
        for item in report.get("follow_up_template", []):
            story.append(p(f"- {item}"))

        doc.build(story)
        return buffer.getvalue()

    @staticmethod
    def get_task_report(user_id: int, task_id: int, display_language: str = "zh") -> dict | None:
        """返回报告 JSON 预览，供前端确认导出内容。"""
        return HistoryService._report_data(user_id, task_id, display_language)

    @staticmethod
    def export_task_report(
        user_id: int,
        task_id: int,
        report_format: str = "pdf",
        display_language: str = "zh",
    ) -> dict | None:
        """导出 HTML 或 PDF 报告，返回文件字节和响应元信息。"""
        report = HistoryService._report_data(user_id, task_id, display_language)
        if not report:
            return None
        filename_base = f"detection_report_{task_id}"
        if report_format == "pdf":
            content = HistoryService._render_report_pdf(report)
            return {
                "content": content,
                "media_type": "application/pdf",
                "filename": f"{filename_base}.pdf",
            }
        html_content = HistoryService._render_report_html(report).encode("utf-8")
        return {
            "content": html_content,
            "media_type": "text/html; charset=utf-8",
            "filename": f"{filename_base}.html",
        }

    @staticmethod
    def delete_task(user_id: int, task_id: int) -> bool:
        """
        删除检测任务及其关联的检测结果（级联删除）

        Args:
            user_id: 用户 ID
            task_id: 任务 ID

        Returns:
            删除成功返回 True，任务不存在或无权访问返回 False
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

            logger.info("用户 %d 删除检测任务 #%d", user_id, task_id)
            return True
        finally:
            db.close()

    @staticmethod
    def get_summary(user_id: int) -> dict:
        """
        获取用户检测历史摘要统计

        Args:
            user_id: 用户 ID

        Returns:
            统计信息字典：总任务数、今日任务数、各状态任务数
        """
        db = SessionLocal()
        try:
            today_start = datetime.now().replace(
                hour=0, minute=0, second=0, microsecond=0
            )

            total = (
                db.query(func.count(DetectionTask.id))
                .filter(DetectionTask.user_id == user_id)
                .scalar()
            )

            today_count = (
                db.query(func.count(DetectionTask.id))
                .filter(
                    DetectionTask.user_id == user_id,
                    DetectionTask.created_at >= today_start,
                )
                .scalar()
            )

            status_counts = {}
            for s in ["completed", "processing", "failed", "pending"]:
                count = (
                    db.query(func.count(DetectionTask.id))
                    .filter(DetectionTask.user_id == user_id, DetectionTask.status == s)
                    .scalar()
                )
                status_counts[s] = count

            risk_counts = {}
            for level in HistoryService.RISK_LEVELS:
                count = (
                    db.query(func.count(DetectionTask.id))
                    .filter(
                        DetectionTask.user_id == user_id,
                        DetectionTask.risk_level == level,
                    )
                    .scalar()
                )
                risk_counts[level] = count
            risk_counts["unassessed"] = (
                db.query(func.count(DetectionTask.id))
                .filter(
                    DetectionTask.user_id == user_id,
                    DetectionTask.risk_level.is_(None),
                )
                .scalar()
            )

            treatment_counts = {}
            for status in HistoryService.TREATMENT_STATUSES:
                count = (
                    db.query(func.count(DetectionTask.id))
                    .filter(
                        DetectionTask.user_id == user_id,
                        DetectionTask.treatment_status == status,
                    )
                    .scalar()
                )
                treatment_counts[status] = count

            return {
                "total_tasks": total,
                "today_tasks": today_count,
                "status_counts": status_counts,
                "risk_counts": risk_counts,
                "treatment_counts": treatment_counts,
            }
        finally:
            db.close()

    @staticmethod
    def list_scenes() -> list:
        """
        获取所有可用的检测场景列表

        Returns:
            场景列表
        """
        db = SessionLocal()
        try:
            scenes = (
                db.query(DetectionScene).filter(DetectionScene.is_active == True).all()
            )
            return [
                {
                    "id": s.id,
                    "name": s.name,
                    "display_name": s.display_name,
                    "category": s.category,
                }
                for s in scenes
            ]
        finally:
            db.close()


history_service = HistoryService()
