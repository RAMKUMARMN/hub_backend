import asyncio
import sys
from urllib.parse import urlparse

from app.config import settings

# Intercept DATABASE_URL to use the isolated test database
original_url = settings.database_url

if "sqlite" in original_url:
    test_url = original_url
    settings.database_url = test_url
else:
    base_url, db_name = original_url.rsplit("/", 1)
    if "?" in db_name:
        db_name, query = db_name.split("?", 1)
        test_db_name = f"{db_name}_test"
        test_url = f"{base_url}/{test_db_name}?{query}"
    else:
        test_db_name = f"{db_name}" if db_name.endswith("_test") else f"{db_name}_test"
        test_url = f"{base_url}/{test_db_name}"
    settings.database_url = test_url


def pytest_sessionstart(session):
    """Auto-creates the isolated test DB and runs Alembic migrations."""
    import asyncpg
    from alembic.config import Config
    from alembic import command

    if "sqlite" in original_url:
        print("🚀 Running migrations on test SQLite database...", end="")
        alembic_cfg = Config("alembic.ini")
        alembic_cfg.set_main_option("sqlalchemy.url", test_url)
        command.upgrade(alembic_cfg, "head")
        print(" Done!\n")
        return

    admin_url = f"{base_url}/postgres"
    db_owner = urlparse(original_url).username

    async def setup_test_db():
        conn_str = admin_url.replace("postgresql+asyncpg://", "postgresql://")
        try:
            conn = await asyncpg.connect(conn_str)
        except Exception as e:
            print(f"\n⚠️ Database connection failed: {e}", file=sys.stderr)
            sys.exit(1)

        exists = await conn.fetchval(
            "SELECT 1 FROM pg_database WHERE datname = $1", test_db_name
        )
        if not exists:
            print(f"\n⚙️ Creating test database '{test_db_name}'...", end="")
            try:
                await conn.execute(f'CREATE DATABASE "{test_db_name}";')
                if db_owner:
                    await conn.execute(f'ALTER DATABASE "{test_db_name}" OWNER TO "{db_owner}";')
                print(" Done!")
            except Exception as e:
                print(f" Failed! (Proceeding assuming database already exists: {e})")
        await conn.close()

    asyncio.run(setup_test_db())

    print("🚀 Running migrations on test database...", end="")
    alembic_cfg = Config("alembic.ini")
    alembic_cfg.set_main_option("sqlalchemy.url", test_url)
    command.upgrade(alembic_cfg, "head")
    print(" Done!\n")


def pytest_sessionfinish(session, exitstatus):
    """Dispose the SQLAlchemy connection pool at the end of the test session."""
    from app.database import engine
    asyncio.run(engine.dispose())


import pytest
from unittest.mock import AsyncMock
from fastapi_limiter.depends import RateLimiter


@pytest.fixture(autouse=True)
def mock_rate_limiter():
    """Mock the fastapi-limiter to avoid dependency on Redis during tests."""
    RateLimiter.__call__ = AsyncMock(return_value=None)


@pytest.fixture(autouse=True)
def _disable_web_search_by_default():
    """Disable web search during tests so standard chat tests use chat_stream
    instead of chat_with_tools.  Tests that need web search (e.g.
    test_search_tool.py) explicitly set settings.enable_web_search = True."""
    original = settings.enable_web_search
    settings.enable_web_search = False
    yield
    settings.enable_web_search = original
