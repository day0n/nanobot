"""Event types for the message bus.

The actual Pydantic models live in ``creato.schemas.bus``.
This module re-exports them for backward compatibility.
"""

from creato.schemas.bus import InboundMessage, OutboundMessage

__all__ = ["InboundMessage", "OutboundMessage"]
