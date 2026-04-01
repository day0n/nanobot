"""Base class for agent tools."""

from abc import ABC, abstractmethod
from collections.abc import AsyncGenerator, Callable
from dataclasses import dataclass, field
from typing import Any

from creato.schemas.tools import ToolResult  # noqa: F401 — re-exported for backward compat


@dataclass(slots=True)
class WorkflowExecution:
    """Return type for workflow tools — carries an async event stream.

    The executor consumes ``event_stream`` and delegates all interpretation
    to the callbacks provided by the tool:

    - ``interpret_event``: decides when to terminate and what string to
      return to the LLM.  ``finish_flow``/``flow_killed`` are NOT handled
      here — the ``event_stream`` generator breaks on those, and the
      executor falls back to ``default_result``.
    - ``make_sse_event``: converts raw Consumer events into AgentEvents
      for SSE forwarding.
    """

    flow_task_id: str
    run_id: str
    ws_id: str
    event_stream: AsyncGenerator[dict[str, Any], None]

    interpret_event: Callable[[dict[str, Any]], str | None] | None = None
    """Process each raw event. Return a string to terminate the stream
    (that string becomes the tool result for the LLM). Return None to
    keep consuming."""

    make_sse_event: Callable[[dict[str, Any]], Any | None] | None = None
    """Convert a raw Consumer event into an AgentEvent for SSE.
    Return None to skip the event."""

    default_result: str = "Workflow completed successfully"
    """Result returned to the LLM when the event stream ends normally
    (finish_flow break) without interpret_event producing a termination."""

    timeout_result: str = (
        "The workflow is still generating and may take a bit longer. "
        "Results will be saved automatically to your assets — nothing "
        "will be lost. You can leave or refresh the page, and check "
        "the assets page later. If generation fails, you will not be charged."
    )
    """Result returned to the LLM when the 8-minute event stream timeout fires."""


class TurnAware:
    """Mixin for tools that need per-turn lifecycle."""

    def on_turn_start(self) -> None:
        """Called before each agent turn begins."""

    def on_turn_end(self) -> bool:
        """Called after each agent turn. Return True if tool already handled the response."""
        return False


class ContextAware:
    """Mixin for tools that need message routing context."""

    def set_routing_context(self, channel: str, chat_id: str, message_id: str | None = None) -> None: ...


class ProgressAware:
    """Mixin for tools that need a progress callback."""

    def set_progress(self, callback: Any) -> None: ...


