---
name: backend-service-integration
description: Set up service layer business logic and integrate with RabbitMQ, Redis, Ollama, ChromaDB, and MinIO/S3 following the project's service patterns.
metadata:
  model: models/gemini-3.1-pro-preview
  last_modified: Mon, 29 Jun 2026 00:00:00 GMT
---

# Backend Service Integration

## Contents
- [Service Pattern](#service-pattern)
- [RabbitMQ](#rabbitmq)
- [Redis](#redis)
- [Ollama](#ollama)
- [ChromaDB](#chromadb)
- [MinIO/S3](#minio-s3)
- [Verification](#verification)

## Service Pattern

Services are stateless functions in `app/services/`:

```python
# app/services/workspace_service.py
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.workspace import Workspace
from app.schemas.workspace import WorkspaceCreate


async def get_workspaces(db: AsyncSession, user_id: str) -> list[Workspace]:
    result = await db.execute(
        select(Workspace).where(Workspace.owner_id == user_id)
    )
    return result.scalars().all()


async def create_workspace(
    db: AsyncSession, data: WorkspaceCreate, user_id: str
) -> Workspace:
    workspace = Workspace(name=data.name, description=data.description, owner_id=user_id)
    db.add(workspace)
    await db.commit()
    await db.refresh(workspace)
    return workspace
```

## RabbitMQ

```python
# app/services/queue_service.py
import json
from aio_pika import connect_robust, Message, DeliveryMode


async def publish(queue_name: str, data: dict):
    connection = await connect_robust(settings.rabbitmq_url)
    async with connection:
        channel = await connection.channel()
        await channel.declare_queue(queue_name, durable=True)
        message = Message(
            body=json.dumps(data).encode(),
            delivery_mode=DeliveryMode.PERSISTENT,
        )
        await channel.default_exchange.publish(message, routing_key=queue_name)
```

## Redis

```python
# app/services/cache_service.py
import json
from redis.asyncio import Redis

redis = Redis.from_url(settings.redis_url)


async def cache_get(key: str) -> dict | None:
    value = await redis.get(key)
    return json.loads(value) if value else None


async def cache_set(key: str, value: dict, ttl: int = 300):
    await redis.setex(key, ttl, json.dumps(value))
```

## Ollama

```python
# app/services/llm_service.py
import httpx


async def generate(prompt: str, model: str = "llama3.2:3b") -> str:
    async with httpx.AsyncClient(timeout=60) as client:
        response = await client.post(
            f"{settings.ollama_url}/api/generate",
            json={"model": model, "prompt": prompt, "stream": False},
        )
        response.raise_for_status()
        return response.json()["response"]
```

## ChromaDB

```python
# app/services/rag_service.py
import chromadb


chroma_client = chromadb.HttpClient(
    host=settings.chromadb_host, port=settings.chromadb_port
)


def search_collection(collection_name: str, query: str, n: int = 5):
    collection = chroma_client.get_or_create_collection(collection_name)
    results = collection.query(query_texts=[query], n_results=n)
    return results
```

## MinIO/S3

```python
# app/services/storage_service.py
import boto3
from botocore.config import Config


s3_client = boto3.client(
    "s3",
    endpoint_url=settings.minio_url,
    aws_access_key_id=settings.minio_access_key,
    aws_secret_access_key=settings.minio_secret_key,
    config=Config(signature_version="s3v4"),
)


async def upload_file(bucket: str, key: str, data: bytes):
    s3_client.put_object(Bucket=bucket, Key=key, Body=data)


async def get_presigned_url(bucket: str, key: str, expires: int = 3600) -> str:
    return s3_client.generate_presigned_url(
        "get_object", Params={"Bucket": bucket, "Key": key}, ExpiresIn=expires
    )
```

## Verification

1. `python -c "from app.services.<name> import *"` — service imports
2. `pytest tests/test_services.py -q` — service tests pass
3. External connections are mocked in unit tests
4. Integration tests use test containers where available
