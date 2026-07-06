import pytest
import pytest_asyncio
import uuid
from fastapi import status
from httpx import AsyncClient, ASGITransport
from sqlalchemy import select, text

from app.main import app
from app.database import AsyncSessionLocal
from app.models.user import User
from app.auth.security.password import hash_password
from app.auth.services.otp_service import OTPService
from app.redis import redis_client

TEST_EMAIL = "student_verify@tkmce.ac.in"
TEST_PASSWORD = "securepassword123"
TEST_NAME = "verifyuser"


@pytest_asyncio.fixture
async def client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


@pytest_asyncio.fixture(autouse=True)
async def clean_redis_and_db():
    # Clear Redis & disconnect pool to prevent loop mismatch
    try:
        await redis_client.connection_pool.disconnect()
    except Exception:
        pass
    await redis_client.flushdb()
    # Clear DB
    from app.database import engine
    await engine.dispose()
    async with AsyncSessionLocal() as session:
        await session.execute(text("TRUNCATE TABLE users CASCADE;"))
        await session.commit()
    yield
    await redis_client.flushdb()
    try:
        await redis_client.connection_pool.disconnect()
    except Exception:
        pass


# ── OTP Service Unit Tests ──────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_generate_otp():
    """Verify generated OTP is always a 6-digit string of numbers."""
    user_id = uuid.uuid4()
    code = await OTPService.generate_otp(user_id, "verify_email")
    assert len(code) == 6
    assert code.isdigit()

    # Verify key was stored in Redis
    stored = await redis_client.get(f"otp:verify_email:{str(user_id)}")
    assert stored == code


@pytest.mark.asyncio
async def test_verify_otp_success():
    """Verify correct code resolves as True and is deleted on use."""
    user_id = uuid.uuid4()
    code = await OTPService.generate_otp(user_id, "verify_email")

    verified = await OTPService.verify_otp(user_id, code, "verify_email")
    assert verified is True

    # Verify code was deleted from Redis
    stored = await redis_client.get(f"otp:verify_email:{str(user_id)}")
    assert stored is None


@pytest.mark.asyncio
async def test_verify_otp_wrong_code():
    """Verify wrong code resolves as False and is not deleted."""
    user_id = uuid.uuid4()
    code = await OTPService.generate_otp(user_id, "verify_email")

    verified = await OTPService.verify_otp(user_id, "000000" if code != "000000" else "111111", "verify_email")
    assert verified is False

    # Verify code still exists in Redis
    stored = await redis_client.get(f"otp:verify_email:{str(user_id)}")
    assert stored == code


@pytest.mark.asyncio
async def test_verify_otp_expired():
    """Verify expired OTP code resolves as False."""
    user_id = uuid.uuid4()
    # Use 1 second expire and sleep 1.1s to simulate expiration
    import asyncio
    code = await OTPService.generate_otp(user_id, "verify_email", expires_in_seconds=1)
    await asyncio.sleep(1.1)

    verified = await OTPService.verify_otp(user_id, code, "verify_email")
    assert verified is False


@pytest.mark.asyncio
async def test_resend_otp_invalidates_previous():
    """Verify resending invalidates older codes."""
    user_id = uuid.uuid4()
    code1 = await OTPService.generate_otp(user_id, "verify_email")
    code2 = await OTPService.resend_otp(user_id, "verify_email")

    assert code1 != code2

    # Verify code1 is invalid now
    verified1 = await OTPService.verify_otp(user_id, code1, "verify_email")
    assert verified1 is False

    # Verify code2 is valid
    verified2 = await OTPService.verify_otp(user_id, code2, "verify_email")
    assert verified2 is True


# ── OTP Route Integration Tests ──────────────────────────────────────────────

@pytest.mark.asyncio
async def test_register_creates_inactive_user_and_sends_otp(client):
    """Verify registration creates user as inactive and creates Redis OTP."""
    response = await client.post(
        "/api/v1/auth/register",
        json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD,
            "full_name": TEST_NAME,
        },
    )
    assert response.status_code == status.HTTP_201_CREATED

    async with AsyncSessionLocal() as session:
        result = await session.execute(select(User).where(User.email == TEST_EMAIL))
        user = result.scalar_one_or_none()
        assert user is not None
        assert user.is_active is False
        assert user.status == "pending"

        # Check Redis key exists
        otp_key = f"otp:verify_email:{str(user.id)}"
        stored = await redis_client.get(otp_key)
        assert stored is not None
        assert len(stored) == 6


