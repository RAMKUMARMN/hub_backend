"""
RabbitMQ producer — publishes notification tasks
and generic jobs to RabbitMQ.

Called by backend APIs and internal services
to enqueue work.
"""

import logging

import aio_pika

from app.config import settings
from app.queue.schemas import Job

logger = logging.getLogger(__name__)


QUEUE_NAMES = {
    # Notification queues
    "email": "email.process",
    "sms": "sms.process",
    "push": "push.process",
    "whatsapp": "push.process",

    # Bulk notifications
    "notify.bulk_email": "notify.bulk_email",
    "notify.bulk_sms": "notify.bulk_sms",

    # AI / RAG queues
    "ai.orchestration": "ai.orchestration",
    "analytics.events": "analytics.events",
    "embedding.processing": "embedding.processing",
    "file.uploads": "file.uploads",
    "memory.processing": "memory.processing",
    "rag.bulk_ingest": "rag.bulk_ingest",
}





async def publish_job(
    job: Job,
) -> None:
    """
    Publish a generic Job message.

    Used for:
    - RAG ingestion
    - AI orchestration
    - Embedding processing
    - Memory processing
    - Analytics events
    - File uploads
    """

    connection = await aio_pika.connect_robust(
        settings.rabbitmq_url
    )

    async with connection:

        channel = await connection.channel()

        queue = await channel.declare_queue(
            job.queue,
            durable=True,
        )

        await channel.default_exchange.publish(
            aio_pika.Message(
                body=job.model_dump_json().encode(),
                delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
            ),
            routing_key=queue.name,
        )

        logger.info(
            "Published job %s to %s",
            job.job_id,
            queue.name,
        )