"""
Auth tests — Person 1 & 2 write here.

TODO:
  - test_register_success: POST /auth/register with valid payload → 201
  - test_register_duplicate_email: second registration with same email → 400
  - test_login_success: valid credentials → 200 + TokenResponse
  - test_login_wrong_password: invalid credentials → 401
  - test_refresh_token: valid refresh token → 200 + new TokenResponse
  - test_me_authenticated: GET /auth/me with valid Bearer → UserResponse
  - test_me_unauthenticated: missing token → 401
"""

from fastapi.testclient import TestClient
from app.main import app
from app.auth.security.jwt import create_access_token

client = TestClient(app)

def test_rbac_admin_access():
    """Test that RBAC works directly from the JWT without a DB lookup."""
    
    # 1. Create a fake admin token
    admin_token = create_access_token({"sub": "123", "role": "admin", "type": "access"})
    
    # 2. Create a fake normal user token
    user_token = create_access_token({"sub": "456", "role": "user", "type": "access"})

    # 3. Test hitting an admin-only endpoint as a normal user
    # It should immediately return 403 Forbidden because of the token payload
    response_user = client.get(
        "/api/v1/admin/users", 
        headers={"Authorization": f"Bearer {user_token}"}
    )
    assert response_user.status_code == 403
    assert response_user.json()["detail"] == "Admin access required"

    # 4. Test hitting an admin-only endpoint as an admin
    # It should pass the RBAC check (it will not return 403)
    # (Note: it may return 200, or 500/SQL error if your local DB isn't fully set up, 
    # but the crucial part is that the security dependency let the request through!)
    response_admin = client.get(
        "/api/v1/admin/users", 
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert response_admin.status_code != 403


def test_token_rotation():
    """
    Test the token rotation pattern:
    1. Register and login to get initial tokens.
    2. Refresh using the refresh token -> success, returns new pair.
    3. Attempt to refresh again with the SAME old refresh token -> fails (401).
    """
    import uuid
    email = f"test_{uuid.uuid4().hex[:8]}@tkmce.ac.in"
    password = "SecurePassword123!"
    
    # 1. Register
    res = client.post("/api/v1/auth/register", json={
        "email": email,
        "password": password,
        "full_name": "Test User"
    })
    assert res.status_code == 201

    # 2. Login
    res = client.post("/api/v1/auth/login", json={
        "email": email,
        "password": password
    })
    assert res.status_code == 200
    tokens = res.json()
    refresh_token_1 = tokens["refresh_token"]

    # 3. Refresh 1 - Should Succeed
    res = client.post("/api/v1/auth/refresh", json={
        "refresh_token": refresh_token_1
    })
    assert res.status_code == 200
    new_tokens = res.json()
    assert refresh_token_1 != new_tokens["refresh_token"]

    # 4. Refresh 2 with OLD token - Should Fail (Token Rotation / Revocation)
    res = client.post("/api/v1/auth/refresh", json={
        "refresh_token": refresh_token_1
    })
    assert res.status_code == 401
    assert "Invalid or revoked refresh token" in res.json()["detail"]
