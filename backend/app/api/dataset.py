"""
数据集管理模块 API

功能：
- 数据集上传
- 自动解析YOLO格式
- 图片浏览
- 标签查看
- 类别统计
- 数据导出
- 系统自动统计
"""

from typing import List, Optional

from fastapi import APIRouter, Depends, File, UploadFile, Query, Path, Response
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.services.dataset_service import dataset_service
from app.entity.schemas import (
    DatasetCreate,
    DatasetResponse,
    DatasetImageResponse,
    DatasetLabelResponse,
    DatasetStatistics,
    DatasetSplitRequest,
    DiseaseClassResponse,
    PageResponse,
    ApiResponse,
)

router = APIRouter(prefix="/api/dataset", tags=["数据集管理"])


@router.post("/create", response_model=ApiResponse)
def create_dataset(
    data: DatasetCreate,
    db: Session = Depends(get_db),
):
    """创建数据集"""
    dataset = dataset_service.create_dataset(
        db=db,
        name=data.name,
        display_name=data.display_name,
        description=data.description,
        category=data.category,
        format_type=data.format_type,
        user_id=1,
    )
    return ApiResponse(data=DatasetResponse.from_orm(dataset).dict())


@router.get("/list", response_model=PageResponse)
def list_datasets(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """分页查询数据集列表"""
    datasets, total = dataset_service.list_datasets(
        db=db, page=page, page_size=page_size, user_id=1
    )
    return PageResponse(
        total=total,
        page=page,
        page_size=page_size,
        total_pages=(total + page_size - 1) // page_size,
        items=[DatasetResponse.from_orm(d) for d in datasets],
    )


@router.get("/detail/{dataset_id}", response_model=DatasetResponse)
def get_dataset_detail(
    dataset_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
):
    """获取数据集详情"""
    dataset = dataset_service.get_dataset(db=db, dataset_id=dataset_id)
    return DatasetResponse.from_orm(dataset)


@router.post("/{dataset_id}/upload/images", response_model=ApiResponse)
def upload_images(
    dataset_id: int = Path(..., ge=1),
    images: List[UploadFile] = File(...),
    db: Session = Depends(get_db),
):
    """上传图片"""
    result = dataset_service.upload_images(db=db, dataset_id=dataset_id, images=images, user_id=1)
    return ApiResponse(data=result)


@router.post("/{dataset_id}/upload/labels", response_model=ApiResponse)
def upload_labels(
    dataset_id: int = Path(..., ge=1),
    labels: List[UploadFile] = File(...),
    db: Session = Depends(get_db),
):
    """上传标签文件"""
    result = dataset_service.upload_labels(db=db, dataset_id=dataset_id, labels=labels, user_id=1)
    return ApiResponse(data=result)


@router.post("/{dataset_id}/convert", response_model=ApiResponse)
def convert_yolo(
    dataset_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
):
    """转换YOLO格式（自动解析）"""
    result = dataset_service.auto_parse_yolo(db=db, dataset_id=dataset_id, user_id=1)
    return ApiResponse(data=result)


@router.get("/{dataset_id}/images", response_model=PageResponse, summary="获取图片列表")
def get_images(
    dataset_id: int = Path(..., ge=1),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    split_type: Optional[str] = Query(None, regex="^(train|val|test)$"),
    has_label: Optional[bool] = Query(None),
    db: Session = Depends(get_db),
):
    """分页查询图片列表"""
    images, total = dataset_service.get_images(
        db=db,
        dataset_id=dataset_id,
        page=page,
        page_size=page_size,
        split_type=split_type,
        has_label=has_label,
        user_id=1,
    )
    return PageResponse(
        total=total,
        page=page,
        page_size=page_size,
        total_pages=(total + page_size - 1) // page_size,
        items=[DatasetImageResponse.from_orm(img) for img in images],
    )


@router.get("/images/{image_id}", response_model=DatasetImageResponse, summary="获取单张图片详情")
def get_image(
    image_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
):
    """获取单张图片详情"""
    image = dataset_service.get_image(db=db, image_id=image_id, user_id=1)
    return DatasetImageResponse.from_orm(image)


@router.delete("/images/{image_id}", response_model=ApiResponse)
def delete_image(
    image_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
):
    """删除图片"""
    dataset_service.delete_image(db=db, image_id=image_id, user_id=1)
    return ApiResponse(message="删除成功")


@router.get("/{dataset_id}/labels", response_model=PageResponse)
def get_labels(
    dataset_id: int = Path(..., ge=1),
    image_id: Optional[int] = Query(None, ge=1),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """查询标签列表"""
    labels, total = dataset_service.get_labels(
        db=db,
        dataset_id=dataset_id,
        image_id=image_id,
        page=page,
        page_size=page_size,
        user_id=1,
    )
    return PageResponse(
        total=total,
        page=page,
        page_size=page_size,
        total_pages=(total + page_size - 1) // page_size,
        items=[DatasetLabelResponse.from_orm(label) for label in labels],
    )


@router.get("/{dataset_id}/statistics", response_model=ApiResponse)
def get_statistics(
    dataset_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
):
    """获取数据集统计信息"""
    stats = dataset_service.get_class_statistics(db=db, dataset_id=dataset_id, user_id=1)
    return ApiResponse(data=stats)


@router.get("/{dataset_id}/summary", response_model=DatasetStatistics)
def get_dataset_summary(
    dataset_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
):
    """获取数据集摘要统计"""
    dataset = dataset_service.get_dataset(db=db, dataset_id=dataset_id)
    return DatasetStatistics(
        total_images=dataset.total_images,
        total_labels=dataset.total_labels,
        total_classes=dataset.total_classes,
        class_distribution=dataset.class_distribution or {},
        train_count=dataset.train_count,
        val_count=dataset.val_count,
        test_count=dataset.test_count,
        data_size=dataset.data_size,
        label_quality=dataset.label_quality or 0.0,
    )


@router.post("/{dataset_id}/split", response_model=ApiResponse)
def split_dataset(
    dataset_id: int = Path(..., ge=1),
    data: DatasetSplitRequest = Depends(),
    db: Session = Depends(get_db),
):
    """自动划分数据集"""
    result = dataset_service.split_dataset(
        db=db,
        dataset_id=dataset_id,
        train_ratio=data.train_ratio,
        val_ratio=data.val_ratio,
        user_id=1,
    )
    return ApiResponse(data=result)


@router.post("/{dataset_id}/export")
def export_dataset(
    dataset_id: int = Path(..., ge=1),
    format_type: str = Query("yolo", regex="^(yolo)$"),
    split_type: str = Query("all", regex="^(all|train|val|test)$"),
    db: Session = Depends(get_db),
):
    """导出数据集"""
    zip_path = dataset_service.export_dataset(
        db=db,
        dataset_id=dataset_id,
        format_type=format_type,
        split_type=split_type,
        user_id=1,
    )

    import os

    with open(zip_path, "rb") as f:
        content = f.read()

    os.remove(zip_path)

    return Response(
        content=content,
        media_type="application/zip",
        headers={"Content-Disposition": f"attachment; filename=dataset_{dataset_id}.zip"},
    )


@router.get("/disease/class", response_model=List[DiseaseClassResponse])
def get_disease_classes():
    """获取病害类别列表"""
    classes = dataset_service.get_disease_classes()
    return [
        DiseaseClassResponse(
            class_id=c["class_id"],
            class_name=c["class_name"],
            class_name_cn=c["class_name_cn"],
        )
        for c in classes
    ]


@router.delete("/{dataset_id}", response_model=ApiResponse)
def delete_dataset(
    dataset_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
):
    """删除数据集"""
    dataset_service.delete_dataset(db=db, dataset_id=dataset_id, user_id=1)
    return ApiResponse(message="删除成功")


@router.post("/{dataset_id}/upload/zip", response_model=ApiResponse)
def upload_dataset_zip(
    dataset_id: int = Path(..., ge=1),
    zip_file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    """
    上传数据集压缩包并自动解析 YOLO 格式

    支持的压缩包结构：
    - train/images/*.jpg
    - train/labels/*.txt
    - val/images/*.jpg
    - val/labels/*.txt
    - test/images/*.jpg
    - test/labels/*.txt
    """
    if not zip_file.filename.endswith(".zip"):
        return ApiResponse(code=400, message="只支持 zip 格式的压缩包")

    try:
        result = dataset_service.upload_dataset_zip(
            db=db,
            dataset_id=dataset_id,
            zip_file=zip_file,
            user_id=1,
        )
        return ApiResponse(data=result)
    except Exception as e:
        import traceback
        print(f"Zip upload error: {e}")
        traceback.print_exc()
        return ApiResponse(code=500, message=f"上传失败: {str(e)}")