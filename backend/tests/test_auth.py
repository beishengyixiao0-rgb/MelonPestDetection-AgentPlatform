"""
认证接口测试

测试目标：
  - 用户注册：正常注册、重复用户名、参数验证
  - 用户登录：正常登录、错误密码、不存在的用户
  - 获取当前用户：有 Token、无 Token、无效 Token

测试策略：
  - 每个测试用例独立，不依赖其他测试的执行顺序
  - 使用唯一的用户名避免测试间冲突
"""

import pytest


class TestRegister:
    """用户注册测试"""

    def test_register_success(self, client):
        """正常注册"""
        response = client.post(
            "/api/auth/register",
            json={
                "username": "test_register_user",
                "email": "test_register@example.com",
                "password": "123456",
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["username"] == "test_register_user"
        assert data["email"] == "test_register@example.com"
        # 确保不返回密码字段
        assert "hashed_password" not in data
        assert "password" not in data

    def test_register_duplicate_username(self, client):
        """重复用户名注册"""
        # 先注册一个用户
        client.post(
            "/api/auth/register",
            json={
                "username": "dup_user",
                "email": "dup1@example.com",
                "password": "123456",
            },
        )
        # 用相同用户名再注册
        response = client.post(
            "/api/auth/register",
            json={
                "username": "dup_user",
                "email": "dup2@example.com",
                "password": "123456",
            },
        )
        assert response.status_code == 400

    def test_register_short_username(self, client):
        """用户名过短（少于 3 字符）"""
        response = client.post(
            "/api/auth/register",
            json={
                "username": "ab",
                "email": "short@example.com",
                "password": "123456",
            },
        )
        assert response.status_code == 422

    def test_register_short_password(self, client):
        """密码过短（少于 6 位）"""
        response = client.post(
            "/api/auth/register",
            json={
                "username": "short_pwd_user",
                "email": "shortpwd@example.com",
                "password": "123",
            },
        )
        assert response.status_code == 422

    def test_register_missing_fields(self, client):
        """缺少必填字段"""
        response = client.post(
            "/api/auth/register",
            json={"username": "no_email_user"},
        )
        assert response.status_code == 422


class TestLogin:
    """用户登录测试"""

    def test_login_success(self, client):
        """正常登录"""
        # 先注册
        client.post(
            "/api/auth/register",
            json={
                "username": "login_user",
                "email": "login@example.com",
                "password": "123456",
            },
        )
        # 再登录
        response = client.post(
            "/api/auth/login",
            json={
                "username": "login_user",
                "password": "123456",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"
        assert data["user"]["username"] == "login_user"
        assert data["user"]["roles"] == ["user"]

    def test_login_wrong_password(self, client):
        """密码错误"""
        # 先注册
        client.post(
            "/api/auth/register",
            json={
                "username": "wrong_pwd_user",
                "email": "wrongpwd@example.com",
                "password": "123456",
            },
        )
        # 用错误密码登录
        response = client.post(
            "/api/auth/login",
            json={
                "username": "wrong_pwd_user",
                "password": "wrongpassword",
            },
        )
        assert response.status_code == 401

    def test_login_nonexistent_user(self, client):
        """不存在的用户"""
        response = client.post(
            "/api/auth/login",
            json={
                "username": "no_such_user_12345",
                "password": "123456",
            },
        )
        assert response.status_code == 401


class TestGetCurrentUser:
    """获取当前用户测试"""

    def test_get_me_with_valid_token(self, client):
        """使用有效 Token 获取用户信息"""
        # 注册并登录
        client.post(
            "/api/auth/register",
            json={
                "username": "me_user",
                "email": "me@example.com",
                "password": "123456",
            },
        )
        login_response = client.post(
            "/api/auth/login",
            json={
                "username": "me_user",
                "password": "123456",
            },
        )
        token = login_response.json()["access_token"]

        # 使用 Token 获取用户信息
        response = client.get(
            "/api/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["username"] == "me_user"
        assert data["email"] == "me@example.com"

    def test_get_me_without_token(self, client):
        """不带 Token 访问受保护接口"""
        response = client.get("/api/auth/me")
        assert response.status_code == 401

    def test_get_me_with_invalid_token(self, client):
        """使用无效 Token"""
        response = client.get(
            "/api/auth/me",
            headers={"Authorization": "Bearer invalid_token_here"},
        )
        assert response.status_code == 401


# ============================================================
# 新增测试 - 忘记密码 7.10
# ============================================================


class TestForgotPassword:
    """忘记密码测试"""

    def test_forgot_password_success(self, client):
        """正常忘记密码"""
        # 先注册用户
        client.post(
            "/api/auth/register",
            json={
                "username": "forgot_user",
                "email": "forgot@example.com",
                "password": "123456",
            },
        )

        response = client.post(
            "/api/auth/forgot-password",
            json={"email": "forgot@example.com"},
        )
        assert response.status_code == 200
        data = response.json()
        assert "token" in data
        assert data["message"] == "重置令牌已生成"
        assert data["expires_in"] == "1小时"

    def test_forgot_password_email_not_found(self, client):
        """邮箱未注册"""
        response = client.post(
            "/api/auth/forgot-password",
            json={"email": "notexist@example.com"},
        )
        assert response.status_code == 404


class TestResetPassword:
    """重置密码测试"""

    def test_reset_password_success(self, client):
        """正常重置密码"""
        # 注册用户
        client.post(
            "/api/auth/register",
            json={
                "username": "reset_user",
                "email": "reset@example.com",
                "password": "123456",
            },
        )

        # 获取重置令牌
        forgot_response = client.post(
            "/api/auth/forgot-password",
            json={"email": "reset@example.com"},
        )
        token = forgot_response.json()["token"]

        # 重置密码
        response = client.post(
            "/api/auth/reset-password",
            json={
                "token": token,
                "new_password": "new789012",
            },
        )
        assert response.status_code == 200
        assert response.json()["message"] == "密码重置成功"

        # 使用新密码登录验证
        login_response = client.post(
            "/api/auth/login",
            json={
                "username": "reset_user",
                "password": "new789012",
            },
        )
        assert login_response.status_code == 200

    def test_reset_password_invalid_token(self, client):
        """无效的重置令牌"""
        response = client.post(
            "/api/auth/reset-password",
            json={
                "token": "invalid_token_12345",
                "new_password": "new789012",
            },
        )
        assert response.status_code == 400
        assert response.json()["message"] == "无效的重置令牌"


class TestProfile:
    """个人信息测试"""

    def test_get_profile_success(self, client):
        """正常获取个人信息"""
        # 注册并登录
        client.post(
            "/api/auth/register",
            json={
                "username": "profile_user",
                "email": "profile@example.com",
                "password": "123456",
            },
        )
        login_response = client.post(
            "/api/auth/login",
            json={
                "username": "profile_user",
                "password": "123456",
            },
        )
        token = login_response.json()["access_token"]

        response = client.get(
            "/api/auth/profile",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["username"] == "profile_user"
        assert "detection_stats" in data  # 包含检测统计

    def test_update_profile_success(self, client):
        """正常修改个人信息"""
        # 注册并登录
        client.post(
            "/api/auth/register",
            json={
                "username": "update_user",
                "email": "update@example.com",
                "password": "123456",
            },
        )
        login_response = client.post(
            "/api/auth/login",
            json={
                "username": "update_user",
                "password": "123456",
            },
        )
        token = login_response.json()["access_token"]

        # 修改个人信息
        response = client.put(
            "/api/auth/profile",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "phone": "13800138000",
                "email": "new_email@example.com",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["phone"] == "13800138000"
        assert data["email"] == "new_email@example.com"


class TestChangePassword:
    """修改密码测试"""

    def test_change_password_success(self, client):
        """正常修改密码"""
        # 注册并登录
        client.post(
            "/api/auth/register",
            json={
                "username": "change_pwd_user",
                "email": "changepwd@example.com",
                "password": "123456",
            },
        )
        login_response = client.post(
            "/api/auth/login",
            json={
                "username": "change_pwd_user",
                "password": "123456",
            },
        )
        token = login_response.json()["access_token"]

        # 修改密码
        response = client.put(
            "/api/auth/password",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "old_password": "123456",
                "new_password": "new654321",
            },
        )
        assert response.status_code == 200
        assert response.json()["message"] == "密码修改成功"

        # 使用新密码登录
        new_login = client.post(
            "/api/auth/login",
            json={
                "username": "change_pwd_user",
                "password": "new654321",
            },
        )
        assert new_login.status_code == 200

    def test_change_password_wrong_old(self, client):
        """旧密码错误"""
        # 注册并登录
        client.post(
            "/api/auth/register",
            json={
                "username": "wrong_old_user",
                "email": "wrongold@example.com",
                "password": "123456",
            },
        )
        login_response = client.post(
            "/api/auth/login",
            json={
                "username": "wrong_old_user",
                "password": "123456",
            },
        )
        token = login_response.json()["access_token"]

        response = client.put(
            "/api/auth/password",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "old_password": "wrong_password",
                "new_password": "new654321",
            },
        )
        assert response.status_code == 400
        assert response.json()["message"] == "旧密码错误"

    def test_change_password_without_token(self, client):
        """未登录修改密码"""
        response = client.put(
            "/api/auth/password",
            json={
                "old_password": "123456",
                "new_password": "new654321",
            },
        )
        assert response.status_code == 401
