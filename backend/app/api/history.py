"""
检测历史记录 API 路由

接口列表：
  - GET    /api/history/severity-questions                     严重程度问卷配置
  - GET    /api/history/tasks                                  检测任务分页列表
  - GET    /api/history/tasks/{task_id}                        检测任务详情（含结果列表）
  - PATCH  /api/history/tasks/{task_id}/location               更新检测任务地理位置
  - GET    /api/history/tasks/{task_id}/weather-risk           刷新天气环境风险
  - GET    /api/history/tasks/{task_id}/report                 检测报告预览
  - GET    /api/history/tasks/{task_id}/report/download        下载检测报告
  - POST   /api/history/tasks/{task_id}/severity-assessment    提交病害严重程度评估
  - PATCH  /api/history/tasks/{task_id}/treatment-status       更新治疗状态
  - DELETE /api/history/tasks/{task_id}                        删除检测任务（级联删除结果）
  - GET    /api/history/summary                                历史记录快速统计
  - GET    /api/history/scenes                                 获取所有检测场景列表
"""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from fastapi.responses import JSONResponse

from app.api.auth import get_current_user
from app.core.language import request_language
from app.core.logger import get_logger
from app.entity.schemas import (
    DetectionTaskLocationUpdate,
    SeverityAssessmentRequest,
    TreatmentStatusUpdate,
)
from app.services.history_service import history_service

logger = get_logger(__name__)

router = APIRouter(prefix="/api/history", tags=["检测历史"])


@router.get("/severity-questions", summary="严重程度问卷配置")
async def get_severity_questions(
    request: Request,
    current_user=Depends(get_current_user),
):
    """返回前端可直接渲染的严重程度问卷问题和选项。"""
    return history_service.get_severity_questions(
        display_language=request_language(request, current_user)
    )


@router.get("/tasks", summary="检测任务分页列表")
async def list_detection_tasks(
    request: Request,
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(10, ge=1, le=100, description="每页数量"),
    task_type: Optional[str] = Query(None, description="任务类型筛选"),
    status: Optional[str] = Query(None, description="状态筛选"),
    scene_id: Optional[int] = Query(None, description="场景 ID 筛选"),
    start_date: Optional[str] = Query(None, description="起始日期 YYYY-MM-DD"),
    end_date: Optional[str] = Query(None, description="结束日期 YYYY-MM-DD"),
    keyword: Optional[str] = Query(None, description="关键词搜索"),
    risk_level: Optional[str] = Query(None, description="严重程度筛选"),
    treatment_status: Optional[str] = Query(None, description="治疗状态筛选"),
    plant_name: Optional[str] = Query(None, description="植物名称筛选"),
    class_name: Optional[str] = Query(None, description="检测类别筛选"),
    current_user=Depends(get_current_user),
):
    """
    分页查询当前用户的检测任务列表

    支持按类型、状态、场景、日期范围筛选
    """
    return history_service.list_tasks(
        user_id=current_user.id,
        page=page,
        page_size=page_size,
        task_type=task_type,
        status=status,
        scene_id=scene_id,
        start_date=start_date,
        end_date=end_date,
        keyword=keyword,
        risk_level=risk_level,
        treatment_status=treatment_status,
        plant_name=plant_name,
        class_name=class_name,
        display_language=request_language(request, current_user),
    )


@router.get("/tasks/{task_id}", summary="检测任务详情")
async def get_detection_task_detail(
    task_id: int,
    request: Request,
    current_user=Depends(get_current_user),
):
    """
    获取检测任务详情，包含完整的结果列表

    返回：任务基本信息 + 每条检测结果（类别、置信度、边界框）
    """
    result = history_service.get_task_detail(
        user_id=current_user.id,
        task_id=task_id,
        display_language=request_language(request, current_user),
    )
    if not result:
        return JSONResponse(
            status_code=404,
            content={"error": "任务不存在或无权访问"},
        )
    return result


@router.patch("/tasks/{task_id}/location", summary="更新检测任务地理位置")
async def update_task_location(
    task_id: int,
    payload: DetectionTaskLocationUpdate,
    refresh_weather: bool = Query(True, description="保存位置后是否立即刷新天气环境风险"),
    current_user=Depends(get_current_user),
):
    """保存用户授权定位或手动填写的位置，并按需立即刷新天气风险。"""
    result = history_service.update_task_location(
        user_id=current_user.id,
        task_id=task_id,
        latitude=payload.latitude,
        longitude=payload.longitude,
        location_name=payload.location_name,
        location_source=payload.location_source,
    )
    if result is None:
        raise HTTPException(status_code=404, detail="任务不存在或无权访问")
    if refresh_weather:
        weather_result = history_service.refresh_weather_risk(
            user_id=current_user.id,
            task_id=task_id,
        )
        if weather_result is None:
            raise HTTPException(status_code=404, detail="任务不存在或无权访问")
        if isinstance(weather_result, dict) and weather_result.get("error"):
            raise HTTPException(
                status_code=weather_result.get("status_code", 400),
                detail=weather_result["error"],
            )
        result.update(
            {
                "environment_risk_level": weather_result.get("environment_risk_level"),
                "weather_summary": weather_result.get("weather_summary"),
                "weather_recommendations": weather_result.get("weather_recommendations"),
                "weather_metrics": weather_result.get("weather_metrics"),
                "weather_reasons": weather_result.get("reasons"),
                "weather_updated_at": weather_result.get("weather_updated_at"),
                "llm_model": weather_result.get("llm_model"),
            }
        )
    return result


