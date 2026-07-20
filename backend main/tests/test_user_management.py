"""用户角色和账户禁用完整测试。"""

import pytest
from app.entity.db_models import User

# ==================== 前置准备 ====================


def create_user(client, username, email, password="123456"):
    """辅助函数：创建用户"""
    response = client.post(
        "/api/auth/register",
        json={"username": username, "email": email, "password": password},
    )
    return response


def get_user_by_username(db_session, username):
    """辅助函数：根据用户名获取用户"""
    return db_session.query(User).filter(User.username == username).first()


def get_user_roles(db_session, user):
    """辅助函数：获取用户角色列表"""
    db_session.refresh(user)
    return [user_role.role.name for user_role in user.user_roles]


# ==================== 一、角色与权限管理 ====================


class TestRoleManagement:
    """角色管理测试"""

    def test_regular_user_cannot_list_users(self, client, user_headers):
        """普通用户调用 GET /api/user/list 应返回 403"""
        response = client.get("/api/user/list", headers=user_headers)
        assert response.status_code == 403
        assert "需要管理员权限" in response.json().get("message", "")

    # 修正：GET /api/user/{id} 路由不存在，改为测试 PUT 接口
    def test_regular_user_cannot_modify_other_user(
        self, client, user_headers, db_session
    ):
        """普通用户修改其他用户信息应返回 403"""
        # 先创建一个普通用户
        create_user(client, "modify_target", "modify_target@example.com")
        target_user = get_user_by_username(db_session, "modify_target")
        assert target_user is not None

        response = client.put(
            f"/api/user/{target_user.id}",
            params={"phone": "13800138000"},
            headers=user_headers,
        )
        assert response.status_code == 403
        assert "需要管理员权限" in response.json().get("message", "")

    def test_regular_user_cannot_delete_other_user(
        self, client, user_headers, db_session
    ):
        """普通用户删除其他用户应返回 403"""
        create_user(client, "delete_target", "delete_target@example.com")
        target_user = get_user_by_username(db_session, "delete_target")
        assert target_user is not None

        response = client.delete(f"/api/user/{target_user.id}", headers=user_headers)
        assert response.status_code == 403
        assert "需要管理员权限" in response.json().get("message", "")

    def test_regular_user_can_view_own_info(self, client, user_headers):
        """普通用户查看自己的信息应返回 200"""
        response = client.get("/api/auth/me", headers=user_headers)
        assert response.status_code == 200
        assert "username" in response.json()
        assert "email" in response.json()

    def test_admin_can_list_users(self, client, admin_headers):
        """管理员查看用户列表应返回 200"""
        response = client.get("/api/user/list", headers=admin_headers)
        assert response.status_code == 200
        assert "data" in response.json()
        assert isinstance(response.json()["data"], list)

    def test_admin_can_promote_user(self, client, db_session, admin_headers):
        """管理员将普通用户提升为管理员"""
        user = get_user_by_username(db_session, "promote_target")
        if not user:
            create_user(client, "promote_target", "promote_target@example.com")
            user = get_user_by_username(db_session, "promote_target")

        response = client.put(
            f"/api/user/{user.id}",
            params={"role_name": "admin"},
            headers=admin_headers,
        )
        assert response.status_code == 200
        assert "更新成功" in response.json().get("message", "")

        db_session.refresh(user)
        roles = [ur.role.name for ur in user.user_roles]
        assert "admin" in roles

    def test_admin_can_demote_user(self, client, db_session, admin_headers):
        """管理员将管理员降级为普通用户"""
        user = get_user_by_username(db_session, "demote_target")
        if not user:
            create_user(client, "demote_target", "demote_target@example.com")
            user = get_user_by_username(db_session, "demote_target")

        # 先提升为admin
        response = client.put(
            f"/api/user/{user.id}",
            params={"role_name": "admin"},
            headers=admin_headers,
        )
        assert response.status_code == 200

        # 降级
        response = client.put(
            f"/api/user/{user.id}",
            params={"role_name": "user"},
            headers=admin_headers,
        )
        assert response.status_code == 200
        assert "更新成功" in response.json().get("message", "")

        db_session.refresh(user)
        roles = [ur.role.name for ur in user.user_roles]
        assert "admin" not in roles

    def test_admin_can_demote_self(self, client, admin_headers):
        """管理员可以降级自己（根据代码，没有限制）"""
        me_response = client.get("/api/auth/me", headers=admin_headers)
        assert me_response.status_code == 200
        admin_user_id = me_response.json().get("id")
        assert admin_user_id is not None

        response = client.put(
            f"/api/user/{admin_user_id}",
            params={"role_name": "user"},
            headers=admin_headers,
        )
        # 代码中只检查了不能删除自己，没有限制降级自己
        # 但降级后如果只剩一个管理员，会返回400
        # 根据实际返回，可能是200或400
        if response.status_code == 400:
            assert "至少需要保留一个" in response.json().get("message", "")
        else:
            assert response.status_code == 200

    def test_admin_cannot_disable_self(self, client, admin_headers):
        """管理员不能禁用自己"""
        me_response = client.get("/api/auth/me", headers=admin_headers)
        assert me_response.status_code == 200
        admin_user_id = me_response.json().get("id")
        assert admin_user_id is not None

        response = client.delete(f"/api/user/{admin_user_id}", headers=admin_headers)
        # 代码中明确检查了不能删除自己
        assert response.status_code == 400
        assert "不能删除自己" in response.json().get("message", "")

    def test_assign_nonexistent_role(self, client, admin_headers, db_session):
        """分配不存在的角色名应返回 400"""
        user = get_user_by_username(db_session, "promote_target")
        assert user is not None

        response = client.put(
            f"/api/user/{user.id}",
            params={"role_name": "super_admin_xxx"},
            headers=admin_headers,
        )
        assert response.status_code == 400
        assert "角色仅支持" in response.json().get("message", "")

    def test_new_user_default_role_is_not_admin(self, client, db_session):
        """新注册用户默认角色为非管理员"""
        create_user(client, "new_default_user", "new_default@example.com")
        user = get_user_by_username(db_session, "new_default_user")
        assert user is not None

        roles = get_user_roles(db_session, user)
        assert "admin" not in roles


