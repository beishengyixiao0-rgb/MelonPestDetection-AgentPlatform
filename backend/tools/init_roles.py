#!/usr/bin/env python
"""
初始化系统角色和默认管理员

使用方式：
    cd backend
    python tools/init_roles.py
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def init_roles():
    """初始化 admin/user 两种业务角色和默认管理员账号。"""
    from app.database.session import get_db
    from app.entity.db_models import Role, User, UserRole
    from app.services.user_service import user_service

    db = next(get_db())

    print("=== 初始化系统角色 ===")
    roles = user_service.ensure_builtin_roles(db)
    admin_role = roles["admin"]
    user_role = roles["user"]
    db.commit()
    print("✓ admin / user 角色已就绪")

    print("\n=== 初始化默认管理员 ===")

    admin_user = db.query(User).filter(User.username == "admin").first()
    if not admin_user:
        admin_user = user_service.register(
            db=db,
            username="admin",
            email="admin@example.com",
            password="admin123",
        )
        admin_user.is_active = True
        user_service.assign_single_role(db, admin_user, "admin")
        db.commit()
        print("✓ 创建默认管理员")
        print("  - 用户名: admin")
        print("  - 密码: admin123")
        print("  - 邮箱: admin@example.com")
    else:
        admin_user.is_active = True
        user_service.assign_single_role(db, admin_user, "admin")
        db.commit()
        print("✓ 默认管理员已存在")

    # 为已有但没有角色的账户补上默认 user 角色。
    unassigned_users = (
        db.query(User)
        .outerjoin(UserRole, UserRole.user_id == User.id)
        .filter(UserRole.id.is_(None))
        .all()
    )
    for user in unassigned_users:
        db.add(UserRole(user_id=user.id, role_id=user_role.id))
    if unassigned_users:
        db.commit()
        print(f"✓ 为 {len(unassigned_users)} 个已有账户分配 user 角色")

    print("\n=== 初始化完成 ===")


if __name__ == "__main__":
    init_roles()