@pytest.mark.asyncio
async def test_verify_otp_route_success(client):
    """Verify calling verify-otp route successfully activates user."""
    # 1. Register user
    await client.post(
        "/api/v1/auth/register",
        json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD,
            "full_name": TEST_NAME,
        },
    )

    async with AsyncSessionLocal() as session:
        user = (await session.execute(select(User).where(User.email == TEST_EMAIL))).scalar_one()

    # 2. Retrieve OTP directly from Redis
    code = await redis_client.get(f"otp:verify_email:{str(user.id)}")

    # 3. Call verification route
    response = await client.post(
        "/api/v1/auth/verify-otp",
        json={"email": TEST_EMAIL, "otp": code},
    )
    assert response.status_code == status.HTTP_200_OK
    assert response.json()["detail"] == "Email verified successfully"

    # 4. Verify user status in DB
    async with AsyncSessionLocal() as session:
        user_db = (await session.execute(select(User).where(User.email == TEST_EMAIL))).scalar_one()
        assert user_db.is_active is True
        assert user_db.status == "active"


@pytest.mark.asyncio
async def test_verify_otp_route_invalid(client):
    """Verify verify-otp route returns 400 for incorrect code."""
    await client.post(
        "/api/v1/auth/register",
        json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD,
            "full_name": TEST_NAME,
        },
    )

    response = await client.post(
        "/api/v1/auth/verify-otp",
        json={"email": TEST_EMAIL, "otp": "000000"},
    )
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.json()["detail"] == "Invalid or expired verification code"


@pytest.mark.asyncio
async def test_resend_otp_route_success(client):
    """Verify resend-otp route resets code and invalidates older one."""
    await client.post(
        "/api/v1/auth/register",
        json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD,
            "full_name": TEST_NAME,
        },
    )

    async with AsyncSessionLocal() as session:
        user = (await session.execute(select(User).where(User.email == TEST_EMAIL))).scalar_one()

    code1 = await redis_client.get(f"otp:verify_email:{str(user.id)}")

    # Call resend route
    response = await client.post(
        "/api/v1/auth/resend-otp",
        json={"email": TEST_EMAIL},
    )
    assert response.status_code == status.HTTP_200_OK

    code2 = await redis_client.get(f"otp:verify_email:{str(user.id)}")
    assert code1 != code2


# ── Password Reset Integration Tests ─────────────────────────────────────────

@pytest.mark.asyncio
async def test_forgot_password_route_success(client):
    """Verify forgot-password route returns 200 for a registered email."""
    # Register user
    await client.post(
        "/api/v1/auth/register",
        json={"email": TEST_EMAIL, "password": TEST_PASSWORD, "full_name": TEST_NAME},
    )

    response = await client.post(
        "/api/v1/auth/forgot-password",
        json={"email": TEST_EMAIL},
    )
    assert response.status_code == status.HTTP_200_OK
    assert "reset link has been sent" in response.json()["detail"]


@pytest.mark.asyncio
async def test_forgot_password_route_unknown_email(client):
    """Verify forgot-password route returns 200 silently for unknown emails."""
    response = await client.post(
        "/api/v1/auth/forgot-password",
        json={"email": "nonexistent@tkmce.ac.in"},
    )
    assert response.status_code == status.HTTP_200_OK
    assert "reset link has been sent" in response.json()["detail"]


@pytest.mark.asyncio
async def test_reset_password_route_success(client, monkeypatch):
    """Verify password reset updates password and allows login with new credentials."""
    # 1. Register & verify user to activate account
    await client.post(
        "/api/v1/auth/register",
        json={"email": TEST_EMAIL, "password": TEST_PASSWORD, "full_name": TEST_NAME},
    )
    async with AsyncSessionLocal() as session:
        user = (await session.execute(select(User).where(User.email == TEST_EMAIL))).scalar_one()
    otp_code = await redis_client.get(f"otp:verify_email:{str(user.id)}")
    await client.post("/api/v1/auth/verify-otp", json={"email": TEST_EMAIL, "otp": otp_code})

    # Mock email sender to capture reset token
    captured_tokens = []
    async def mock_send_email(email, link):
        token = link.split("token=")[1]
        captured_tokens.append(token)

    monkeypatch.setattr(
        "app.auth.services.password_reset_service.send_password_reset_email",
        mock_send_email,
    )

    # 2. Trigger forgot password
    await client.post("/api/v1/auth/forgot-password", json={"email": TEST_EMAIL})
    assert len(captured_tokens) == 1
    token = captured_tokens[0]

    # 3. Reset password
    reset_response = await client.post(
        "/api/v1/auth/reset-password",
        json={"token": token, "new_password": "newsecurepassword123"},
    )
    assert reset_response.status_code == status.HTTP_200_OK
    assert reset_response.json()["detail"] == "Password has been reset successfully."

    # 4. Attempt login with old password (should fail)
    old_login = await client.post(
        "/api/v1/auth/login",
        json={"email": TEST_EMAIL, "password": TEST_PASSWORD},
    )
    assert old_login.status_code == status.HTTP_401_UNAUTHORIZED

    # 5. Attempt login with new password (should succeed)
    new_login = await client.post(
        "/api/v1/auth/login",
        json={"email": TEST_EMAIL, "password": "newsecurepassword123"},
    )
    assert new_login.status_code == status.HTTP_200_OK
    assert "access_token" in new_login.json()


