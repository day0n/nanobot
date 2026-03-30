"""Message bus contracts — Pydantic (runtime validation).

These types cross the bus → loop and loop → bus boundaries.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class InboundMessage(BaseModel):
    """A message received from a channel (Telegram, Discord, API, etc.)."""

    channel: str
    sender_id: str
    chat_id: str
    content: str
    timestamp: datetime = Field(default_factory=datetime.now)
    media: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    session_key_override: str | None = None

    @property
    def session_key(self) -> str:
        return self.session_key_override or f"{self.channel}:{self.chat_id}"


class OutboundMessage(BaseModel):
    """A message to send back to a channel."""

    channel: str
    chat_id: str
    content: str
    reply_to: str | None = None
    media: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
