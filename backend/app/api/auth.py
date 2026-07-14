"""
认证相关 API 路由
- POST /api/auth/register          用户注册
- POST /api/auth/login             用户登录
- POST /api/auth/forgot-password   忘记密码（生成重置令牌）
- POST /api/auth/reset-password    重置密码（验证令牌并更新密码）
- GET    /api/auth/profile         获取个人信息（含检测统计）
- PUT    /api/auth/profile         修改个人信息
- PUT    /api/auth/password        修改密码
- GET    /api/auth/me              获取当前用户信息（兼容旧接口）
"""


from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError
from sqlalchemy.orm import Session


from app.core.security import decode_access_token
from app.database.session import get_db
from app.entity.schemas import (
    ChangePassword,
    ForgotPasswordRequest,
    ProfileResponse,
    ProfileUpdateRequest,
    ResetPasswordRequest,
    TokenResponse,
    UserLogin,
    UserRegister,
    UserResponse,
)
from app.services.user_service import user_service


router = APIRouter(prefix="/api/auth", tags=["认证"])


import logging

bearer_scheme = HTTPBearer(auto_error=False)

logger = logging.getLogger(__name__)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: Session = Depends(get_db),
):
    """
    从 JWT Token 中解析当前用户
    在需要认证的路由中通过 Depends(get_current_user) 使用
    """
    credentials_exception = HTTPException(
        status_code=401,
        detail="未认证或认证失败",
        headers={"WWW-Authenticate": "Bearer"},
    )

    logger.debug(f"credentials: {credentials}")

    if credentials is None:
        logger.error("未提供 Authorization 头")
        raise credentials_exception

    try:
        token = credentials.credentials
        logger.debug(f"token length: {len(token)}, token preview: {token[:20]}...")

        payload = decode_access_token(token)
        logger.debug(f"payload: {payload}")

        user_id_str: str = payload.get("sub")
        if user_id_str is None:
            logger.error("Token 中缺少 sub 字段")
            raise credentials_exception
        user_id = int(user_id_str)
        logger.debug(f"user_id: {user_id}")

    except JWTError as e:
        logger.error(f"JWT 解析失败: {str(e)}")
        raise credentials_exception
    except ValueError as e:
        logger.error(f"用户 ID 转换失败: {str(e)}")
        raise credentials_exception

    user = user_service.get_user_by_id(db, user_id)
    if user is None:
        logger.error(f"用户不存在: user_id={user_id}")
        raise credentials_exception

    logger.debug(f"认证成功: username={user.username}")
    return user


# ══════════════════════════════════════════════════════════════
# 公开接口（无需登录）
# ══════════════════════════════════════════════════════════════


@router.post("/register", response_model=UserResponse, status_code=201)
async def register(request: UserRegister, db: Session = Depends(get_db)):
    """
    用户注册

    - **username**: 用户名（3-50 字符）
    - **email**: 邮箱
    - **password**: 密码（至少 6 位）
    """
    user = user_service.register(
        db=db,
        username=request.username,
        email=request.email,
        password=request.password,
    )
    return user


@router.post("/login", response_model=TokenResponse)
async def login(request: UserLogin, db: Session = Depends(get_db)):
    """
    用户登录

    - 支持用户名或邮箱登录
    - 返回 JWT access_token（有效期 30 分钟）
    - 后续请求在 Header 中携带：Authorization: Bearer <token>
    """
    user = user_service.login(
        db=db,
        username=request.username,
        password=request.password,
    )

    access_token = user_service.create_access_token_for_user(user)
    roles = user_service.get_user_roles(db, user)

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": {
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "avatar": user.avatar,
            "roles": roles,
        },
    }


@router.post("/forgot-password")
async def forgot_password(
    request: ForgotPasswordRequest, db: Session = Depends(get_db)
):
    """
    忘记密码 - 生成一次性重置令牌

    - 提交注册邮箱，生成有效期 1 小时的重置令牌
    - 实际项目中应通过邮件发送令牌，此处直接返回用于开发调试
    """
    token = user_service.forgot_password(db=db, email=request.email)
    return {
        "message": "重置令牌已生成",
        "token": token,
        "expires_in": "1小时",
    }


@router.post("/reset-password")
async def reset_password(
    request: ResetPasswordRequest, db: Session = Depends(get_db)
):
    """
    重置密码 - 验证令牌并更新密码

    - **token**: 忘记密码接口返回的重置令牌
    - **new_password**: 新密码（至少 6 位）
    """
    user_service.reset_password(
        db=db,
        token=request.token,
        new_password=request.new_password,
    )
    return {"message": "密码重置成功"}


# ══════════════════════════════════════════════════════════════
# 需要登录的接口
# ══════════════════════════════════════════════════════════════


@router.get("/profile", response_model=ProfileResponse)
async def get_profile(
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    获取个人信息（含检测统计数据）

    - 需要 Token 认证
    - 返回用户基本信息 + 检测任务统计
    """
    roles = user_service.get_user_roles(db, current_user)
    stats = user_service.get_detection_statistics(db, current_user.id)

    return {
        "id": current_user.id,
        "username": current_user.username,
        "email": current_user.email,
        "phone": current_user.phone,
        "avatar": current_user.avatar,
        "is_active": current_user.is_active,
        "roles": roles,
        "last_login_at": current_user.last_login_at,
        "created_at": current_user.created_at,
        "detection_stats": stats,
    }


@router.put("/profile", response_model=ProfileResponse)
async def update_profile(
    request: ProfileUpdateRequest,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    修改个人信息

    - 需要 Token 认证
    - 可修改：邮箱（唯一性校验）、手机号、头像
    - 只传需要修改的字段即可
    """
    user = user_service.update_profile(
        db=db,
        user=current_user,
        phone=request.phone,
        avatar=request.avatar,
        email=request.email,
    )
    roles = user_service.get_user_roles(db, user)
    stats = user_service.get_detection_statistics(db, user.id)

    return {
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "phone": user.phone,
        "avatar": user.avatar,
        "is_active": user.is_active,
        "roles": roles,
        "last_login_at": user.last_login_at,
        "created_at": user.created_at,
        "detection_stats": stats,
    }


@router.put("/password")
async def change_password(
    request: ChangePassword,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    修改密码

    - 需要 Token 认证
    - 需验证旧密码正确后才能修改
    """
    user_service.change_password(
        db=db,
        user=current_user,
        old_password=request.old_password,
        new_password=request.new_password,
    )
    return {"message": "密码修改成功"}


# ══════════════════════════════════════════════════════════════
# 兼容旧接口
# ══════════════════════════════════════════════════════════════


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """获取当前登录用户信息（需要 Token 认证）"""
    roles = user_service.get_user_roles(db, current_user)
    return {
        "id": current_user.id,
        "username": current_user.username,
        "email": current_user.email,
        "phone": current_user.phone,
        "avatar": current_user.avatar,
        "is_active": current_user.is_active,
        "is_superuser": current_user.is_superuser,
        "roles": roles,
        "last_login_at": current_user.last_login_at,
        "created_at": current_user.created_at,
    }
