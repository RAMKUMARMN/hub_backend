"""Stub SMS sender for local development/testing."""
import logging
from typing import Optional

logger = logging.getLogger(__name__)


async def send_sms(to: str, body: Optional[str] = None) -> None:
    logger.info("(stub) send_sms to=%s body=%s", to, body)
