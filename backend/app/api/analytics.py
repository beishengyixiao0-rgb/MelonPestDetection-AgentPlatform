"""
分析看板 API 路由

提供数据可视化所需的统计接口：
  - GET  /api/analytics/summary        获取总体统计概览
  - GET  /api/analytics/disease-distribution  获取疾病分布统计
  - GET  /api/analytics/detection-trend       获取检测趋势数据
  - GET  /api/analytics/model-performance     获取模型性能指标
  - GET  /api/analytics/top-diseases         获取热门疾病排行
"""

from datetime import datetime, timedelta
from typing import List

from app.api.auth import get_current_user
from app.core.logger import get_logger
from app.database.session import get_db
from app.entity.db_models import (
    DetectionResult,
    DetectionTask,
    ModelVersion,
    TrainingTask,
)
from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

logger = get_logger(__name__)
router = APIRouter(prefix="/api/analytics", tags=["analytics"])

COLORS = ["#16a34a", "#0ea5e9", "#f59e0b", "#8b5cf6", "#ec4899", "#94a3b8"]


@router.get("/summary")
def get_analytics_summary(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """
    获取分析看板总体统计概览
    """
    total_tasks = (
        db.query(func.count(DetectionTask.id))
        .filter(DetectionTask.user_id == current_user.id)
        .scalar()
    ) or 0

    total_images = (
        db.query(func.coalesce(func.sum(DetectionTask.total_images), 0))
        .filter(DetectionTask.user_id == current_user.id)
        .scalar()
    )

    total_objects = (
        db.query(func.coalesce(func.sum(DetectionTask.total_objects), 0))
        .filter(DetectionTask.user_id == current_user.id)
        .scalar()
    )

    last_month_start = datetime.now() - timedelta(days=30)
    last_month_tasks = (
        db.query(func.count(DetectionTask.id))
        .filter(
            DetectionTask.user_id == current_user.id,
            DetectionTask.created_at >= last_month_start,
        )
        .scalar()
    ) or 0

    two_month_ago_start = datetime.now() - timedelta(days=60)
    prev_month_tasks = (
        db.query(func.count(DetectionTask.id))
        .filter(
            DetectionTask.user_id == current_user.id,
            DetectionTask.created_at >= two_month_ago_start,
            DetectionTask.created_at < last_month_start,
        )
        .scalar()
    ) or 0

    detection_change = 0
    if prev_month_tasks > 0:
        detection_change = round(
            ((last_month_tasks - prev_month_tasks) / prev_month_tasks) * 100, 1
        )

    avg_confidence = (
        db.query(func.coalesce(func.avg(DetectionResult.confidence), 0))
        .join(DetectionTask)
        .filter(DetectionTask.user_id == current_user.id)
        .scalar()
    )
    avg_confidence = round(avg_confidence * 100, 1) if avg_confidence else 0

    latest_model = (
        db.query(ModelVersion)
        .join(TrainingTask)
        .filter(TrainingTask.user_id == current_user.id)
        .order_by(ModelVersion.created_at.desc())
        .first()
    )

    model_accuracy = 0
    if latest_model and latest_model.map50:
        model_accuracy = round(latest_model.map50 * 100, 1)

    accuracy_change = 0
    if latest_model:
        prev_model = (
            db.query(ModelVersion)
            .join(TrainingTask)
            .filter(
                TrainingTask.user_id == current_user.id,
                ModelVersion.id != latest_model.id,
            )
            .order_by(ModelVersion.created_at.desc())
            .first()
        )
        if prev_model and prev_model.map50:
            accuracy_change = round((latest_model.map50 - prev_model.map50) * 100, 1)

    identified_count = (
        db.query(func.count(DetectionResult.id))
        .join(DetectionTask)
        .filter(DetectionTask.user_id == current_user.id)
        .scalar()
    ) or 0

    identification_rate = 0
    if total_images > 0:
        identification_rate = round((identified_count / (total_images * 3)) * 100, 1)

    return {
        "total_detections": total_tasks,
        "detection_change": detection_change,
        "diseases_identified": identified_count,
        "identification_rate": identification_rate,
        "model_accuracy": model_accuracy,
        "accuracy_change": accuracy_change,
        "avg_confidence": avg_confidence,
        "data_updated_at": datetime.now().isoformat(),
    }


@router.get("/disease-distribution")
def get_disease_distribution(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """
    获取疾病分布统计（饼图数据）
    """
    last_30_days = datetime.now() - timedelta(days=30)

    distribution = (
        db.query(
            DetectionResult.class_name,
            DetectionResult.class_name_cn,
            func.count(DetectionResult.class_name),
        )
        .join(DetectionTask)
        .filter(
            DetectionTask.user_id == current_user.id,
            DetectionTask.created_at >= last_30_days,
        )
        .group_by(DetectionResult.class_name, DetectionResult.class_name_cn)
        .order_by(func.count(DetectionResult.class_name).desc())
        .limit(6)
        .all()
    )

    total = sum(count for _, _, count in distribution) if distribution else 0

    result = []
    other_count = 0

    for i, (class_name, class_name_cn, count) in enumerate(distribution):
        if i < 5:
            percentage = round((count / total) * 100, 1) if total > 0 else 0
            result.append(
                {
                    "name": class_name_cn or class_name,
                    "value": percentage,
                    "count": count,
                    "color": COLORS[i],
                }
            )
        else:
            other_count += count

    if other_count > 0 and total > 0:
        other_percentage = round((other_count / total) * 100, 1)
        result.append(
            {
                "name": "其他",
                "value": other_percentage,
                "count": other_count,
                "color": COLORS[5],
            }
        )

    if not result:
        result = [
            {
                "name": "No Data",
                "value": 100,
                "count": 0,
                "color": COLORS[5],
            }
        ]

    return result


@router.get("/detection-trend")
def get_detection_trend(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """
    获取检测趋势数据（折线图数据，最近7个月）
    """
    now = datetime.now()
    trend_data = []

    for i in range(6, -1, -1):
        month_start = (now.replace(day=1) - timedelta(days=i * 30)).replace(day=1)
        month_end = (month_start + timedelta(days=32)).replace(day=1)

        month_label = month_start.strftime("%b")

        tasks_count = (
            db.query(func.count(DetectionTask.id))
            .filter(
                DetectionTask.user_id == current_user.id,
                DetectionTask.created_at >= month_start,
                DetectionTask.created_at < month_end,
            )
            .scalar()
        ) or 0

        objects_count = (
            db.query(func.coalesce(func.sum(DetectionTask.total_objects), 0))
            .filter(
                DetectionTask.user_id == current_user.id,
                DetectionTask.created_at >= month_start,
                DetectionTask.created_at < month_end,
            )
            .scalar()
        )

        trend_data.append(
            {
                "month": month_label,
                "detections": tasks_count,
                "identified": objects_count,
            }
        )

    return trend_data


@router.get("/model-performance")
def get_model_performance(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """
    获取模型性能指标
    """
    latest_model = (
        db.query(ModelVersion)
        .join(TrainingTask)
        .filter(TrainingTask.user_id == current_user.id)
        .order_by(ModelVersion.created_at.desc())
        .first()
    )

    if not latest_model:
        return [
            {
                "label": "Precision",
                "value": 0,
                "color": COLORS[0],
            },
            {
                "label": "Recall",
                "value": 0,
                "color": COLORS[1],
            },
            {
                "label": "F1 Score",
                "value": 0,
                "color": COLORS[2],
            },
            {
                "label": "mAP@50",
                "value": 0,
                "color": COLORS[3],
            },
        ]

    precision = round(latest_model.precision * 100, 1) if latest_model.precision else 0
    recall = round(latest_model.recall * 100, 1) if latest_model.recall else 0
    map50 = round(latest_model.map50 * 100, 1) if latest_model.map50 else 0

    f1_score = 0
    if precision + recall > 0:
        f1_score = round(2 * precision * recall / (precision + recall), 1)

    return [
        {
            "label": "Precision",
            "value": precision,
            "color": COLORS[0],
        },
        {
            "label": "Recall",
            "value": recall,
            "color": COLORS[1],
        },
        {
            "label": "F1 Score",
            "value": f1_score,
            "color": COLORS[2],
        },
        {
            "label": "mAP@50",
            "value": map50,
            "color": COLORS[3],
        },
    ]


@router.get("/top-diseases")
def get_top_diseases(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """
    获取热门疾病排行
    """
    last_30_days = datetime.now() - timedelta(days=30)
    last_60_days = datetime.now() - timedelta(days=60)

    current_distribution = (
        db.query(
            DetectionResult.class_name,
            DetectionResult.class_name_cn,
            func.count(DetectionResult.class_name),
        )
        .join(DetectionTask)
        .filter(
            DetectionTask.user_id == current_user.id,
            DetectionTask.created_at >= last_30_days,
        )
        .group_by(DetectionResult.class_name, DetectionResult.class_name_cn)
        .order_by(func.count(DetectionResult.class_name).desc())
        .limit(5)
        .all()
    )

    previous_distribution = (
        db.query(
            DetectionResult.class_name,
            func.count(DetectionResult.class_name),
        )
        .join(DetectionTask)
        .filter(
            DetectionTask.user_id == current_user.id,
            DetectionTask.created_at >= last_60_days,
            DetectionTask.created_at < last_30_days,
        )
        .group_by(DetectionResult.class_name)
        .all()
    )

    prev_dict = {name: count for name, count in previous_distribution}

    result = []
    max_count = 1

    for i, (class_name, class_name_cn, count) in enumerate(current_distribution):
        prev_count = prev_dict.get(class_name, 0)
        change = 0
        if prev_count > 0:
            change = round(((count - prev_count) / prev_count) * 100, 1)
        elif count > 0:
            change = 100

        if count > max_count:
            max_count = count

        result.append(
            {
                "name": class_name_cn or class_name,
                "count": count,
                "change": change,
                "color": COLORS[i],
                "max_count": max_count,
            }
        )

    for item in result:
        item["max_count"] = max_count

    return result
