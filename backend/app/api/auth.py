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


from fastapi import APIRouter, Depends, HTTPException, Header
from jose import JWTError
from sqlalchemy.orm import Session


from app.core.security import decode_access_token
from app.database.session import get_db
from app.entity.schemas import (
    ChangePassword,
    DisplayLanguageUpdate,
    ForgotPasswordRequest,
    ProfileResponse,
    ProfileUpdateRequest,
    ResetPasswordRequest,
    TokenResponse,
    UserLogin,
    UserRegister,
    UserResponse,
    VerifyCodeRequest,
)
from app.services.user_service import user_service


router = APIRouter(prefix="/api/auth", tags=["认证"])


import logging

logger = logging.getLogger(__name__)


async def get_current_user(
    authorization: str = Header(None),
    db: Session = Depends(get_db),
):
    """
    从 JWT Token 中解析当前用户
    在需要认证的路由中通过 Depends(get_current_user) 使用
    支持两种格式的Authorization头：
    1. Bearer <token>（标准格式）
    2. 直接输入token（Swagger UI授权时使用）
    """
    credentials_exception = HTTPException(
        status_code=401,
        detail="未认证或认证失败",
        headers={"WWW-Authenticate": "Bearer"},
    )

    if authorization is None:
        logger.error("未提供 Authorization 头")
        raise credentials_exception

    try:
        token = authorization.strip()
        if token.lower().startswith("bearer "):
            token = token[7:]

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
    if not user.is_active:
        logger.warning(f"已禁用账号请求接口: user_id={user_id}")
        raise HTTPException(status_code=403, detail="账号已被禁用")

    logger.debug(f"认证成功: username={user.username}")
    return user


def require_admin(current_user=Depends(get_current_user)):
    """
    管理员权限验证依赖
    仅 admin 角色可通过；is_superuser 不再作为独立业务权限。
    """
    roles = [ur.role.name for ur in current_user.user_roles]
    if "admin" not in roles:
        raise HTTPException(status_code=403, detail="需要管理员权限")

    return current_user


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
async def login_json(request: UserLogin, db: Session = Depends(get_db)):
    """
    用户登录（JSON格式）

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
        "expires_in": 1800,
        "user": {
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "avatar": user.avatar,
            "display_language": user.display_language,
            "roles": roles,
        },
    }


@router.post("/forgot-password")
async def forgot_password(
    request: ForgotPasswordRequest, db: Session = Depends(get_db)
):
    """
    忘记密码 - 发送 6 位验证码到邮箱

    - 提交注册邮箱，系统生成 6 位验证码并通过邮件发送
    - 验证码有效期 5 分钟
    """
    user_service.forgot_password(db=db, email=request.email)
    return {
        "message": "验证码已发送到您的邮箱，请在 5 分钟内使用",
    }


@router.post("/verify-code")
async def verify_code(
    request: VerifyCodeRequest, db: Session = Depends(get_db)
):
    """
    验证码校验 - 验证邮箱和验证码是否有效

    - **email**: 注册邮箱
    - **code**: 6 位验证码

    返回验证码是否有效，用于前端在用户输入验证码后即时校验。
    """
    from app.entity.db_models import User
    from datetime import datetime

    user = db.query(User).filter(User.email == request.email).first()
    if not user:
        raise HTTPException(status_code=400, detail="该邮箱未注册")

    if not user.reset_token or user.reset_token != request.code:
        raise HTTPException(status_code=400, detail="验证码错误")

    if user.reset_token_expires_at < datetime.now():
        raise HTTPException(status_code=400, detail="验证码已过期，请重新申请")

    return {"message": "验证码有效"}


@router.post("/reset-password")
async def reset_password(
    request: ResetPasswordRequest, db: Session = Depends(get_db)
):
    """
    重置密码 - 验证邮箱和验证码并更新密码

    - **email**: 注册邮箱
    - **code**: 6 位验证码
    - **new_password**: 新密码（至少 6 位）
    """
    user_service.reset_password(
        db=db,
        email=request.email,
        code=request.code,
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
        "display_language": current_user.display_language,
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
        "display_language": user.display_language,
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


# 保留细分路径兼容已接入客户端，同时以 /preferences 作为用户偏好统一入口。
@router.put("/preferences")
@router.put("/preferences/display-language")
async def update_display_language(
    request: DisplayLanguageUpdate,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """保存用户语言偏好，供未携带语言请求头的后续请求使用。"""
    # Pydantic 已限制为 zh/en，此处只负责持久化当前登录用户自己的偏好。
    current_user.display_language = request.display_language
    db.commit()
    db.refresh(current_user)
    return {"display_language": current_user.display_language}


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
        "display_language": current_user.display_language,
        "is_active": current_user.is_active,
        "is_superuser": current_user.is_superuser,
        "roles": roles,
        "last_login_at": current_user.last_login_at,
        "created_at": current_user.created_at,
    }
