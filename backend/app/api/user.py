"""
用户管理 API 路由（管理员专用）
- GET    /api/user/list          用户列表查看
- POST   /api/user/create        创建用户
- PUT    /api/user/{user_id}     编辑用户（修改信息、分配角色）
- DELETE /api/user/{user_id}     删除用户
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.auth import require_admin
from app.database.session import get_db
from app.entity.db_models import User, Role, UserRole
from app.entity.schemas import ApiResponse, PageResponse
from app.core.security import hash_password


router = APIRouter(prefix="/api/user", tags=["用户管理"])


@router.get("/list", response_model=PageResponse, openapi_extra={"security": [{"BearerAuth": []}]})
def list_users(
    page: int = 1,
    page_size: int = 20,
    db: Session = Depends(get_db),
    current_user=Depends(require_admin),
):
    """
    用户列表查看（管理员专用）
    """
    query = db.query(User)
    total = query.count()
    users = (
        query.order_by(User.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

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

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": (total + page_size - 1) // page_size,
        "items": user_list,
    }


@router.post("/create", response_model=ApiResponse, status_code=201, openapi_extra={"security": [{"BearerAuth": []}]})
def create_user(
    username: str,
    email: str,
    password: str,
    phone: str = None,
    role_name: str = "user",
    db: Session = Depends(get_db),
    current_user=Depends(require_admin),
):
    """
    创建用户（管理员专用）
    """
    existing_user = db.query(User).filter(User.username == username).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="用户名已存在")

    existing_email = db.query(User).filter(User.email == email).first()
    if existing_email:
        raise HTTPException(status_code=400, detail="邮箱已被注册")

    role = db.query(Role).filter(Role.name == role_name).first()
    if not role:
        raise HTTPException(status_code=400, detail=f"角色不存在: {role_name}")

    new_user = User(
        username=username,
        email=email,
        hashed_password=hash_password(password),
        phone=phone,
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    user_role = UserRole(user_id=new_user.id, role_id=role.id)
    db.add(user_role)
    db.commit()

    return {
        "code": 201,
        "message": "用户创建成功",
        "data": {
            "id": new_user.id,
            "username": new_user.username,
            "email": new_user.email,
            "role": role_name,
        },
    }


@router.put("/{user_id}", response_model=ApiResponse, openapi_extra={"security": [{"BearerAuth": []}]})
def edit_user(
    user_id: int,
    email: str = None,
    phone: str = None,
    avatar: str = None,
    is_active: bool = None,
    role_name: str = None,
    db: Session = Depends(get_db),
    current_user=Depends(require_admin),
):
    """
    编辑用户（管理员专用）
    """
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")

    if email and email != user.email:
        existing = db.query(User).filter(User.email == email).first()
        if existing:
            raise HTTPException(status_code=400, detail="该邮箱已被其他用户使用")
        user.email = email

    if phone is not None:
        user.phone = phone
    if avatar is not None:
        user.avatar = avatar
    if is_active is not None:
        user.is_active = is_active

    if role_name:
        role = db.query(Role).filter(Role.name == role_name).first()
        if not role:
            raise HTTPException(status_code=400, detail=f"角色不存在: {role_name}")

        db.query(UserRole).filter(UserRole.user_id == user_id).delete()
        user_role = UserRole(user_id=user_id, role_id=role.id)
        db.add(user_role)

    db.commit()
    db.refresh(user)

    roles = [ur.role.name for ur in user.user_roles]

    return {
        "code": 200,
        "message": "用户信息更新成功",
        "data": {
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "phone": user.phone,
            "avatar": user.avatar,
            "is_active": user.is_active,
            "roles": roles,
        },
    }


@router.delete("/{user_id}", response_model=ApiResponse, openapi_extra={"security": [{"BearerAuth": []}]})
def delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(require_admin),
):
    """
    删除用户（管理员专用）
    """
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")

    if user.id == current_user.id:
        raise HTTPException(status_code=400, detail="不能删除自己")

    db.delete(user)
    db.commit()

    return {
        "code": 200,
        "message": "用户删除成功",
        "data": None,
    }
