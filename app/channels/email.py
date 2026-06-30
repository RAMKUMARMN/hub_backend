"""Stub email sender for local development/testing."""
import logging
from typing import Optional

logger = logging.getLogger(__name__)


async def send_email(to: str, subject: str, body: Optional[str] = None, html_body: Optional[str] = None) -> None:
    logger.info("(stub) send_email to=%s subject=%s", to, subject)