class Tool(ABC):
    """
    Abstract base class for agent tools.

    Tools are capabilities that the agent can use to interact with
    the environment, such as reading files, executing commands, etc.
    """

    _TYPE_MAP = {
        "string": str,
        "integer": int,
        "number": (int, float),
        "boolean": bool,
        "array": list,
        "object": dict,
    }

    @staticmethod
    def _resolve_type(t: Any) -> str | None:
        """Resolve JSON Schema type to a simple string.

        JSON Schema allows ``"type": ["string", "null"]`` (union types).
        We extract the first non-null type so validation/casting works.
        """
        if isinstance(t, list):
            for item in t:
                if item != "null":
                    return item
            return None
        return t

    @property
    @abstractmethod
    def name(self) -> str:
        """Tool name used in function calls."""
        pass

    @property
    @abstractmethod
    def description(self) -> str:
        """Description of what the tool does."""
        pass

    @property
    @abstractmethod
    def parameters(self) -> dict[str, Any]:
        """JSON Schema for tool parameters."""
        pass

    @abstractmethod
    async def execute(self, **kwargs: Any) -> str | ToolResult:
        """
        Execute the tool with given parameters.

        Args:
            **kwargs: Tool-specific parameters.

        Returns:
            String result of the tool execution.
        """
        pass

    def cast_params(self, params: dict[str, Any]) -> dict[str, Any]:
        """Apply safe schema-driven casts before validation."""
        schema = self.parameters or {}
        if schema.get("type", "object") != "object":
            return params

        return self._cast_object(params, schema)

    def _cast_object(self, obj: Any, schema: dict[str, Any]) -> dict[str, Any]:
        """Cast an object (dict) according to schema."""
        if not isinstance(obj, dict):
            return obj

        props = schema.get("properties", {})
        required = set(schema.get("required", []))
        result = {}

        for key, value in obj.items():
            # Strip None values for optional params — LLMs often pass null to mean "omit"
            if value is None and key not in required:
                continue
            if key in props:
                result[key] = self._cast_value(value, props[key])
            else:
                result[key] = value

        return result

    def _cast_value(self, val: Any, schema: dict[str, Any]) -> Any:
        """Cast a single value according to schema."""
        target_type = self._resolve_type(schema.get("type"))

        if target_type == "boolean" and isinstance(val, bool):
            return val
        if target_type == "integer" and isinstance(val, int) and not isinstance(val, bool):
            return val
        if target_type in self._TYPE_MAP and target_type not in ("boolean", "integer", "array", "object"):
            expected = self._TYPE_MAP[target_type]
            if isinstance(val, expected):
                return val

        if target_type == "integer" and isinstance(val, str):
            try:
                return int(val)
            except ValueError:
                return val

        if target_type == "number" and isinstance(val, str):
            try:
                return float(val)
            except ValueError:
                return val

        if target_type == "string":
            return val if val is None else str(val)

        if target_type == "boolean" and isinstance(val, str):
            val_lower = val.lower()
            if val_lower in ("true", "1", "yes"):
                return True
            if val_lower in ("false", "0", "no"):
                return False
            return val

        if target_type == "array" and isinstance(val, list):
            item_schema = schema.get("items")
            return [self._cast_value(item, item_schema) for item in val] if item_schema else val

        if target_type == "object" and isinstance(val, dict):
            return self._cast_object(val, schema)

        return val

    def validate_params(self, params: dict[str, Any]) -> list[str]:
        """Validate tool parameters against JSON schema. Returns error list (empty if valid)."""
        if not isinstance(params, dict):
            return [f"parameters must be an object, got {type(params).__name__}"]
        schema = self.parameters or {}
        if schema.get("type", "object") != "object":
            raise ValueError(f"Schema must be object type, got {schema.get('type')!r}")
        return self._validate(params, {**schema, "type": "object"}, "")

    def _validate(self, val: Any, schema: dict[str, Any], path: str) -> list[str]:
        raw_type = schema.get("type")
        nullable = (isinstance(raw_type, list) and "null" in raw_type) or schema.get(
            "nullable", False
        )
        t, label = self._resolve_type(raw_type), path or "parameter"
        if nullable and val is None:
            return []
        if t == "integer" and (not isinstance(val, int) or isinstance(val, bool)):
            return [f"{label} should be integer"]
        if t == "number" and (
            not isinstance(val, self._TYPE_MAP[t]) or isinstance(val, bool)
        ):
            return [f"{label} should be number"]
        if t in self._TYPE_MAP and t not in ("integer", "number") and not isinstance(val, self._TYPE_MAP[t]):
            return [f"{label} should be {t}"]

        errors = []
        if "enum" in schema and val not in schema["enum"]:
            errors.append(f"{label} must be one of {schema['enum']}")
        if t in ("integer", "number"):
            if "minimum" in schema and val < schema["minimum"]:
                errors.append(f"{label} must be >= {schema['minimum']}")
            if "maximum" in schema and val > schema["maximum"]:
                errors.append(f"{label} must be <= {schema['maximum']}")
        if t == "string":
            if "minLength" in schema and len(val) < schema["minLength"]: # type: ignore
                errors.append(f"{label} must be at least {schema['minLength']} chars")
            if "maxLength" in schema and len(val) > schema["maxLength"]: # pyright: ignore[reportArgumentType]
                errors.append(f"{label} must be at most {schema['maxLength']} chars")
        if t == "object":
            props = schema.get("properties", {})
            for k in schema.get("required", []):
                if k not in val:
                    errors.append(f"missing required {path + '.' + k if path else k}")
            for k, v in val.items(): # type: ignore
                if k in props:
                    errors.extend(self._validate(v, props[k], path + "." + k if path else k))
        if t == "array" and "items" in schema:
            for i, item in enumerate(val): # type: ignore
                errors.extend(
                    self._validate(item, schema["items"], f"{path}[{i}]" if path else f"[{i}]")
                )
        return errors

    def to_schema(self) -> dict[str, Any]:
        """Convert tool to OpenAI function schema format."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }
