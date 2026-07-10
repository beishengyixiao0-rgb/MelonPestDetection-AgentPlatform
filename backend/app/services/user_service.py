"""
用户服务层
处理用户注册、登录、鉴权等业务逻辑
"""

import secrets
from datetime import datetime, timedelta

from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.security import create_access_token, hash_password, verify_password
from app.entity.db_models import DetectionTask, User


class UserService:
    """用户服务"""

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

        # 创建新用户
        new_user = User(
            username=username,
            email=email,
            hashed_password=hash_password(password),
        )
        db.add(new_user)
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

        if not verify_password(password, user.hashed_password):
            raise HTTPException(status_code=401, detail="用户名或密码错误")

        # 更新最后登录时间
        user.last_login_at = datetime.now()
        db.commit()

        return user

    @staticmethod
    def create_access_token_for_user(user: User) -> str:
        """为用户生成 JWT Token"""
        return create_access_token(data={"sub": str(user.id)})

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
        忘记密码 - 生成一次性重置令牌

        Args:
            db: 数据库会话
            email: 注册邮箱

        Returns:
            重置令牌（实际项目中应通过邮件发送）

        Raises:
            HTTPException: 邮箱未注册
        """
        user = db.query(User).filter(User.email == email).first()
        if not user:
            raise HTTPException(status_code=404, detail="该邮箱未注册")

        # 生成随机令牌（32 字节 hex，64 字符）
        token = secrets.token_hex(32)
        # 令牌有效期 1 小时
        expires_at = datetime.now() + timedelta(hours=1)

        user.reset_token = token
        user.reset_token_expires_at = expires_at
        db.commit()

        return token

    @staticmethod
    def reset_password(db: Session, token: str, new_password: str) -> None:
        """
        重置密码 - 验证令牌并更新密码

        Args:
            db: 数据库会话
            token: 重置令牌
            new_password: 新密码

        Raises:
            HTTPException: 令牌无效或已过期
        """
        user = (
            db.query(User)
            .filter(User.reset_token == token)
            .first()
        )
        if not user:
            raise HTTPException(status_code=400, detail="无效的重置令牌")

        # 检查令牌是否过期
        if user.reset_token_expires_at < datetime.now():
            raise HTTPException(status_code=400, detail="重置令牌已过期，请重新申请")

        # 更新密码并清除令牌
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
