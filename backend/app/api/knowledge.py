"""
知识库管理 API 路由

接口列表：
  - 普通用户接口：
    - POST /api/knowledge/documents    上传文档（待审核）
    - GET  /api/knowledge/documents    查看已发布文档列表
    - GET  /api/knowledge/documents/{id} 查看文档详情/预览
    - GET  /api/knowledge/my-submissions 查看我的投稿及审核状态
    - POST /api/knowledge/search       手动测试检索（只查已发布）
  
  - 管理员接口：
    - GET  /api/knowledge/admin/documents 全部文档列表（含筛选）
    - GET  /api/knowledge/admin/pending    待审核队列
    - PUT  /api/knowledge/admin/{id}/approve 审核通过（触发向量化）
    - PUT  /api/knowledge/admin/{id}/reject  驳回（填写原因）
    - DELETE /api/knowledge/admin/{id}      删除文档（同步删除向量）
    - POST /api/knowledge/admin/{id}/reindex 重新索引
    - POST /api/knowledge/build          构建/重建知识库索引
    - GET  /api/knowledge/stats          知识库统计信息
"""

import os
import re
import uuid
from datetime import datetime
from pathlib import PurePosixPath
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from pydantic import BaseModel

from app.api.auth import get_current_user, require_admin
from app.core.logger import get_logger
from app.database.session import SessionLocal
from app.entity.db_models import KnowledgeDocument
from app.rag.retriever import knowledge_retriever
from app.storage.minio_client import MinIOClient

logger = get_logger(__name__)

router = APIRouter(prefix="/api/knowledge", tags=["知识库管理"])

class SearchRequest(BaseModel):
    query: str
    top_k: int = 3


class DocumentQueryParams(BaseModel):
    status: Optional[str] = None
    page: int = 1
    page_size: int = 20


ALLOWED_KNOWLEDGE_EXTENSIONS = {".md", ".txt"}


def _safe_filename(filename: str) -> str:
    """生成适合保存到 MinIO object_name 的文件名片段。"""
    basename = PurePosixPath(filename.replace("\\", "/")).name
    return re.sub(r"[^A-Za-z0-9._-]", "_", basename).strip("._") or "document.txt"


def _knowledge_object_name(filename: str) -> str:
    """知识库文档统一放在固定前缀下，方便后续按目录管理。"""
    return f"knowledge/documents/{uuid.uuid4().hex}_{_safe_filename(filename)}"


def _content_type_for_extension(file_ext: str) -> str:
    if file_ext == ".md":
        return "text/markdown; charset=utf-8"
    return "text/plain; charset=utf-8"


async def _create_pending_document_from_upload(
    *,
    db,
    file: UploadFile,
    current_user,
    title: Optional[str] = None,
) -> dict:
    """
    保存上传文档到 MinIO，并创建待审核数据库记录。

    数据库 file_path 字段保存的是 MinIO object_name，不再保存本地磁盘路径。
    """
    original_filename = file.filename or "document.txt"
    file_ext = os.path.splitext(original_filename)[1].lower()
    if file_ext not in ALLOWED_KNOWLEDGE_EXTENSIONS:
        raise HTTPException(status_code=400, detail=f"不支持的文件类型，仅支持 {ALLOWED_KNOWLEDGE_EXTENSIONS}")

    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="上传文件不能为空")

    object_name = _knowledge_object_name(original_filename)
    minio_client = MinIOClient()
    try:
        minio_client.upload_bytes(
            object_name=object_name,
            data=data,
            content_type=_content_type_for_extension(file_ext),
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"文件上传到 MinIO 失败: {str(e)}")

    document_title = title or os.path.splitext(original_filename)[0]
    try:
        document = KnowledgeDocument(
            title=document_title,
            file_path=object_name,
            uploader_id=current_user.id,
            status="pending",
            visibility="public",
        )
        db.add(document)
        db.commit()
        db.refresh(document)
    except Exception:
        db.rollback()
        minio_client.delete_object(object_name)
        raise

    return {
        "filename": original_filename,
        "document_id": document.id,
        "title": document.title,
        "file_path": document.file_path,
        "status": document.status,
    }


