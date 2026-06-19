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

async def publish_calendar_notification(payload: dict):
    """
    Publish a calendar reminder notification payload to RabbitMQ.
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
            body=json.dumps(payload).encode("utf-8"),
            delivery_mode=aio_pika.DeliveryMode.PERSISTENT
        )
        
        await exchange.publish(
            message,
            routing_key="calendar.notification.trigger"
        )

async def publish_todo_reminder(payload: dict):
    """
    Publish a To-Do task reminder notification payload to RabbitMQ.
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
            body=json.dumps(payload).encode("utf-8"),
            delivery_mode=aio_pika.DeliveryMode.PERSISTENT
        )
        
        await exchange.publish(
            message,
            routing_key="todo.reminder.trigger"
        )


async def publish_bulk_credentials(payload: dict):
    """
    Publish credential delivery event for bulk-created users.
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
            body=json.dumps(payload).encode("utf-8"),
            delivery_mode=aio_pika.DeliveryMode.PERSISTENT
        )

        await exchange.publish(
            message,
            routing_key="email.credentials.send"
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
