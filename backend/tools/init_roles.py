#!/usr/bin/env python
"""
初始化系统角色和默认超级管理员

使用方式：
    cd backend
    python tools/init_roles.py
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def init_roles():
    """初始化角色和默认管理员"""
    from app.database.session import get_db
    from app.entity.db_models import Role, User, UserRole
    from app.services.user_service import user_service

    db = next(get_db())

    print("=== 初始化系统角色 ===")

    admin_role = db.query(Role).filter(Role.name == "admin").first()
    if not admin_role:
        admin_role = Role(
            name="admin",
            display_name="管理员",
            description="系统管理员，拥有所有权限",
            is_system=True,
        )
        db.add(admin_role)
        db.commit()
        print("✓ 创建管理员角色")
    else:
        print("✓ 管理员角色已存在")

    user_role = db.query(Role).filter(Role.name == "user").first()
    if not user_role:
        user_role = Role(
            name="user",
            display_name="普通用户",
            description="普通用户，仅拥有检测和智能体功能",
            is_system=True,
        )
        db.add(user_role)
        db.commit()
        print("✓ 创建普通用户角色")
    else:
        print("✓ 普通用户角色已存在")

    print("\n=== 初始化默认超级管理员 ===")

    admin_user = db.query(User).filter(User.username == "admin").first()
    if not admin_user:
        admin_user = user_service.register(
            db=db,
            username="admin",
            email="admin@example.com",
            password="admin123",
        )
        admin_user.is_superuser = True
        admin_user.is_active = True

        existing_ur = db.query(UserRole).filter(
            UserRole.user_id == admin_user.id,
            UserRole.role_id == admin_role.id
        ).first()
        if not existing_ur:
            db.add(UserRole(user_id=admin_user.id, role_id=admin_role.id))

        db.commit()
        print("✓ 创建默认超级管理员")
        print("  - 用户名: admin")
        print("  - 密码: admin123")
        print("  - 邮箱: admin@example.com")
    else:
        if not admin_user.is_superuser:
            admin_user.is_superuser = True
            db.commit()
            print("✓ 更新为超级管理员")
        print("✓ 默认超级管理员已存在")

    print("\n=== 初始化完成 ===")


if __name__ == "__main__":
    init_roles()