def _read_document_content_from_minio(object_name: str) -> str:
    """读取知识库文档原文用于详情预览。"""
    data = MinIOClient().get_object(object_name)
    return data.decode("utf-8")


# ==============================================================================
# 普通用户接口
# ==============================================================================


@router.post("/documents", summary="上传文档（待审核）")
async def upload_document(
    file: UploadFile = File(...),
    title: Optional[str] = None,
    current_user=Depends(get_current_user),
):
    """
    普通用户上传文档，状态为待审核，不进入向量库
    
    Args:
        file: 文档文件（支持 .md, .txt）
        title: 文档标题（可选，未提供时从文件名提取）
    """
    db = SessionLocal()
    try:
        item = await _create_pending_document_from_upload(
            db=db,
            file=file,
            current_user=current_user,
            title=title,
        )
        logger.info("用户 %s 上传知识库文档到 MinIO: %s (id=%d)", current_user.username, item["title"], item["document_id"])
        
        return {
            "message": "文档上传成功，等待审核",
            "document_id": item["document_id"],
            "status": item["status"],
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"创建文档记录失败: {str(e)}")
    finally:
        db.close()


@router.post("/documents/batch", summary="批量上传文档（待审核）")
async def upload_documents_batch(
    files: list[UploadFile] = File(...),
    current_user=Depends(get_current_user),
):
    """
    一次上传多个知识库文档，每个文件单独创建一条待审核记录。

    单个文件失败不会中断其他文件处理，返回结果中会列出成功和失败明细。
    """
    if not files:
        raise HTTPException(status_code=400, detail="请至少上传一个文件")

    db = SessionLocal()
    items = []
    try:
        for file in files:
            try:
                item = await _create_pending_document_from_upload(
                    db=db,
                    file=file,
                    current_user=current_user,
                )
                items.append(item)
            except HTTPException as e:
                items.append({
                    "filename": file.filename or "document.txt",
                    "error": e.detail,
                })
            except Exception as e:
                items.append({
                    "filename": file.filename or "document.txt",
                    "error": f"创建文档记录失败: {str(e)}",
                })

        success_count = sum(1 for item in items if "document_id" in item)
        failed_count = len(items) - success_count
        logger.info("用户 %s 批量上传知识库文档: 成功 %d, 失败 %d", current_user.username, success_count, failed_count)
        return {
            "message": "文档上传完成",
            "total": len(items),
            "success_count": success_count,
            "failed_count": failed_count,
            "items": items,
        }
    finally:
        db.close()


@router.get("/documents", summary="查看已发布文档列表")
async def list_published_documents(
    current_user=Depends(get_current_user),
    page: int = 1,
    page_size: int = 20,
):
    """
    查看所有已发布的文档（status=approved）
    
    Args:
        page: 页码
        page_size: 每页数量
    """
    db = SessionLocal()
    try:
        query = db.query(KnowledgeDocument).filter(
            KnowledgeDocument.status == "approved",
            KnowledgeDocument.visibility == "public",
        )
        
        total = query.count()
        documents = query.offset((page - 1) * page_size).limit(page_size).all()
        
        results = []
        for doc in documents:
            results.append({
                "id": doc.id,
                "title": doc.title,
                "file_path": doc.file_path,
                "uploader_id": doc.uploader_id,
                "uploader_name": doc.uploader.username if doc.uploader else None,
                "status": doc.status,
                "reviewer_id": doc.reviewer_id,
                "reviewer_name": doc.reviewer.username if doc.reviewer else None,
                "review_comment": doc.review_comment,
                "reviewed_at": doc.reviewed_at,
                "visibility": doc.visibility,
                "chunk_count": doc.chunk_count,
                "created_at": doc.created_at,
                "updated_at": doc.updated_at,
            })
        
        return {
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": (total + page_size - 1) // page_size,
            "items": results,
        }
    finally:
        db.close()


