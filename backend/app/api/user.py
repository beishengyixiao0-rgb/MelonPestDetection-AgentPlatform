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
            "is_superuser": user.is_superuser,
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

    role = db.query(Role).filter(Role.name == "user").first()
    if role:
        existing_ur = db.query(UserRole).filter(
            UserRole.user_id == user.id,
            UserRole.role_id == role.id
        ).first()
        if not existing_ur:
            db.add(UserRole(user_id=user.id, role_id=role.id))

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
        role = db.query(Role).filter(Role.name == role_name).first()
        if not role:
            raise HTTPException(status_code=400, detail=f"角色 {role_name} 不存在")

        db.query(UserRole).filter(UserRole.user_id == user_id).delete()
        db.add(UserRole(user_id=user_id, role_id=role.id))

    db.commit()
    return ApiResponse(message="更新成功")


@router.delete("/{user_id}", response_model=ApiResponse)
def delete_user(
    user_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
    current_user=Depends(require_admin),
):
    """删除用户"""
    if current_user.id == user_id:
        raise HTTPException(status_code=400, detail="不能删除自己")

    user = user_service.get_user_by_id(db, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")

    db.delete(user)
    db.commit()
    return ApiResponse(message="删除成功")