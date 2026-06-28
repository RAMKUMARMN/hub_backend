"""
Shared Redis Connection Pool infrastructure.
Provides a single connection instance used by rate limiters, session managers,
and OTP services to prevent multiple open connection pools.
"""
import redis.asyncio as redis
from app.config import settings

# Create the async Redis connection client.
# decode_responses=True ensures redis returns standard Python strings instead of bytes.
redis_client = redis.from_url(
    settings.redis_url,
    encoding="utf-8",
    decode_responses=True,
    protocol=2
)