@router.get("/documents/{document_id}", summary="查看文档详情/预览")
async def get_document_detail(
    document_id: int,
    current_user=Depends(get_current_user),
):
    """
    查看文档详情，普通用户只能查看已发布文档
    """
    db = SessionLocal()
    try:
        document = db.query(KnowledgeDocument).filter(
            KnowledgeDocument.id == document_id
        ).first()
        
        if not document:
            raise HTTPException(status_code=404, detail="文档不存在")
        
        # 普通用户只能查看已发布文档，管理员可以查看所有
        roles = [ur.role.name for ur in current_user.user_roles]
        is_admin = "admin" in roles
        
        if not is_admin and document.status != "approved":
            raise HTTPException(status_code=403, detail="无权访问该文档")
        
        # 从 MinIO 读取文档内容用于预览；读取失败不影响元信息展示。
        content = ""
        try:
            content = _read_document_content_from_minio(document.file_path)
        except Exception as e:
            logger.warning("读取知识库文档预览失败: id=%d, path=%s, error=%s", document.id, document.file_path, str(e))
        
        return {
            "id": document.id,
            "title": document.title,
            "file_path": document.file_path,
            "content": content,
            "uploader_id": document.uploader_id,
            "uploader_name": document.uploader.username if document.uploader else None,
            "status": document.status,
            "reviewer_id": document.reviewer_id,
            "reviewer_name": document.reviewer.username if document.reviewer else None,
            "review_comment": document.review_comment,
            "reviewed_at": document.reviewed_at,
            "visibility": document.visibility,
            "chunk_count": document.chunk_count,
            "created_at": document.created_at,
            "updated_at": document.updated_at,
        }
    finally:
        db.close()


