"""Centralized data contracts for the creato agent system.

All cross-module data types are defined here. Business modules import
from this package — this package never imports from business modules.

- TypedDict: LLM message types (dict-native, zero runtime cost)
- Pydantic BaseModel: cross-module data contracts (runtime validation)
- dataclass: stays in original modules (runtime objects with state/callables)
"""

# Messages (TypedDict — zero runtime cost)
from creato.schemas.messages import (
    AgentDisplayMessage,
    AssistantMessage,
    ChatMessage,
    MessageDeltaData,
    MessageList,
    StoredMessage,
    SystemMessage,
    ToolCallDict,
    ToolCallFunction,
    ToolMessage,
    UserMessage,
)

# Providers (Pydantic)
from creato.schemas.providers import LLMResponse, ToolCallRequest

# Tools (Pydantic)
from creato.schemas.tools import (
    SubagentRequest,
    SubagentResult,
    ToolEventPayload,
    ToolResult,
)

# Executor (Pydantic)
from creato.schemas.executor import ExecutorResult

# Bus (Pydantic)
from creato.schemas.bus import InboundMessage, OutboundMessage

# Events (Pydantic)
from creato.schemas.events import (
    AgentCompletedData,
    AgentFailedData,
    AgentResponse,
    AgentStartedData,
    StepData,
    SubagentCompletedData,
    SubagentStartedData,
    ToolCompletedData,
    ToolFailedData,
    ToolStartedData,
)

# Session (Pydantic)
from creato.schemas.session import (
    SessionMetaDoc,
    StoredMessageDoc,
    ToolTraceDoc,
)

__all__ = [
    # Messages (TypedDict)
    "AgentDisplayMessage",
    "AssistantMessage",
    "ChatMessage",
    "MessageDeltaData",
    "MessageList",
    "StoredMessage",
    "SystemMessage",
    "ToolCallDict",
    "ToolCallFunction",
    "ToolMessage",
    "UserMessage",
    # Providers
    "LLMResponse",
    "ToolCallRequest",
    # Tools
    "SubagentRequest",
    "SubagentResult",
    "ToolEventPayload",
    "ToolResult",
    # Executor
    "ExecutorResult",
    # Bus
    "InboundMessage",
    "OutboundMessage",
    # Events
    "AgentCompletedData",
    "AgentFailedData",
    "AgentResponse",
    "AgentStartedData",
    "StepData",
    "SubagentCompletedData",
    "SubagentStartedData",
    "ToolCompletedData",
    "ToolFailedData",
    "ToolStartedData",
    # Session
    "SessionMetaDoc",
    "StoredMessageDoc",
    "ToolTraceDoc",
]
