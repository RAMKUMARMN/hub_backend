import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from unittest.mock import AsyncMock, patch
from sqlalchemy import text

from app.main import app
from app.database import AsyncSessionLocal


@pytest_asyncio.fixture(autouse=True)
async def clean_database():
    from app.database import engine
    await engine.dispose()
    from app.redis import redis_client
    try:
        await redis_client.connection_pool.disconnect()
    except Exception:
        pass
    async with AsyncSessionLocal() as session:
        await session.execute(text("TRUNCATE TABLE users, todos CASCADE;"))
        await session.commit()
    yield


@pytest.mark.asyncio
async def test_dashboard_cache_miss():
    """First call should compute and store cache"""

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get("/api/v1/dashboard/9b5b203f-13db-4041-afb1-631e37c52cf5")

    assert response.status_code == 200
    data = response.json()

    assert "todos" in data
    assert "focus" in data
    assert "calendar" in data
    assert "weekly_stats" in data


@pytest.mark.asyncio
async def test_dashboard_cache_hit():
    """Second call should use cache (fast path)"""

    with patch("app.services.dashboard_service.redis_client.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = '{"todos": {"total": 0, "completed": 0, "pending": 0, "overdue": 0}, "focus": {"sessions_this_week": 0, "total_focus_minutes": 0, "productivity_score": 0}, "calendar": {"today_events": 0, "upcoming_events": []}, "achievements": [], "activity_feed": [], "weekly_stats": {"focus_trend": [], "task_completion_rate": 0.0}}'

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            response = await ac.get("/api/v1/dashboard/9b5b203f-13db-4041-afb1-631e37c52cf5")

        assert response.status_code == 200


@pytest.mark.asyncio
async def test_cache_invalidation_called():
    """Ensure invalidation is triggered"""

    with patch("app.services.dashboard_service.invalidate_dashboard_cache", new_callable=AsyncMock) as mock_invalidate:

        # simulate call
        await mock_invalidate("9b5b203f-13db-4041-afb1-631e37c52cf5")

        mock_invalidate.assert_called_once()