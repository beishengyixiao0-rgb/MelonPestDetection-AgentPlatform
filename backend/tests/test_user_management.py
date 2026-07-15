"""用户角色和账户禁用测试。"""

from app.entity.db_models import User


def test_regular_user_cannot_manage_users(client, user_headers):
    response = client.get("/api/user/list", headers=user_headers)
    assert response.status_code == 403


def test_admin_can_promote_user(client, db_session, admin_headers):
    user = db_session.query(User).filter(User.username == "test_user").first()
    if not user:
        response = client.post(
            "/api/auth/register",
            json={"username": "promote_target", "email": "promote_target@example.com", "password": "123456"},
        )
        assert response.status_code == 201
        user = db_session.query(User).filter(User.username == "promote_target").first()

    response = client.put(
        f"/api/user/{user.id}",
        params={"role_name": "admin"},
        headers=admin_headers,
    )
    assert response.status_code == 200
    db_session.refresh(user)
    assert [user_role.role.name for user_role in user.user_roles] == ["admin"]


def test_disabling_user_blocks_login_and_existing_token(client, db_session, admin_headers, user_headers):
    user = db_session.query(User).filter(User.username == "test_user").first()
    assert user is not None

    response = client.delete(f"/api/user/{user.id}", headers=admin_headers)
    assert response.status_code == 200
    assert response.json()["message"] == "账户已禁用"

    existing_token_response = client.get("/api/auth/me", headers=user_headers)
    assert existing_token_response.status_code == 403

    login_response = client.post(
        "/api/auth/login",
        json={"username": "test_user", "password": "123456"},
    )
    assert login_response.status_code == 403