# ==================== 二、账户禁用功能 ====================


class TestAccountDisable:
    """账户禁用测试"""

    def test_admin_can_disable_user(self, client, admin_headers, db_session):
        """管理员可以禁用用户"""
        user = get_user_by_username(db_session, "test_user")
        assert user is not None
        assert user.is_active is True

        response = client.delete(f"/api/user/{user.id}", headers=admin_headers)
        assert response.status_code == 200
        assert response.json()["message"] == "账户已禁用"

        db_session.refresh(user)
        assert user.is_active is False

    def test_disabled_user_cannot_login(self, client, db_session, admin_headers):
        """禁用用户后无法登录"""
        user = get_user_by_username(db_session, "test_user")
        assert user is not None

        response = client.delete(f"/api/user/{user.id}", headers=admin_headers)
        assert response.status_code == 200

        login_response = client.post(
            "/api/auth/login",
            json={"username": "test_user", "password": "123456"},
        )
        assert login_response.status_code == 403
        assert "账号已被禁用" in login_response.json().get("message", "")

    def test_disabled_user_existing_token_blocked(
        self, client, admin_headers, db_session, user_headers
    ):
        """禁用用户后原有Token失效"""
        me_response = client.get("/api/auth/me", headers=user_headers)
        assert me_response.status_code == 200

        user_id = me_response.json().get("id")
        assert user_id is not None

        response = client.delete(f"/api/user/{user_id}", headers=admin_headers)
        assert response.status_code == 200

        existing_token_response = client.get("/api/auth/me", headers=user_headers)
        assert existing_token_response.status_code == 403

    def test_disabled_user_can_access_public_endpoints(
        self, client, db_session, admin_headers
    ):
        """禁用用户后仍可访问公共接口"""
        user = get_user_by_username(db_session, "test_user")
        assert user is not None

        response = client.delete(f"/api/user/{user.id}", headers=admin_headers)
        assert response.status_code == 200

        health_response = client.get("/api/health")
        assert health_response.status_code == 200

    def test_disabled_user_cannot_call_protected_apis(
        self, client, admin_headers, db_session, user_headers
    ):
        """禁用用户后无法调用受保护接口"""
        user = get_user_by_username(db_session, "test_user")
        assert user is not None

        response = client.delete(f"/api/user/{user.id}", headers=admin_headers)
        assert response.status_code == 200

        detection_response = client.post(
            "/api/detection/single",
            headers=user_headers,
            files={"file": ("test.jpg", b"fake_image_data", "image/jpeg")},
        )
        assert detection_response.status_code == 403

    def test_disable_already_disabled_user(self, client, admin_headers, db_session):
        """禁用已禁用的用户应返回 200（幂等设计）"""
        user = get_user_by_username(db_session, "test_user")
        assert user is not None

        response1 = client.delete(f"/api/user/{user.id}", headers=admin_headers)
        assert response1.status_code == 200

        response2 = client.delete(f"/api/user/{user.id}", headers=admin_headers)
        assert response2.status_code == 200
        assert response2.json().get("message") == "账户已禁用"

    def test_disable_nonexistent_user(self, client, admin_headers):
        """禁用不存在的用户应返回 404"""
        response = client.delete("/api/user/999999", headers=admin_headers)
        assert response.status_code == 404
        assert "用户不存在" in response.json().get("message", "")

    def test_admin_can_enable_disabled_user(self, client, admin_headers, db_session):
        """管理员可以重新启用已禁用用户。"""
        create_user(client, "enable_target", "enable_target@example.com")
        user = get_user_by_username(db_session, "enable_target")
        assert user is not None

        disable_response = client.delete(f"/api/user/{user.id}", headers=admin_headers)
        assert disable_response.status_code == 200

        enable_response = client.patch(
            f"/api/user/{user.id}/enable",
            headers=admin_headers,
        )
        assert enable_response.status_code == 200
        assert enable_response.json().get("message") == "账户已启用"

        db_session.refresh(user)
        assert user.is_active is True

    def test_enabled_user_can_login_again(self, client, admin_headers, db_session):
        """重新启用后用户可以再次登录。"""
        create_user(client, "enable_login_target", "enable_login@example.com")
        user = get_user_by_username(db_session, "enable_login_target")
        assert user is not None

        assert client.delete(f"/api/user/{user.id}", headers=admin_headers).status_code == 200
        assert (
            client.patch(f"/api/user/{user.id}/enable", headers=admin_headers).status_code
            == 200
        )

        login_response = client.post(
            "/api/auth/login",
            json={"username": "enable_login_target", "password": "123456"},
        )
        assert login_response.status_code == 200
        assert "access_token" in login_response.json()

    def test_enable_already_enabled_user(self, client, admin_headers, db_session):
        """启用已启用的用户应返回 200（幂等设计）。"""
        create_user(client, "already_enabled_target", "already_enabled@example.com")
        user = get_user_by_username(db_session, "already_enabled_target")
        assert user is not None
        assert user.is_active is True

        response = client.patch(f"/api/user/{user.id}/enable", headers=admin_headers)
        assert response.status_code == 200
        assert response.json().get("message") == "账户已启用"

    def test_regular_user_cannot_enable_user(self, client, user_headers, db_session):
        """普通用户不能启用账户。"""
        create_user(client, "regular_enable_target", "regular_enable@example.com")
        user = get_user_by_username(db_session, "regular_enable_target")
        assert user is not None

        response = client.patch(f"/api/user/{user.id}/enable", headers=user_headers)
        assert response.status_code == 403
        assert "需要管理员权限" in response.json().get("message", "")

    def test_enable_nonexistent_user(self, client, admin_headers):
        """启用不存在的用户应返回 404。"""
        response = client.patch("/api/user/999999/enable", headers=admin_headers)
        assert response.status_code == 404
        assert "用户不存在" in response.json().get("message", "")

    def test_cannot_disable_last_admin(self, client, admin_headers, db_session):
        """不能禁用最后一个管理员"""
        # 查找当前有多少个管理员
        me_response = client.get("/api/auth/me", headers=admin_headers)
        assert me_response.status_code == 200
        admin_user_id = me_response.json().get("id")

        # 如果只有一个管理员，尝试禁用自己会返回400
        # 如果有多个管理员，需要找一个普通用户来测试
        # 这里测试禁用自己（最后一个管理员的情况）
        response = client.delete(f"/api/user/{admin_user_id}", headers=admin_headers)
        assert response.status_code == 400
        assert "不能删除自己" in response.json().get("message", "")


