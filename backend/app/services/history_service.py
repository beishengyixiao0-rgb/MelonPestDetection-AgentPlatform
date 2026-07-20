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
from datetime import datetime
from io import BytesIO
from typing import Optional

import httpx
from sqlalchemy import desc, false, func, or_
from sqlalchemy.orm import joinedload

from app.config.detection import DetectionConfig
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
            assessment.llm_model = "rule-based"
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
        return {
            "environment_risk_level": level,
            "weather_summary": summary,
            "weather_recommendations": recommendations,
            "weather_metrics": metrics,
            "reasons": reasons or ["当前天气指标未触发明显高风险规则。"],
        }

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
    def _report_data(user_id: int, task_id: int, display_language: str = "zh") -> dict | None:
        """聚合报告需要的检测、评估、治疗、位置和天气信息。"""
        detail = HistoryService.get_task_detail(user_id, task_id, display_language)
        if not detail:
            return None
        task = detail["task"]
        return {
            "generated_at": datetime.now().isoformat(),
            "task": task,
            "class_counts": detail["class_counts"],
            "class_counts_display": detail["class_counts_display"],
            "results": detail["results"],
            "severity_assessments": detail.get("severity_assessments", []),
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

        result_rows = "\n".join(
            f"<tr><td>{esc(item.get('class_name_display'))}</td><td>{esc(item.get('plant_name_display'))}</td>"
            f"<td>{esc(item.get('disease_name_display'))}</td><td>{esc(item.get('confidence'))}</td>"
            f"<td>{esc(item.get('annotated_image_url'))}</td></tr>"
            for item in results
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

  <h2>任务信息</h2>
  <table>
    <tr><th>任务 ID</th><td>{esc(task.get("id"))}</td></tr>
    <tr><th>检测场景</th><td>{esc(task.get("scene_name"))}</td></tr>
    <tr><th>检测时间</th><td>{esc(task.get("created_at"))}</td></tr>
    <tr><th>图片数量</th><td>{esc(task.get("total_images"))}</td></tr>
    <tr><th>目标数量</th><td>{esc(task.get("total_objects"))}</td></tr>
    <tr><th>治疗状态</th><td>{esc(task.get("treatment_status"))}</td></tr>
  </table>

  <h2>检测结果</h2>
  <table>
    <tr><th>类别</th><th>植物</th><th>病害</th><th>置信度</th><th>标注图 URL</th></tr>
    {result_rows}
  </table>

  <h2>严重程度评估</h2>
  {assessment_blocks}

  <h2>天气与环境风险</h2>
  <table>
    <tr><th>地点</th><td>{esc(task.get("location_name"))}</td></tr>
    <tr><th>经纬度</th><td>{esc(task.get("latitude"))}, {esc(task.get("longitude"))}</td></tr>
    <tr><th>环境风险</th><td>{esc(task.get("environment_risk_level"))}</td></tr>
    <tr><th>天气摘要</th><td>{esc(task.get("weather_summary"))}</td></tr>
  </table>
  <ul>
    {"".join(f"<li>{esc(item)}</li>" for item in task.get("weather_recommendations", []))}
  </ul>
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
            from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
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

        task = report["task"]
        story = [
            Paragraph("农作物病害检测报告", styles["Title"]),
            Paragraph(f"生成时间：{report.get('generated_at')}", styles["Normal"]),
            Spacer(1, 8),
            Paragraph("任务信息", styles["Heading2"]),
        ]
        task_table = Table(
            [
                ["任务 ID", str(task.get("id"))],
                ["检测场景", task.get("scene_name") or ""],
                ["检测时间", task.get("created_at") or ""],
                ["目标数量", str(task.get("total_objects") or 0)],
                ["严重程度", task.get("risk_level") or "unassessed"],
                ["治疗状态", task.get("treatment_status") or "pending"],
                ["环境风险", task.get("environment_risk_level") or "unavailable"],
            ],
            colWidths=[36 * mm, 120 * mm],
        )
        task_table.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.5, colors.grey), ("FONT", (0, 0), (-1, -1), font_name)]))
        story.extend([task_table, Spacer(1, 8), Paragraph("检测结果", styles["Heading2"])])

        rows = [["类别", "植物", "病害", "置信度"]]
        for item in report["results"]:
            rows.append([
                item.get("class_name_display") or "",
                item.get("plant_name_display") or "",
                item.get("disease_name_display") or "",
                str(item.get("confidence") or ""),
            ])
        result_table = Table(rows, colWidths=[48 * mm, 35 * mm, 45 * mm, 24 * mm])
        result_table.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.5, colors.grey), ("FONT", (0, 0), (-1, -1), font_name)]))
        story.append(result_table)

        story.extend([Spacer(1, 8), Paragraph("建议", styles["Heading2"])])
        actions = []
        for item in report["severity_assessments"]:
            actions.extend(item.get("recommended_actions", []))
        actions.extend(task.get("weather_recommendations") or [])
        for action in actions or ["暂未生成建议。"]:
            story.append(Paragraph(f"- {action}", styles["Normal"]))

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
