import pytest
import pytest_asyncio
from unittest.mock import patch
from httpx import AsyncClient, ASGITransport
from app.main import app

@pytest_asyncio.fixture
async def client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c

@pytest.mark.asyncio
@patch("app.routers.auth.verify_google_token")
async def test_google_login_new_user(mock_verify, client):
    # Mock verify_google_token to return valid user details
    mock_verify.return_value = {
        "email": "new_user@example.com",
        "name": "New Google User",
        "picture": "https://example.com/avatar.png",
        "aud": "mocked_client_id"
    }

    response = await client.post(
        "/api/v1/auth/google",
        json={"id_token": "valid_mocked_token"}
    )
    
    assert response.status_code == 200
    json_data = response.json()
    assert "access_token" in json_data
    assert "refresh_token" in json_data
    assert json_data["token_type"] == "bearer"

@pytest.mark.asyncio
@patch("app.routers.auth.verify_google_token")
async def test_google_login_invalid_token(mock_verify, client):
    # Mock verify_google_token to return None
    mock_verify.return_value = None

    response = await client.post(
        "/api/v1/auth/google",
        json={"id_token": "invalid_mocked_token"}
    )
    
    assert response.status_code == 400
    assert response.json()["detail"] == "Invalid Google token"
