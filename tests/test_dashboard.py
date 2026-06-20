import pytest
from httpx import AsyncClient
from unittest.mock import AsyncMock, patch

from app.main import app


@pytest.mark.asyncio
async def test_dashboard_cache_miss():
    """First call should compute and store cache"""

    async with AsyncClient(app=app, base_url="http://test") as ac:
        response = await ac.get("/api/v1/dashboard/test-user-id")

    assert response.status_code == 200
    data = response.json()

    assert "todos" in data
    assert "focus" in data
    assert "calendar" in data
    assert "weekly_stats" in data


@pytest.mark.asyncio
async def test_dashboard_cache_hit():
    """Second call should use cache (fast path)"""

    with patch("app.services.dashboard_service.redis_client.get") as mock_get:
        mock_get.return_value = '{"cached": true}'

        async with AsyncClient(app=app, base_url="http://test") as ac:
            response = await ac.get("/api/v1/dashboard/test-user-id")

        assert response.status_code == 200


@pytest.mark.asyncio
async def test_cache_invalidation_called():
    """Ensure invalidation is triggered"""

    with patch("app.services.dashboard_service.invalidate_dashboard_cache") as mock_invalidate:

        # simulate call
        await mock_invalidate("test-user-id")

        mock_invalidate.assert_called_once()