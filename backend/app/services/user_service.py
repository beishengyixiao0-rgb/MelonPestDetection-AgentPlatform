"""
用户服务层
处理用户注册、登录、鉴权等业务逻辑
"""

import random
from datetime import datetime, timedelta

from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.security import create_access_token, hash_password, verify_password
from app.entity.db_models import DetectionTask, Role, User, UserRole
from app.services.email_service import EmailService


class UserService:
    """用户服务"""

    BUILTIN_ROLES = {
        "admin": {"display_name": "管理员", "description": "系统管理员，拥有管理功能"},
        "user": {"display_name": "普通用户", "description": "普通用户，仅拥有检测和智能对话功能"},
    }

    @staticmethod
    def ensure_builtin_roles(db: Session) -> dict[str, Role]:
        """确保系统仅有的两种业务角色存在，并返回角色对象。"""
        roles = {}
        for name, values in UserService.BUILTIN_ROLES.items():
            role = db.query(Role).filter(Role.name == name).first()
            if not role:
                role = Role(name=name, is_system=True, **values)
                db.add(role)
                db.flush()
            roles[name] = role
        return roles

    @staticmethod
    def assign_single_role(db: Session, user: User, role_name: str) -> None:
        """将用户设置为唯一业务角色，避免 admin/user 角色并存。"""
        roles = UserService.ensure_builtin_roles(db)
        role = roles.get(role_name)
        if not role:
            raise HTTPException(status_code=400, detail=f"角色不存在: {role_name}")
        db.query(UserRole).filter(UserRole.user_id == user.id).delete()
        db.add(UserRole(user_id=user.id, role_id=role.id))
        db.flush()

    @staticmethod
    def register(db: Session, username: str, email: str, password: str) -> User:
        """
        用户注册

        Args:
            db: 数据库会话
            username: 用户名
            email: 邮箱
            password: 明文密码

        Returns:
            新创建的用户对象

        Raises:
            HTTPException: 用户名或邮箱已存在
        """
        # 检查用户名是否已存在
        existing_user = db.query(User).filter(User.username == username).first()
        if existing_user:
            raise HTTPException(status_code=400, detail="用户名已存在")

        # 检查邮箱是否已存在
        existing_email = db.query(User).filter(User.email == email).first()
        if existing_email:
            raise HTTPException(status_code=400, detail="邮箱已被注册")

        # 角色种子可能尚未通过管理脚本初始化；注册时兜底保证 user 角色存在。
        roles = UserService.ensure_builtin_roles(db)

        # 创建新用户并默认分配 user 角色。
        new_user = User(
            username=username,
            email=email,
            hashed_password=hash_password(password),
        )
        db.add(new_user)
        db.flush()
        db.add(UserRole(user_id=new_user.id, role_id=roles["user"].id))
        db.commit()
        db.refresh(new_user)

        return new_user

    @staticmethod
    def login(db: Session, username: str, password: str) -> User:
        """
        用户登录（支持用户名或邮箱登录）

        Args:
            db: 数据库会话
            username: 用户名或邮箱
            password: 明文密码

        Returns:
            登录成功的用户对象

        Raises:
            HTTPException: 用户名或密码错误
        """
        # 支持用户名或邮箱登录
        user = (
            db.query(User)
            .filter(
                (User.username == username) | (User.email == username)
            )
            .first()
        )
        if not user:
            raise HTTPException(status_code=401, detail="用户名或密码错误")

        if not user.is_active:
            raise HTTPException(status_code=403, detail="账号已被禁用")

        if not verify_password(password, user.hashed_password):
            raise HTTPException(status_code=401, detail="用户名或密码错误")

        # 更新最后登录时间
        user.last_login_at = datetime.now()
        db.commit()

        return user

    @staticmethod
    def create_access_token_for_user(user: User) -> str:
        """为用户生成 JWT Token"""
        return create_access_token(data={"sub": str(user.id), "language": user.display_language})

    @staticmethod
    def get_user_roles(db: Session, user: User) -> list[str]:
        """获取用户的角色标识列表"""
        return [ur.role.name for ur in user.user_roles]

    @staticmethod
    def get_user_by_id(db: Session, user_id: int) -> User:
        """根据 ID 获取用户"""
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="用户不存在")
        return user

    @staticmethod
    def forgot_password(db: Session, email: str) -> str:
        """
        忘记密码 - 生成 6 位验证码并发送邮件

        Args:
            db: 数据库会话
            email: 注册邮箱

        Returns:
            验证码（用于开发调试，生产环境应仅通过邮件发送）

        Raises:
            HTTPException: 邮箱未注册或邮件发送失败
        """
        user = db.query(User).filter(User.email == email).first()
        if not user:
            raise HTTPException(status_code=404, detail="该邮箱未注册")

        # 生成 6 位数字验证码
        code = f"{random.randint(100000, 999999)}"
        # 验证码有效期 5 分钟
        expires_at = datetime.now() + timedelta(minutes=5)

        user.reset_token = code
        user.reset_token_expires_at = expires_at
        db.commit()

        # 发送邮件
        success = EmailService.send_verification_code(email, code)
        if not success:
            raise HTTPException(status_code=500, detail="验证码邮件发送失败，请稍后重试")

        return code

    @staticmethod
    def reset_password(db: Session, email: str, code: str, new_password: str) -> None:
        """
        重置密码 - 验证邮箱和验证码并更新密码

        Args:
            db: 数据库会话
            email: 注册邮箱
            code: 6 位验证码
            new_password: 新密码

        Raises:
            HTTPException: 邮箱未注册、验证码错误或已过期
        """
        user = db.query(User).filter(User.email == email).first()
        if not user:
            raise HTTPException(status_code=400, detail="该邮箱未注册")

        if not user.reset_token or user.reset_token != code:
            raise HTTPException(status_code=400, detail="验证码错误")

        # 检查验证码是否过期
        if user.reset_token_expires_at < datetime.now():
            raise HTTPException(status_code=400, detail="验证码已过期，请重新申请")

        # 更新密码并清除验证码
        user.hashed_password = hash_password(new_password)
        user.reset_token = None
        user.reset_token_expires_at = None
        db.commit()

    @staticmethod
    def change_password(
        db: Session, user: User, old_password: str, new_password: str
    ) -> None:
        """
        修改密码 - 验证旧密码后更新

        Args:
            db: 数据库会话
            user: 当前用户
            old_password: 旧密码
            new_password: 新密码

        Raises:
            HTTPException: 旧密码错误
        """
        if not verify_password(old_password, user.hashed_password):
            raise HTTPException(status_code=400, detail="旧密码错误")

        user.hashed_password = hash_password(new_password)
        db.commit()

    @staticmethod
    def update_profile(
        db: Session,
        user: User,
        phone: str | None = None,
        avatar: str | None = None,
        email: str | None = None,
    ) -> User:
        """
        修改个人信息

        Args:
            db: 数据库会话
            user: 当前用户
            phone: 新手机号
            avatar: 新头像 URL
            email: 新邮箱（需唯一性校验）

        Returns:
            更新后的用户对象

        Raises:
            HTTPException: 邮箱已被其他用户使用
        """
        if email is not None and email != user.email:
            existing = db.query(User).filter(User.email == email).first()
            if existing:
                raise HTTPException(status_code=400, detail="该邮箱已被其他用户使用")
            user.email = email

        if phone is not None:
            user.phone = phone
        if avatar is not None:
            user.avatar = avatar

        db.commit()
        db.refresh(user)
        return user

    @staticmethod
    def get_detection_statistics(db: Session, user_id: int) -> dict:
        """
        获取用户的检测统计数据

        Args:
            db: 数据库会话
            user_id: 用户 ID

        Returns:
            检测统计数据字典
        """
        # 总任务数
        total_tasks = (
            db.query(func.count(DetectionTask.id))
            .filter(DetectionTask.user_id == user_id)
            .scalar()
        ) or 0

        # 总图像数
        total_images = (
            db.query(func.coalesce(func.sum(DetectionTask.total_images), 0))
            .filter(DetectionTask.user_id == user_id)
            .scalar()
        )

        # 总目标数
        total_objects = (
            db.query(func.coalesce(func.sum(DetectionTask.total_objects), 0))
            .filter(DetectionTask.user_id == user_id)
            .scalar()
        )

        # 平均推理耗时
        avg_inference_time = (
            db.query(func.avg(DetectionTask.total_inference_time))
            .filter(
                DetectionTask.user_id == user_id,
                DetectionTask.total_images > 0,
            )
            .scalar()
        ) or 0.0

        # 各场景检测次数
        from app.entity.db_models import DetectionScene

        scene_dist_rows = (
            db.query(DetectionScene.display_name, func.count(DetectionTask.id))
            .join(DetectionTask, DetectionTask.scene_id == DetectionScene.id)
            .filter(DetectionTask.user_id == user_id)
            .group_by(DetectionScene.display_name)
            .all()
        )
        scene_distribution = {row[0]: row[1] for row in scene_dist_rows}

        return {
            "total_tasks": total_tasks,
            "total_images": total_images,
            "total_objects": total_objects,
            "avg_inference_time": round(float(avg_inference_time), 2),
            "class_distribution": {},
            "daily_trend": [],
            "scene_distribution": scene_distribution,
        }


# 全局单例
user_service = UserService()