@router.get("/my-submissions", summary="查看我的投稿")
async def list_my_submissions(
    current_user=Depends(get_current_user),
    page: int = 1,
    page_size: int = 20,
):
    """
    查看当前用户的投稿记录及审核状态
    """
    db = SessionLocal()
    try:
        query = db.query(KnowledgeDocument).filter(
            KnowledgeDocument.uploader_id == current_user.id
        )
        
        total = query.count()
        documents = query.order_by(KnowledgeDocument.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()
        
        results = []
        for doc in documents:
            results.append({
                "id": doc.id,
                "title": doc.title,
                "file_path": doc.file_path,
                "status": doc.status,
                "review_comment": doc.review_comment,
                "reviewed_at": doc.reviewed_at,
                "created_at": doc.created_at,
                "updated_at": doc.updated_at,
            })
        
        return {
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": (total + page_size - 1) // page_size,
            "items": results,
        }
    finally:
        db.close()


@router.post("/search", summary="测试检索")
async def search_knowledge(
    request: SearchRequest,
    current_user=Depends(get_current_user),
):
    """手动测试知识库检索（只检索已发布文档）"""
    results = knowledge_retriever.search(request.query, top_k=request.top_k)
    return {
        "query": request.query,
        "results": results,
        "count": len(results),
    }


# ==============================================================================
# 管理员接口
# ==============================================================================


@router.get("/admin/documents", summary="全部文档列表（管理员）")
async def list_all_documents(
    status: Optional[str] = None,
    current_user=Depends(require_admin),
    page: int = 1,
    page_size: int = 20,
):
    """
    管理员查看全部文档列表，支持按状态筛选
    
    Args:
        status: 状态筛选（pending/approved/rejected/processing/failed）
    """
    db = SessionLocal()
    try:
        query = db.query(KnowledgeDocument)
        
        if status:
            query = query.filter(KnowledgeDocument.status == status)
        
        total = query.count()
        documents = query.order_by(KnowledgeDocument.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()
        
        results = []
        for doc in documents:
            results.append({
                "id": doc.id,
                "title": doc.title,
                "file_path": doc.file_path,
                "uploader_id": doc.uploader_id,
                "uploader_name": doc.uploader.username if doc.uploader else None,
                "status": doc.status,
                "reviewer_id": doc.reviewer_id,
                "reviewer_name": doc.reviewer.username if doc.reviewer else None,
                "review_comment": doc.review_comment,
                "reviewed_at": doc.reviewed_at,
                "visibility": doc.visibility,
                "chunk_count": doc.chunk_count,
                "created_at": doc.created_at,
                "updated_at": doc.updated_at,
            })
        
        return {
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": (total + page_size - 1) // page_size,
            "items": results,
        }
    finally:
        db.close()


@router.get("/admin/pending", summary="待审核队列（管理员）")
async def list_pending_documents(
    current_user=Depends(require_admin),
    page: int = 1,
    page_size: int = 20,
):
    """
    管理员查看待审核文档队列
    """
    db = SessionLocal()
    try:
        query = db.query(KnowledgeDocument).filter(
            KnowledgeDocument.status == "pending"
        )
        
        total = query.count()
        documents = query.order_by(KnowledgeDocument.created_at.asc()).offset((page - 1) * page_size).limit(page_size).all()
        
        results = []
        for doc in documents:
            results.append({
                "id": doc.id,
                "title": doc.title,
                "file_path": doc.file_path,
                "uploader_id": doc.uploader_id,
                "uploader_name": doc.uploader.username if doc.uploader else None,
                "status": doc.status,
                "created_at": doc.created_at,
            })
        
        return {
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": (total + page_size - 1) // page_size,
            "items": results,
        }
    finally:
        db.close()


@router.put("/admin/{document_id}/approve", summary="审核通过（管理员）")
async def approve_document(
    document_id: int,
    current_user=Depends(require_admin),
):
    """
    管理员审核通过文档，触发向量化并写入向量库
    
    流程：更新状态为processing → 解析文档 → 分块 → Embedding → 写入向量库 → 更新状态为approved
    """
    db = SessionLocal()
    try:
        document = db.query(KnowledgeDocument).filter(
            KnowledgeDocument.id == document_id
        ).first()
        
        if not document:
            raise HTTPException(status_code=404, detail="文档不存在")
        
        if document.status != "pending":
            raise HTTPException(status_code=400, detail=f"文档当前状态为 {document.status}，无法审核")
        
        # 更新状态为处理中
        document.status = "processing"
        document.reviewer_id = current_user.id
        document.reviewed_at = datetime.now()
        db.commit()
        
        # 构建索引
        chunk_count = knowledge_retriever.index_document(
            document_id=document.id,
            file_path=document.file_path,
            title=document.title,
        )
        
        if chunk_count > 0:
            document.status = "approved"
            document.chunk_count = chunk_count
            db.commit()
            logger.info("管理员 %s 审核通过文档: %s (id=%d)", current_user.username, document.title, document.id)
            return {"message": "文档审核通过，已加入知识库", "document_id": document.id, "status": "approved"}
        else:
            # 索引构建失败，回滚状态
            document.status = "failed"
            document.review_comment = "文档索引构建失败"
            db.commit()
            logger.error("文档 %d 索引构建失败", document.id)
            raise HTTPException(status_code=500, detail="文档索引构建失败，请重试")
    
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error("审核文档失败: %s", str(e))
        raise HTTPException(status_code=500, detail=f"审核失败: {str(e)}")
    finally:
        db.close()


@router.put("/admin/{document_id}/reject", summary="驳回文档（管理员）")
async def reject_document(
    document_id: int,
    review_comment: str,
    current_user=Depends(require_admin),
):
    """
    管理员驳回文档，填写驳回原因
    """
    db = SessionLocal()
    try:
        document = db.query(KnowledgeDocument).filter(
            KnowledgeDocument.id == document_id
        ).first()
        
        if not document:
            raise HTTPException(status_code=404, detail="文档不存在")
        
        if document.status != "pending":
            raise HTTPException(status_code=400, detail=f"文档当前状态为 {document.status}，无法驳回")
        
        document.status = "rejected"
        document.reviewer_id = current_user.id
        document.review_comment = review_comment
        document.reviewed_at = datetime.now()
        db.commit()
        
        logger.info("管理员 %s 驳回文档: %s (id=%d)", current_user.username, document.title, document.id)
        return {"message": "文档已驳回", "document_id": document.id, "status": "rejected"}
    
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error("驳回文档失败: %s", str(e))
        raise HTTPException(status_code=500, detail=f"驳回失败: {str(e)}")
    finally:
        db.close()


@router.delete("/admin/{document_id}", summary="删除文档（管理员）")
async def delete_document(
    document_id: int,
    current_user=Depends(require_admin),
):
    """
    管理员删除文档，同步删除向量库中的对应向量
    """
    db = SessionLocal()
    try:
        document = db.query(KnowledgeDocument).filter(
            KnowledgeDocument.id == document_id
        ).first()
        
        if not document:
            raise HTTPException(status_code=404, detail="文档不存在")
        
        # 删除向量库中的向量
        deleted_count = knowledge_retriever.delete_document_index(document_id)
        logger.info("删除文档 %d 的向量: %d 条", document_id, deleted_count)
        
        # 删除 MinIO 原文对象。delete_object 内部会忽略对象不存在的情况。
        MinIOClient().delete_object(document.file_path)
        
        # 删除数据库记录
        db.delete(document)
        db.commit()
        
        logger.info("管理员 %s 删除文档: %s (id=%d)", current_user.username, document.title, document.id)
        return {"message": "文档已删除", "document_id": document_id, "deleted_vectors": deleted_count}
    
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error("删除文档失败: %s", str(e))
        raise HTTPException(status_code=500, detail=f"删除失败: {str(e)}")
    finally:
        db.close()


@router.post("/admin/{document_id}/reindex", summary="重新索引（管理员）")
async def reindex_document(
    document_id: int,
    current_user=Depends(require_admin),
):
    """
    管理员重新索引文档（先删除旧向量，再重建）
    """
    db = SessionLocal()
    try:
        document = db.query(KnowledgeDocument).filter(
            KnowledgeDocument.id == document_id
        ).first()
        
        if not document:
            raise HTTPException(status_code=404, detail="文档不存在")
        
        if document.status != "approved":
            raise HTTPException(status_code=400, detail="只有已发布的文档才能重新索引")
        
        # 删除旧向量
        deleted_count = knowledge_retriever.delete_document_index(document_id)
        logger.info("删除文档 %d 的旧向量: %d 条", document_id, deleted_count)
        
        # 重建索引
        chunk_count = knowledge_retriever.index_document(
            document_id=document.id,
            file_path=document.file_path,
            title=document.title,
        )
        
        if chunk_count > 0:
            document.chunk_count = chunk_count
            db.commit()
            logger.info("管理员 %s 重新索引文档: %s (id=%d)", current_user.username, document.title, document.id)
            return {"message": "文档重新索引完成", "document_id": document.id}
        else:
            logger.error("文档 %d 重新索引失败", document.id)
            raise HTTPException(status_code=500, detail="重新索引失败")
    
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error("重新索引文档失败: %s", str(e))
        raise HTTPException(status_code=500, detail=f"重新索引失败: {str(e)}")
    finally:
        db.close()


# ==============================================================================
# 原有接口（保留）
# ==============================================================================


@router.post("/build", summary="构建知识库索引")
async def build_index(
    force_rebuild: bool = False,
    _current_user=Depends(require_admin),
):
    """管理员按已发布文档重建知识库索引。"""
    db = SessionLocal()
    try:
        stats = knowledge_retriever.rebuild_approved_documents(db, force_rebuild=force_rebuild)
    finally:
        db.close()

    if not stats.get("success") or stats.get("total_chunks", 0) <= 0:
        raise HTTPException(status_code=503, detail={"message": "知识库索引构建失败", "stats": stats})
    return {"message": "知识库索引构建完成", "stats": stats}


@router.get("/stats", summary="知识库统计")
async def get_stats(current_user=Depends(get_current_user)):
    """获取知识库统计信息"""
    return knowledge_retriever.get_stats()
