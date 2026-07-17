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
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from pydantic import BaseModel

from app.api.auth import get_current_user, require_admin
from app.core.logger import get_logger
from app.database.session import SessionLocal
from app.entity.db_models import KnowledgeDocument
from app.entity.schemas import KnowledgeDocumentResponse
from app.rag.retriever import knowledge_retriever

logger = get_logger(__name__)

router = APIRouter(prefix="/api/knowledge", tags=["知识库管理"])

# 知识库文档上传目录
KNOWLEDGE_UPLOAD_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))),
    "knowledge_base",
)


class SearchRequest(BaseModel):
    query: str
    top_k: int = 3


class DocumentQueryParams(BaseModel):
    status: Optional[str] = None
    page: int = 1
    page_size: int = 20


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
    # 检查文件类型
    allowed_extensions = {".md", ".txt"}
    file_ext = os.path.splitext(file.filename)[1].lower()
    if file_ext not in allowed_extensions:
        raise HTTPException(status_code=400, detail=f"不支持的文件类型，仅支持 {allowed_extensions}")

    # 确保上传目录存在
    os.makedirs(KNOWLEDGE_UPLOAD_DIR, exist_ok=True)
    
    # 生成文件名（避免重复）
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{timestamp}_{file.filename}"
    file_path = os.path.join(KNOWLEDGE_UPLOAD_DIR, filename)

    # 保存文件
    try:
        with open(file_path, "wb") as f:
            f.write(await file.read())
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"文件保存失败: {str(e)}")

    # 如果未提供标题，从文件名提取
    if not title:
        title = os.path.splitext(file.filename)[0]

    # 创建数据库记录
    db = SessionLocal()
    try:
        document = KnowledgeDocument(
            title=title,
            file_path=file_path,
            uploader_id=current_user.id,
            status="pending",
            visibility="public",
        )
        db.add(document)
        db.commit()
        db.refresh(document)
        logger.info("用户 %s 上传文档: %s (id=%d)", current_user.username, title, document.id)
        
        return {
            "message": "文档上传成功，等待审核",
            "document_id": document.id,
            "status": "pending",
        }
    except Exception as e:
        db.rollback()
        # 删除已保存的文件
        if os.path.exists(file_path):
            os.remove(file_path)
        raise HTTPException(status_code=500, detail=f"创建文档记录失败: {str(e)}")
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
        
        # 读取文档内容用于预览
        content = ""
        if os.path.exists(document.file_path):
            with open(document.file_path, "r", encoding="utf-8") as f:
                content = f.read()
        
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
        success = knowledge_retriever.index_document(
            document_id=document.id,
            file_path=document.file_path,
            title=document.title,
        )
        
        if success:
            # 获取分块数量
            chunk_count = knowledge_retriever.get_stats().get("total_chunks", 0)
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
        
        # 删除文件
        if os.path.exists(document.file_path):
            os.remove(document.file_path)
        
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
        success = knowledge_retriever.index_document(
            document_id=document.id,
            file_path=document.file_path,
            title=document.title,
        )
        
        if success:
            chunk_count = knowledge_retriever.get_stats().get("total_chunks", 0)
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
    current_user=Depends(get_current_user),
):
    """构建或重建知识库索引"""
    success = knowledge_retriever.build_index(force_rebuild=force_rebuild)
    stats = knowledge_retriever.get_stats()
    if not success or stats["total_chunks"] <= 0:
        raise HTTPException(status_code=503, detail={"message": "知识库索引构建失败", "stats": stats})
    return {"message": "知识库索引构建完成", "stats": stats}


@router.get("/stats", summary="知识库统计")
async def get_stats(current_user=Depends(get_current_user)):
    """获取知识库统计信息"""
    return knowledge_retriever.get_stats()