"""
用户管理 API（管理员专用）

接口列表：
  - GET    /api/user/list           获取用户列表
  - POST   /api/user/create         创建用户
  - PUT    /api/user/{user_id}      编辑用户
  - DELETE /api/user/{user_id}      删除用户
"""

from fastapi import APIRouter, Depends, HTTPException, Path, Query
from sqlalchemy.orm import Session

from app.api.auth import require_admin
from app.database.session import get_db
from app.entity.db_models import Role, User, UserRole
from app.entity.schemas import ApiResponse
from app.services.user_service import user_service

router = APIRouter(prefix="/api/user", tags=["用户管理"])


def _is_admin(user: User) -> bool:
    return any(user_role.role.name == "admin" for user_role in user.user_roles)


def _active_admin_count(db: Session) -> int:
    users = db.query(User).filter(User.is_active.is_(True)).all()
    return sum(_is_admin(user) for user in users)


@router.get("/list", response_model=ApiResponse)
def list_users(
    db: Session = Depends(get_db),
    current_user=Depends(require_admin),
):
    """获取用户列表"""
    users = db.query(User).all()

    user_list = []
    for user in users:
        roles = [ur.role.name for ur in user.user_roles]
        user_list.append({
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "phone": user.phone,
            "avatar": user.avatar,
            "is_active": user.is_active,
            "roles": roles,
            "last_login_at": user.last_login_at,
            "created_at": user.created_at,
        })

    return ApiResponse(data=user_list)


@router.post("/create", response_model=ApiResponse)
def create_user(
    username: str = Query(..., description="用户名"),
    email: str = Query(..., description="邮箱"),
    password: str = Query(..., description="密码"),
    phone: str = Query(None, description="手机号"),
    db: Session = Depends(get_db),
    current_user=Depends(require_admin),
):
    """创建用户"""
    existing = db.query(User).filter((User.username == username) | (User.email == email)).first()
    if existing:
        raise HTTPException(status_code=400, detail="用户名或邮箱已存在")

    user = user_service.register(db=db, username=username, email=email, password=password)
    user.phone = phone

    db.commit()

    return ApiResponse(data={"id": user.id, "username": user.username, "email": user.email})


@router.put("/{user_id}", response_model=ApiResponse)
def update_user(
    user_id: int = Path(..., ge=1),
    username: str = Query(None, description="用户名"),
    email: str = Query(None, description="邮箱"),
    phone: str = Query(None, description="手机号"),
    avatar: str = Query(None, description="头像"),
    role_name: str = Query(None, description="角色（admin/user）"),
    db: Session = Depends(get_db),
    current_user=Depends(require_admin),
):
    """编辑用户"""
    user = user_service.get_user_by_id(db, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")

    if email:
        existing = db.query(User).filter(User.email == email, User.id != user_id).first()
        if existing:
            raise HTTPException(status_code=400, detail="邮箱已被使用")
        user.email = email

    if username:
        existing = db.query(User).filter(User.username == username, User.id != user_id).first()
        if existing:
            raise HTTPException(status_code=400, detail="用户名已被使用")
        user.username = username

    if phone is not None:
        user.phone = phone
    if avatar is not None:
        user.avatar = avatar

    if role_name:
        if role_name not in {"admin", "user"}:
            raise HTTPException(status_code=400, detail="角色仅支持 admin 或 user")
        if _is_admin(user) and role_name != "admin" and _active_admin_count(db) <= 1:
            raise HTTPException(status_code=400, detail="系统至少需要保留一个启用的管理员")
        user_service.assign_single_role(db, user, role_name)

    db.commit()
    return ApiResponse(message="更新成功")


@router.delete("/{user_id}", response_model=ApiResponse)
def delete_user(
    user_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
    current_user=Depends(require_admin),
):
    """禁用用户账户，保留其训练、检测和对话历史。"""
    if current_user.id == user_id:
        raise HTTPException(status_code=400, detail="不能删除自己")

    user = user_service.get_user_by_id(db, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")

    if _is_admin(user) and _active_admin_count(db) <= 1:
        raise HTTPException(status_code=400, detail="系统至少需要保留一个启用的管理员")

    user.is_active = False
    db.commit()
    return ApiResponse(message="账户已禁用")
