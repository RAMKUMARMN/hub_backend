import asyncio
import sys
from urllib.parse import urlparse

from app.config import settings

# Intercept DATABASE_URL to use the isolated test database
original_url = settings.database_url
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
            await conn.execute(f'CREATE DATABASE "{test_db_name}";')
            if db_owner:
                await conn.execute(f'ALTER DATABASE "{test_db_name}" OWNER TO "{db_owner}";')
            print(" Done!")
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