@router.get("/tasks/{task_id}/weather-risk", summary="刷新天气环境风险")
async def refresh_weather_risk(
    task_id: int,
    current_user=Depends(get_current_user),
):
    """根据任务经纬度调用天气服务，生成病害扩散环境风险和建议。"""
    result = history_service.refresh_weather_risk(
        user_id=current_user.id,
        task_id=task_id,
    )
    if result is None:
        raise HTTPException(status_code=404, detail="任务不存在或无权访问")
    if isinstance(result, dict) and result.get("error"):
        raise HTTPException(
            status_code=result.get("status_code", 400),
            detail=result["error"],
        )
    return result


@router.get("/tasks/{task_id}/report", summary="检测报告预览")
async def get_task_report(
    task_id: int,
    request: Request,
    current_user=Depends(get_current_user),
):
    """返回报告 JSON 预览，供前端展示或确认导出内容。"""
    result = history_service.get_task_report(
        user_id=current_user.id,
        task_id=task_id,
        display_language=request_language(request, current_user),
    )
    if result is None:
        raise HTTPException(status_code=404, detail="任务不存在或无权访问")
    return result


@router.get("/tasks/{task_id}/report/download", summary="下载检测报告")
async def download_task_report(
    task_id: int,
    request: Request,
    format: str = Query("pdf", pattern="^(html|pdf)$", description="导出格式，默认 PDF"),
    current_user=Depends(get_current_user),
):
    """下载 HTML 或 PDF 报告；PDF 依赖 reportlab。"""
    try:
        result = history_service.export_task_report(
            user_id=current_user.id,
            task_id=task_id,
            report_format=format,
            display_language=request_language(request, current_user),
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    if result is None:
        raise HTTPException(status_code=404, detail="任务不存在或无权访问")
    return Response(
        content=result["content"],
        media_type=result["media_type"],
        headers={
            "Content-Disposition": f'attachment; filename="{result["filename"]}"'
        },
    )


@router.post("/tasks/{task_id}/severity-assessment", summary="提交病害严重程度评估")
async def create_severity_assessment(
    task_id: int,
    payload: SeverityAssessmentRequest,
    request: Request,
    current_user=Depends(get_current_user),
):
    """
    基于检测结果和用户问卷评估病害严重程度。

    YOLO 置信度不等同于病害严重程度，后端只把检测类别和目标数量作为背景信息。
    """
    result = history_service.create_severity_assessment(
        user_id=current_user.id,
        task_id=task_id,
        class_name=payload.class_name,
        answers=payload.answers,
        additional_notes=payload.additional_notes,
        display_language=request_language(request, current_user),
    )
    if result is None:
        raise HTTPException(status_code=404, detail="任务不存在或无权访问")
    if isinstance(result, dict) and result.get("error"):
        raise HTTPException(
            status_code=result.get("status_code", 400),
            detail=result["error"],
        )
    return result


@router.patch("/tasks/{task_id}/treatment-status", summary="更新治疗状态")
async def update_treatment_status(
    task_id: int,
    payload: TreatmentStatusUpdate,
    current_user=Depends(get_current_user),
):
    """用户手动维护治疗状态；该状态独立于检测任务 completed/failed。"""
    result = history_service.update_treatment_status(
        user_id=current_user.id,
        task_id=task_id,
        status=payload.status,
        note=payload.note,
    )
    if result is None:
        raise HTTPException(status_code=404, detail="任务不存在或无权访问")
    return result


@router.delete("/tasks/{task_id}", summary="删除检测任务")
async def delete_detection_task(
    task_id: int,
    current_user=Depends(get_current_user),
):
    """
    删除检测任务及其关联的检测结果（级联删除）

    仅允许删除自己的任务
    """
    success = history_service.delete_task(
        user_id=current_user.id,
        task_id=task_id,
    )
    if not success:
        return JSONResponse(
            status_code=404,
            content={"error": "任务不存在或无权访问"},
        )
    logger.info("用户 %s 删除检测任务 #%d", current_user.username, task_id)
    return {"message": f"任务 #{task_id} 已删除", "task_id": task_id}


@router.get("/summary", summary="历史记录快速统计")
async def get_history_summary(
    current_user=Depends(get_current_user),
):
    """
    快速获取当前用户的检测历史摘要

    返回：总任务数、各状态任务数、今日任务数
    """
    return history_service.get_summary(user_id=current_user.id)


@router.get("/scenes", summary="获取所有检测场景列表")
async def list_scenes(
    _current_user=Depends(get_current_user),
):
    """获取所有可用的检测场景（用于筛选下拉框）"""
    scenes = history_service.list_scenes()
    return {"scenes": scenes}