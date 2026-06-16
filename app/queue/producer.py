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
