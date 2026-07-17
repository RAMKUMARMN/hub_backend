import json
import aio_pika
from app.config import settings

async def publish_focus_completed(payload: dict):
    """
    Publish a completed focus session event payload to RabbitMQ.
    """
    connection = await aio_pika.connect_robust(settings.rabbitmq_url)
    async with connection:
        channel = await connection.channel()
        
        # Declare topic exchange to route achievements
        exchange = await channel.declare_exchange(
            "cixio.topic",
            aio_pika.ExchangeType.TOPIC,
            durable=True
        )
        
        message = aio_pika.Message(
            body=json.dumps(payload).encode("utf-8"),
            delivery_mode=aio_pika.DeliveryMode.PERSISTENT
        )
        
        await exchange.publish(
            message,
            routing_key="focus.session.completed"
        )


async def publish_user_cleanup(user_id: str):
    """
    Publish user cleanup event after soft delete.
    """
    connection = await aio_pika.connect_robust(settings.rabbitmq_url)

    async with connection:
        channel = await connection.channel()

        exchange = await channel.declare_exchange(
            "cixio.topic",
            aio_pika.ExchangeType.TOPIC,
            durable=True
        )

        message = aio_pika.Message(
            body=json.dumps({"user_id": user_id}).encode("utf-8"),
            delivery_mode=aio_pika.DeliveryMode.PERSISTENT
        )

        await exchange.publish(
            message,
            routing_key="admin.user.cleanup"
        )


async def publish_notification_to_queue(
    channel: str,
    recipient: str,
    subject: str | None = None,
    body: str = "",
    message_type: str = "general",
    priority: str = "high",
    html_body: str | None = None,
    title: str | None = None,
    data: dict | None = None,
) -> None:
    """
    Publish a notification to the specified priority queue ('high', 'medium', 'low')
    with support for dead-lettering (DLA) and 3 retry attempts on failure.
    """
    import asyncio
    import logging
    logger = logging.getLogger(__name__)

    payload = {
        "channel": channel,
        "recipient": recipient,
        "subject": subject,
        "body": body,
        "html_body": html_body,
        "title": title or subject,
        "message_type": message_type,
        "priority": priority,
        "data": data or {},
    }

    max_retries = 3
    for attempt in range(1, max_retries + 2):  # 1 initial attempt + 3 retries = 4 total attempts
        try:
            connection = await aio_pika.connect_robust(settings.rabbitmq_url)
            async with connection:
                channel_obj = await connection.channel()

                # Declare Dead Letter Exchange (DLX) and Dead Letter Queue (DLQ/DLA)
                dlx = await channel_obj.declare_exchange(
                    "dla.exchange",
                    aio_pika.ExchangeType.DIRECT,
                    durable=True
                )
                dla_queue = await channel_obj.declare_queue(
                    "dla",
                    durable=True
                )
                await dla_queue.bind(dlx, routing_key="dla")

                # Declare Main Exchange
                exchange = await channel_obj.declare_exchange(
                    "notification.exchange",
                    aio_pika.ExchangeType.DIRECT,
                    durable=True
                )

                # Ensure priority is valid
                if priority not in ("high", "medium", "low"):
                    priority = "high"

                # Declare all three priority queues to ensure they exist
                for q_name in ("high", "medium", "low"):
                    q = await channel_obj.declare_queue(
                        q_name,
                        durable=True,
                        arguments={
                            "x-dead-letter-exchange": "dla.exchange",
                            "x-dead-letter-routing-key": "dla",
                        }
                    )
                    await q.bind(exchange, routing_key=q_name)

                # Publish message to the appropriate queue via direct exchange
                message = aio_pika.Message(
                    body=json.dumps(payload).encode("utf-8"),
                    delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
                    type=message_type,
                )

                await exchange.publish(
                    message,
                    routing_key=priority
                )
                logger.info(
                    "Successfully published %s notification to '%s' queue (recipient: %s)",
                    message_type, priority, recipient
                )
                return
        except Exception as e:
            logger.warning(
                "Attempt %d/4 to publish notification to RabbitMQ failed: %s",
                attempt, e
            )
            if attempt >= max_retries + 1:
                logger.error(
                    "Failed to publish notification to RabbitMQ after %d retries.",
                    max_retries
                )
                raise e
            # Exponential backoff
            await asyncio.sleep(2 ** attempt * 0.1)