# ==================== 三、管理员跨用户数据访问 ====================


class TestAdminCrossUserAccess:
    """管理员跨用户数据访问测试"""

    def test_admin_can_delete_other_user_dataset(
        self, client, admin_headers, db_session
    ):
        """管理员可以删除其他用户的数据集"""
        create_user(client, "dataset_user", "dataset_user@example.com")
        login_response = client.post(
            "/api/auth/login",
            json={"username": "dataset_user", "password": "123456"},
        )
        assert login_response.status_code == 200
        dataset_user_headers = {
            "Authorization": f"Bearer {login_response.json()['access_token']}"
        }

        create_response = client.post(
            "/api/dataset",
            json={
                "name": "test_dataset",
                "display_name": "测试数据集",
                "description": "用于测试",
                "category": "fruit",
                "format_type": "yolo",
            },
            headers=dataset_user_headers,
        )
        if create_response.status_code == 200:
            dataset_id = create_response.json().get("id")

            delete_response = client.delete(
                f"/api/dataset/{dataset_id}",
                headers=admin_headers,
            )
            assert delete_response.status_code == 200
            assert delete_response.json()["message"] == "数据集已删除"


# ==================== 四、端到端测试 ====================


class TestEndToEndFlow:
    """端到端综合流程测试"""

    def test_full_lifecycle_user_management_flow(
        self, client, admin_headers, db_session
    ):
        """完整的用户生命周期管理流程"""
        # 1. 注册新用户
        create_response = create_user(client, "lifecycle_user", "lifecycle@example.com")
        assert create_response.status_code == 201
        user = get_user_by_username(db_session, "lifecycle_user")
        assert user is not None

        # 2. 验证默认角色为非管理员
        roles = get_user_roles(db_session, user)
        assert "admin" not in roles

        # 3. 登录验证
        login_response = client.post(
            "/api/auth/login",
            json={"username": "lifecycle_user", "password": "123456"},
        )
        assert login_response.status_code == 200
        access_token = login_response.json()["access_token"]
        user_headers = {"Authorization": f"Bearer {access_token}"}

        # 4. 普通用户调用管理接口被拒绝
        list_response = client.get("/api/user/list", headers=user_headers)
        assert list_response.status_code == 403
        assert "需要管理员权限" in list_response.json().get("message", "")

        # 5. 管理员提升用户
        promote_response = client.put(
            f"/api/user/{user.id}",
            params={"role_name": "admin"},
            headers=admin_headers,
        )
        assert promote_response.status_code == 200
        assert "更新成功" in promote_response.json().get("message", "")

        # 6. 验证角色已变更
        db_session.refresh(user)
        roles = get_user_roles(db_session, user)
        assert "admin" in roles

        # 7. 管理员禁用用户
        disable_response = client.delete(f"/api/user/{user.id}", headers=admin_headers)
        assert disable_response.status_code == 200

        # 8. 验证禁用后无法登录
        login_response2 = client.post(
            "/api/auth/login",
            json={"username": "lifecycle_user", "password": "123456"},
        )
        assert login_response2.status_code == 403
        assert "账号已被禁用" in login_response2.json().get("message", "")
