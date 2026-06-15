"""
Integration Testing Framework & Database Lifecycle Architecture

This module implements database-backed integration tests for authentication routes.
To protect the integrity of local development data, the test suite leverages a 
dynamic database isolation pattern.

================================================================================
1. ARCHITECTURE & WORKFLOW
================================================================================
- Environment Interception:
  Upon test invocation, `pytest` executes the root conftest.py. This intercepts 
  the DATABASE_URL from .env and programmatically rewrites the target database 
  name from 'cixiohub' to 'cixiohub_test'.
  
- Automated Lifecycle Management:
  The runner connects to PostgreSQL using the configured credentials, checks for the 
  existence of 'cixiohub_test', creates it if missing, and executes the complete 
  Alembic migration history ('alembic upgrade head') to sync the schema.

- Safe Test Isolation:
  An autouse pytest fixture (clean_database) truncates test tables before each 
  execution. This ensures a clean, predictable state for every test case while 
  leaving your manual development database ('cixiohub') completely untouched.

================================================================================
2. LOCAL DATABASE SETUP (Onboarding Guide)
================================================================================
Run the following SQL commands in your local PostgreSQL terminal to initialize 
the development environment:

  -- Create primary development database and owner role
  CREATE DATABASE cixiohub;
  CREATE USER cixiohub WITH PASSWORD 'cixiohub';
  ALTER DATABASE cixiohub OWNER TO cixiohub;

  -- Grant database creation privileges to the application role.
  -- This is required to allow the test framework to auto-create 'cixiohub_test'.
  ALTER ROLE cixiohub WITH CREATEDB;

================================================================================
3. RUNNING THE SUITE
================================================================================
Execute migrations on the dev database and run the test suite:
  alembic upgrade head
  pytest app/auth/tests/
"""


import pytest
import pytest_asyncio
from fastapi import status
from httpx import AsyncClient, ASGITransport
from sqlalchemy import select, text

from app.main import app
from app.database import AsyncSessionLocal
from app.models.user import User
from app.auth.security.password import hash_password

# ── Test constants (loaded from .env via app settings) ──────────────────────
from app.config import settings

TEST_EMAIL = settings.test_email
TEST_PASSWORD = settings.test_password
TEST_NAME = settings.test_name
TEST_PHONE = settings.test_phone


# ── Fixtures ────────────────────────────────────────────────────────────────

@pytest_asyncio.fixture
async def client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


@pytest_asyncio.fixture(autouse=True)
async def clean_database():
    """Dispose stale pool connections and truncate tables before each test.

    Each test function gets its own event loop. The global engine was created
    at import time on a different loop, so we must dispose the pool to force
    fresh connections bound to the current test's loop.
    """
    from app.database import engine
    await engine.dispose()
    from app.redis import redis_client
    try:
        await redis_client.connection_pool.disconnect()
    except Exception:
        pass
    async with AsyncSessionLocal() as session:
        await session.execute(text("TRUNCATE TABLE users CASCADE;"))
        await session.commit()
    yield


@pytest_asyncio.fixture
async def seed_user():
    """Insert a standard test user and return the ORM instance."""
    async with AsyncSessionLocal() as session:
        user = User(
            email=TEST_EMAIL,
            full_name=TEST_NAME,
            hashed_password=hash_password(TEST_PASSWORD),
            is_active=True,
            status="active",
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)
        return user


# ── Registration Tests ──────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_register_route_success(client):
    response = await client.post(
        "/api/v1/auth/register",
        json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD,
            "full_name": TEST_NAME,
            "phone": TEST_PHONE,
        },
    )

    assert response.status_code == status.HTTP_201_CREATED
    data = response.json()
    assert data["email"] == TEST_EMAIL
    assert data["full_name"] == TEST_NAME
    assert "hashed_password" not in data

    async with AsyncSessionLocal() as session:
        result = await session.execute(select(User).where(User.email == TEST_EMAIL))
        db_user = result.scalar_one_or_none()
        assert db_user is not None
        assert db_user.full_name == TEST_NAME


@pytest.mark.asyncio
async def test_register_route_duplicate_email(client):
    await client.post(
        "/api/v1/auth/register",
        json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD,
            "full_name": TEST_NAME,
        },
    )

    response = await client.post(
        "/api/v1/auth/register",
        json={
            "email": TEST_EMAIL,
            "password": "anotherpassword",
            "full_name": "Another Name",
        },
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.json()["detail"] == "Email already registered"


@pytest.mark.asyncio
async def test_register_route_invalid_email(client):
    response = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "invalid-email-format",
            "password": TEST_PASSWORD,
            "full_name": TEST_NAME,
        },
    )
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


# ── Login Tests ─────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_login_route_success(client, seed_user):
    response = await client.post(
        "/api/v1/auth/login",
        json={"email": TEST_EMAIL, "password": TEST_PASSWORD},
    )

    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data


@pytest.mark.asyncio
async def test_login_route_wrong_password(client, seed_user):
    response = await client.post(
        "/api/v1/auth/login",
        json={"email": TEST_EMAIL, "password": "incorrectpassword"},
    )

    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert response.json()["detail"] == "Invalid credentials"


# ── Token Refresh Tests ─────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_refresh_route_success(client, seed_user):
    login_response = await client.post(
        "/api/v1/auth/login",
        json={"email": TEST_EMAIL, "password": TEST_PASSWORD},
    )
    refresh_token = login_response.json()["refresh_token"]

    response = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": refresh_token},
    )

    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data


# ── /me Endpoint Tests ──────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_me_route_authenticated(client, seed_user):
    login_response = await client.post(
        "/api/v1/auth/login",
        json={"email": TEST_EMAIL, "password": TEST_PASSWORD},
    )
    access_token = login_response.json()["access_token"]

    response = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {access_token}"},
    )

    assert response.status_code == status.HTTP_200_OK
    assert response.json()["email"] == TEST_EMAIL


@pytest.mark.asyncio
async def test_me_route_unauthenticated(client):
    response = await client.get("/api/v1/auth/me")
    assert response.status_code == status.HTTP_401_UNAUTHORIZED

