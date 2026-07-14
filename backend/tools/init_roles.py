"""
角色初始化脚本

用途：初始化系统角色（管理员、普通用户）和默认超级管理员

使用方式：
    cd backend
    .venv\Scripts\activate
    python tools\init_roles.py
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy.orm import Session
from app.database.session import get_db
from app.entity.db_models import Role, User, UserRole
from app.core.security import hash_password


def init_roles(db: Session):
    """初始化系统角色"""
    roles = [
        {"name": "admin", "display_name": "管理员", "description": "拥有系统所有权限"},
        {"name": "user", "display_name": "普通用户", "description": "仅拥有检测和智能体功能"},
    ]

    created_roles = []
    for role_data in roles:
        existing = db.query(Role).filter(Role.name == role_data["name"]).first()
        if existing:
            print(f"角色已存在: {role_data['name']}")
            created_roles.append(existing)
            continue

        role = Role(
            name=role_data["name"],
            display_name=role_data["display_name"],
            description=role_data["description"],
            is_system=True,
        )
        db.add(role)
        db.commit()
        db.refresh(role)
        print(f"创建角色: {role.name} ({role.display_name})")
        created_roles.append(role)

    return created_roles


def init_default_admin(db: Session, admin_role: Role):
    """初始化默认超级管理员"""
    default_admin = db.query(User).filter(User.username == "admin").first()
    if default_admin:
        print(f"更新管理员密码")
        default_admin.hashed_password = hash_password("admin123")
        default_admin.is_superuser = True
        default_admin.is_active = True

        existing_role = db.query(UserRole).filter(
            UserRole.user_id == default_admin.id,
            UserRole.role_id == admin_role.id
        ).first()
        if not existing_role:
            user_role = UserRole(user_id=default_admin.id, role_id=admin_role.id)
            db.add(user_role)

        db.commit()
        print(f"管理员: username=admin, email=admin@example.com, password=admin123")
        print(f"请首次登录后立即修改密码！")
        return

    admin = User(
        username="admin",
        email="admin@example.com",
        hashed_password=hash_password("admin123"),
        is_superuser=True,
        is_active=True,
    )
    db.add(admin)
    db.commit()
    db.refresh(admin)

    user_role = UserRole(user_id=admin.id, role_id=admin_role.id)
    db.add(user_role)
    db.commit()

    print(f"创建默认超级管理员: username=admin, email=admin@example.com, password=admin123")
    print(f"请首次登录后立即修改密码！")


def main():
    print("=" * 50)
    print("角色初始化脚本")
    print("=" * 50)

    db = next(get_db())

    try:
        roles = init_roles(db)
        admin_role = roles[0]
        init_default_admin(db, admin_role)
        print()
        print("初始化完成！")
    except Exception as e:
        db.rollback()
        print(f"初始化失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        db.close()


if __name__ == "__main__":
    main()