@pytest.mark.asyncio
async def test_reset_password_token_replay_fails(client, monkeypatch):
    """Verify that a reset token cannot be reused after a successful reset."""
    await client.post(
        "/api/v1/auth/register",
        json={"email": TEST_EMAIL, "password": TEST_PASSWORD, "full_name": TEST_NAME},
    )

    captured_tokens = []
    async def mock_send_email(email, link):
        captured_tokens.append(link.split("token=")[1])

    monkeypatch.setattr(
        "app.auth.services.password_reset_service.send_password_reset_email",
        mock_send_email,
    )

    await client.post("/api/v1/auth/forgot-password", json={"email": TEST_EMAIL})
    token = captured_tokens[0]

    # First reset succeeds
    res1 = await client.post(
        "/api/v1/auth/reset-password",
        json={"token": token, "new_password": "newsecurepassword123"},
    )
    assert res1.status_code == status.HTTP_200_OK

    # Second reset with same token fails
    res2 = await client.post(
        "/api/v1/auth/reset-password",
        json={"token": token, "new_password": "anotherpassword123"},
    )
    assert res2.status_code == status.HTTP_400_BAD_REQUEST
    assert res2.json()["detail"] == "This password reset link has already been used"


@pytest.mark.asyncio
async def test_reset_password_expired_token(client):
    """Verify that an expired token returns 400 Bad Request."""
    # Generate an expired JWT manually
    from jose import jwt
    from app.config import settings
    from datetime import datetime, timedelta, timezone

    payload = {
        "sub": str(uuid.uuid4()),
        "purpose": "password_reset",
        "hash": "somehashsegment",
        "exp": datetime.now(timezone.utc) - timedelta(minutes=1),  # Expired 1 min ago
    }
    expired_token = jwt.encode(payload, settings.secret_key, algorithm=settings.algorithm)

    response = await client.post(
        "/api/v1/auth/reset-password",
        json={"token": expired_token, "new_password": "newsecurepassword123"},
    )
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.json()["detail"] == "Invalid or expired password reset link"


@pytest.mark.asyncio
async def test_non_institutional_email_requires_admin_approval(client):
    """Verify that registering with a non-institutional email requires admin approval.
    
    1. Register with a non-institutional email (e.g. user@gmail.com).
    2. Retrieve OTP and verify it.
    3. Verify that user status is 'pending' and is_active is True.
    4. Attempt login, verify it fails with 403 Forbidden.
    5. Admin approves the user.
    6. Attempt login, verify it succeeds.
    """
    non_inst_email = "external_user@gmail.com"
    non_inst_password = "password123"
    non_inst_name = "External User"

    # 1. Register user
    reg_resp = await client.post(
        "/api/v1/auth/register",
        json={
            "email": non_inst_email,
            "password": non_inst_password,
            "full_name": non_inst_name,
        },
    )
    assert reg_resp.status_code == status.HTTP_201_CREATED

    async with AsyncSessionLocal() as session:
        user = (await session.execute(select(User).where(User.email == non_inst_email))).scalar_one()
        assert user.is_active is False
        assert user.status == "pending"

    # 2. Verify OTP
    code = await redis_client.get(f"otp:verify_email:{str(user.id)}")
    assert code is not None

    verify_resp = await client.post(
        "/api/v1/auth/verify-otp",
        json={"email": non_inst_email, "otp": code},
    )
    assert verify_resp.status_code == status.HTTP_200_OK

    # 3. Check status is still pending after OTP verification
    async with AsyncSessionLocal() as session:
        user_db = (await session.execute(select(User).where(User.email == non_inst_email))).scalar_one()
        assert user_db.is_active is True
        assert user_db.status == "pending"

    # 4. Attempt login, must fail with 403 Forbidden
    login_resp = await client.post(
        "/api/v1/auth/login",
        json={"email": non_inst_email, "password": non_inst_password},
    )
    assert login_resp.status_code == status.HTTP_403_FORBIDDEN
    assert login_resp.json()["detail"] == "Account pending admin approval"

    # 5. Admin approves the user
    async with AsyncSessionLocal() as session:
        from app.auth.repositories.user_repository import UserRepository
        await UserRepository(session).approve_user(user.id)

    # 6. Attempt login, must succeed now
    login_resp_approved = await client.post(
        "/api/v1/auth/login",
        json={"email": non_inst_email, "password": non_inst_password},
    )
    assert login_resp_approved.status_code == status.HTTP_200_OK
    assert "access_token" in login_resp_approved.json()
