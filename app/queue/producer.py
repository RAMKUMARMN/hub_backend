import json
import logging
import aio_pika
from app.config import settings

logger = logging.getLogger(__name__)

async def publish_job(queue_name: str, payload: dict) -> None:
    """
    Connects to RabbitMQ and publishes the notification job payload
    to the designated queue channel.
    """
    try:
        # Connect using the URL from your backend .env
        connection = await aio_pika.connect_robust(settings.rabbitmq_url)
        async with connection:
            channel = await connection.channel()
            
            # Ensure the targeted processing queue exists
            queue = await channel.declare_queue(queue_name, durable=True)
            
            # Convert dictionary payload to bytes
            message_body = json.dumps(payload).encode()
            
            # Send it straight into the RabbitMQ queue
            await channel.default_exchange.publish(
                aio_pika.Message(
                    body=message_body,
                    delivery_mode=aio_pika.DeliveryMode.PERSISTENT
                ),
                routing_key=queue_name,
            )
            logger.info("Successfully pushed job %s to queue %s", payload.get("job_id"), queue_name)
            
    except Exception as e:
        logger.error("Failed to publish message to RabbitMQ: %s", str(e))
        raise e