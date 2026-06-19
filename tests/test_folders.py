import pytest
import pytest_asyncio
import uuid

pytestmark = pytest.mark.asyncio

from fastapi import status
from httpx import AsyncClient, ASGITransport
from sqlalchemy import select, text

from app.main import app
from app.database import AsyncSessionLocal
from app.models.user import User
from app.models.folder import DocumentFolder
from app.models.document import Document
from app.auth.security.password import hash_password
from app.config import settings

TEST_EMAIL = settings.test_email
TEST_PASSWORD = settings.test_password
TEST_NAME = settings.test_name

@pytest_asyncio.fixture
async def client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c

@pytest_asyncio.fixture(autouse=True)
async def clean_database():
    from app.database import engine
    from app.redis import redis_client
    await engine.dispose()
    try:
        await redis_client.aclose()
    except Exception:
        pass
    async with AsyncSessionLocal() as session:
        await session.execute(text("TRUNCATE TABLE users, document_folders, documents CASCADE;"))
        await session.commit()
    yield


@pytest_asyncio.fixture
async def seed_user():
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

@pytest_asyncio.fixture
async def auth_headers(client, seed_user):
    login_response = await client.post(
        "/api/v1/auth/login",
        json={"email": TEST_EMAIL, "password": TEST_PASSWORD},
    )
    access_token = login_response.json()["access_token"]
    return {"Authorization": f"Bearer {access_token}"}

async def test_create_and_list_folders(client, auth_headers):
    # Create folder
    response = await client.post(
        "/api/v1/document-folders/",
        json={"name": "Semester 1"},
        headers=auth_headers
    )
    assert response.status_code == status.HTTP_201_CREATED
    assert response.json()["name"] == "Semester 1"

    # List folders
    list_response = await client.get("/api/v1/document-folders/", headers=auth_headers)
    assert list_response.status_code == status.HTTP_200_OK
    assert len(list_response.json()) == 1
    assert list_response.json()[0]["name"] == "Semester 1"

async def test_delete_folder_unassigns_documents(client, auth_headers, seed_user):
    # Setup: Create folder and a document assigned to it
    async with AsyncSessionLocal() as session:
        folder = DocumentFolder(user_id=seed_user.id, name="Class Materials")
        session.add(folder)
        await session.commit()
        await session.refresh(folder)
        
        doc = Document(
            user_id=seed_user.id,
            filename="syllabus.pdf",
            file_type="pdf",
            file_size=1024,
            storage_path="/uploads/syllabus.pdf",
            folder_id=folder.id,
            processed=False
        )
        session.add(doc)
        await session.commit()
        await session.refresh(doc)
        
        folder_id = folder.id
        doc_id = doc.id

    # Delete the folder
    delete_response = await client.delete(f"/api/v1/document-folders/{folder_id}", headers=auth_headers)
    assert delete_response.status_code == status.HTTP_204_NO_CONTENT

    # Verify document is unassigned
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Document).where(Document.id == doc_id))
        updated_doc = result.scalar_one()
        assert updated_doc.folder_id is None
