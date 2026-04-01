# Creato Agent 数据结构参考手册

本文档定义了 creato agent 系统中所有跨模块数据契约。开发新 agent、tool、provider 时必须遵循这些类型定义。

所有类型集中定义在 `creato/schemas/` 包中，业务模块统一从此导入：

```python
from creato.schemas import LLMResponse, ToolResult, SubagentRequest, ...
```

---

## 类型分层规则

| 分类 | 机制 | 适用场景 |
|---|---|---|
| TypedDict | 零运行时开销，纯静态检查 | LLM 消息列表（dict-native 协议） |
| Pydantic BaseModel | 运行时校验 + 序列化 | 跨模块纯数据契约 |
| dataclass | 轻量运行时对象 | 含状态/方法/Callable/AsyncGenerator 的对象 |

判断标准：
- 数据会被序列化（JSON/BSON/SSE）或来自外部 → Pydantic
- 本质是给 LLM API 传的 dict → TypedDict
- 有状态、有方法、有 Callable → dataclass

---

## 1. LLM 消息类型（TypedDict）

**文件：** `creato/schemas/messages.py`

这些类型定义了在 executor、prompt builder、provider、session 之间流转的消息格式。LLM API 要求 plain dict，所以用 TypedDict。

### 消息结构

```python
SystemMessage       { role: "system",    content: str }
UserMessage         { role: "user",      content: str | list[dict] }
AssistantMessage    { role: "assistant", content: str | None, tool_calls?, reasoning_content?, thinking_blocks? }
ToolMessage         { role: "tool",      tool_call_id: str, name: str, content: str }
AgentDisplayMessage { role: "agent",     content: str, turn?, tool_hints?, created_at? }
```

### Tool Call 子结构

```python
ToolCallFunction { name: str, arguments: str(JSON), provider_specific_fields? }
ToolCallDict     { id: str, type: "function", function: ToolCallFunction, provider_specific_fields? }
```

### 类型别名

```python
ChatMessage   = SystemMessage | UserMessage | AssistantMessage | ToolMessage
StoredMessage = ChatMessage | AgentDisplayMessage    # 含 "agent" 角色，用于 session 存储
MessageList   = list[ChatMessage]                    # executor/provider 方法签名统一用这个
```

### 高频流式 Payload

```python
MessageDeltaData { content: str }    # message.delta 事件用 TypedDict，不走 Pydantic
```

### 使用示例

```python
from creato.schemas import MessageList

messages: MessageList = [
    {"role": "system", "content": "You are a helpful assistant."},
    {"role": "user", "content": "Hello"},
]
```

---

## 2. LLM Provider 响应（Pydantic）

**文件：** `creato/schemas/providers.py`
**边界：** provider → executor

开发新 provider 时，`chat()` 和 `stream()` 必须返回这些类型。

### ToolCallRequest

LLM 返回的工具调用请求。

```python
class ToolCallRequest(BaseModel):
    id: str                                          # 调用 ID
    name: str                                        # 工具名
    arguments: dict[str, Any]                        # 参数（自动 coerce string/list → dict）
    provider_specific_fields: dict[str, Any] | None  # provider 扩展字段
    function_provider_specific_fields: dict[str, Any] | None
```

`arguments` 字段有 `field_validator`：LLM 有时返回 JSON string 或 list，会自动转为 dict。

方法：
- `to_openai_tool_call() -> dict` — 序列化为 OpenAI 格式

### LLMResponse

LLM 的完整响应。

```python
class LLMResponse(BaseModel):
    content: str | None = None
    tool_calls: list[ToolCallRequest] = []
    finish_reason: str = "stop"                      # "stop" | "tool_calls" | "error"
    usage: dict[str, int] = {}                       # {"prompt_tokens": N, "completion_tokens": N}
    reasoning_content: str | None = None             # DeepSeek-R1, Kimi 等
    thinking_blocks: list[dict[str, Any]] | None = None  # Anthropic extended thinking
```

属性：
- `has_tool_calls -> bool`

### Provider 实现要求

```python
from creato.providers.base import LLMProvider, LLMStreamChunk
from creato.schemas import LLMResponse, ToolCallRequest, MessageList

class MyProvider(LLMProvider):
    async def chat(self, messages: MessageList, ...) -> LLMResponse:
        # 必须返回 LLMResponse
        return LLMResponse(content="hello", usage={"prompt_tokens": 10, "completion_tokens": 5})

    async def chat_stream(self, messages: MessageList, ...) -> AsyncGenerator[LLMStreamChunk, None]:
        # LLMStreamChunk 仍然是 dataclass（热路径）
        yield LLMStreamChunk(text_delta="hello")

    def get_default_model(self) -> str:
        return "my-model"
```

> **注意：** `LLMStreamChunk` 和 `GenerationSettings` 保持 dataclass，因为是 streaming 热路径和内部配置。

---

## 3. Tool 契约（Pydantic）

**文件：** `creato/schemas/tools.py`
**边界：** tool → executor, main agent ↔ subagent

### ToolEventPayload

Tool 执行过程中推给前端的 SSE 子事件。

```python
class ToolEventPayload(BaseModel):
    name: str                        # 事件名，如 "get_workflow", "workflow_update"
    data: dict[str, Any] = {}        # 事件数据
```

### ToolResult

Tool 的结构化返回值。只在需要给前端推事件时使用，普通 tool 直接返回 `str`。

```python
class ToolResult(BaseModel):
    content: str                              # 喂回 LLM 的文本
    events: list[ToolEventad] = []       # 推给前端的 SSE 事件
```

### SubagentRequest / SubagentResult

Agent 间通信的契约。

```python
class SubagentRequest(BaseModel):
    task: str              # 任务描述
    agent_type: str        # agent 类型名

class SubagentResult(BaseModel):
    agent_type: str
    content: str                    # agent 的最终回复
    tools_used: list[str] = []     # 使用过的工具列表
    iterations: int = 0            # 迭代次数
```

方法：
- `to_tool_response() -> str` — 序列化为 tool result 字符串喂回 LLM

### 开发新 Tool

```python
from creato.core.tools.base import Tool
from creato.schemas import ToolResult, ToolEventPayload

class MyTool(Tool):
    ty
    def name(self) -> str:
        return "my_tool"

    @property
    def description(self) -> str:
        return "Does something useful"

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query"},
            },
            "required": ["query"],
        }

    async def execute(self, query: str, **kwargs) -> str | ToolResult:
        result = do_something(query)

        # 简单返回：直接返回 str
    n f"Found: {result}"

        # 需要推前端事件：返回 ToolResult
        return ToolResult(
            content=f"Found: {result}",
            events=[ToolEventPayload(name="my_event", data={"id": result.id})],
        )
```

---

## 4. Executor 输出（Pydantic）

**文件：** `creato/schemas/executor.py`
**边界：** executor → loop

### ExecutorResult

```python
class ExecutorResult(BaseModel):
    content: str | None = None                       # 最终回复文本
    tools_used: list[str] = []                       # 使用过的工具名列表
    messages: MessageList = []                       # 完整消息历史（含 tool calls）
    tool_timings: dict[str, dict[str, Any]] = {}     # tool_call_id → 耗时等
    iterations: int = 0                              # 迭代次数
```

---

## 5. 消息总线（Pydantic）

**文件：** `creato/schemas/bus.py`
**边界：** channel → loop, loop → channel

### InboundMessage

```python
class InboundMessage(BaseModel):
    channel: str                          # "api", "telegram", "discord", ...
    sender_id: str
    chat_id: str
    content: str
    timestamp: datetime = now()
    media: list[str] = []                 # 媒体 URL 列表
    metadata: dict[str, Any] = {}         # channel 特定数据
    session_key_override: str | None      # 覆盖默认 session key
```

属性：`session_key -> str` — 默认 `"{channel}:{chat_id}"`

### OutboundMessage

```python
class OutboundMessage(BaseModel):
    channel: str
    chat_id: str
    content: str
    reply_to: str | None = None
    media: list[str] = []
    metadata: dict[str, Any] = {}
```

---

## 6. SSE 事件 Payload（Pydantic）

**文件：** `creato/schemas/events.py`
**边界：** loop → API server → 前端

事件通过 `AgentEvent` 信封发送，信封本身是 dataclass：

```python
@dataclass
class AgentEvent:
    event: str                    # 事件名（dot-notation）
    data: dict[str, Any] = {}    # payload（由下面的 Pydantic model 校验后 dump）
```

### Agent 生命周期

| 事件名 | Payload | 字段 |
|---|---|---`agent.started` | `AgentStartedData` | session_id, run_id |
| `agent.completed` | `AgentCompletedData` | content, usage? |
| `agent.failed` | `AgentFailedData` | error |
| `agent.heartbeat` | `{}` | 无 |

### 消息流式

| 事件名 | Payload | 字段 |
|---|---|---|
| `message.delta` | `MessageDeltaData` (TypedDict) | content |

### Tool 事件

| 事件名 | Payload | 字段 |
|---|---|---|
| `tool.started` | `ToolStartedData` | tool_name, tool_call_id, arguments |
| `tool.completed` | `ToolCompletedData` | tool_call_id, duration_ms |
| `tool.failed` | `ToolFailedData` | tool_call_id, error |
| `tool.event` | `ToolEventData` | event_name, + 扁平展开的 extra 字段 |

### Step 事件

| 事件名 | Payload | 字段 |
|---|---|---|
| `step.started` | `StepData` | step |
| `step.completed` | `StepData` | step |

### Subagent 事件

| 事件名 | Payload | 字段 |
|---|---|---|
| `subagent.started` | `SubagentStartedData` | agent_type, task |
| `subagent.completed` | `SubagentCompletedData` | agent_type, tools_used, result_preview |
| `subagent.message.delta` | `MessageDeltaData` (TypedDict) | content |
| `subagent.tool.started` | `ToolStartedData` | tool_name, tool_call_id, arguments |
| `subagent.tool.complebagentToolCompletedData` | tool_name, tool_call_id, duration_ms, error? |
| `subagent.tool.event` | `ToolEventData` | event_name, + 扁平展开的 extra 字段 |
| `subagent.step.started` | `StepData` | step |
| `subagent.step.completed` | `StepData` | step |

### Workflow 事件

Workflow 事件的 data 来自 Consumer 外部协议，保持 `dict[str, Any]` 透传，不做 Pydantic 约束。

| 事件名 | data |
|---|---|
| `workflow.started` | `{ flow_task_id, run_id, ws_id }` |
| `workflow.node_status` | Consumer 原始事件 |
| `workflow.model_ready` | Consumer 原始事件 |
| `workflow.model_status` | Consumer 原始事件 |
| `workfpaused` | `{ flow_task_id, flow_run_id, ws_id, node_id }` |
| `workflow.completed` | Consumer 原始事件 |
| `workflow.failed` | Consumer 原始事件 |
| `workflow.killed` | Consumer 原始事件 |

### AgentResponse（非流式）

```python
class AgentResponse(BaseModel):
    id: str
    session_id: str
    status: str                          # "completed" | "failed"
    output: list[dict[str, Any]] = []    # [{"type": "message", "content": "..."}, ...]
    usage: dict[str, int] | None
    model: str | None
    error: str | None
```

方法：
- `to_dict() -> dict` — 向后兼容的序列化

### 发送事件

所有事件必reato/core/events.py` 中的构造函数发送，禁止直接构造 `AgentEvent`：

```python
# 正确
from creato.core.events import tool_started, subagent_message_delta
await on_progress(tool_started("web_search", "tc_123", {"query": "test"}))

# 错误 — 绕过 Pydantic 校验
await on_progress(AgentEvent(event="tool.started", data={...}))
```

---

## 7. Session 存储（Pydantic）

**文件：** `creato/schemas/session.py`
**边界：** loop/session ↔ MongoDB/Redis

读写双侧校验：写入前 `model_validate()` 防脏数据落库，读取时 `model_validate()` normalize 旧数据。

### StoredMessageDoc — `agent_messages` 集合

```python
class StoredMessageDoc(BaseModel):
    model_config = {"extra": "allow"}    # 兼容旧数据未知字段

    role: "user" | "agent" | "assistant" | "tool"
    content: str | list[dict] | None
    turn: int | None
    tool_calls: list[dict] | None
    tool_call_id: str | None
    name: str | None
    tool_hints: list[str] | None
    thinking_blocks: list[dict] | None
    reasoning_content: str | None
    created_at: str | None
```

### SessionMetaDoc — `agent_sessions` 集合

```python
class SessionMetaDoc(BaseModel):
    model_config = {"extra": "allow"}

    user_id: str
    workflow_id: str | None
    channel: str
    summary: str | None
    message_count: int
    turn_count: int
    last_message_preview: str | None
    created_at: datetime | None
    updated_at: datetime | None
    metadata: dict[str, Any]
```

### ToolTraceDoc — `agent_tool_traces` 集合

```python
class ToolTraceDoc(BaseModel):
    session_id: str
    turn: int
    tool_call_id: str
    tool_name: str
    input: dict[str, Any]
    output: str
    output_size_bytes: int
    status: "success" | "error"
    error: str | None
    duration_ms: int
    started_at: datetime | None
    completed_at: datetime | None
```

---

## 8. Agent Profile（aclass）

**文件：** `creato/core/profile.py`

Agent 定义包含 `Callable` 字段，不适合 Pydantic。后续会拆分出 `AgentManifest`（Pydantic）。

### AgentProfile

```python
@dataclass(frozen=True)
class AgentProfile:
    name: str
    description: str
    system_prompt: str | Callable[..., str]
    tool_factories: tuple[Callable[[AgentContext], Tool], ...]
    inline_skills: tuple[str, ...] = ()
    loadable_skills: tuple[str, ...] = ()
    model: str | None = None
    max_iterations: int = 40
```

### 开发新 Subagent

```python
from creato.core.profile import AgentProfile, AgentContext
from creato.core.tools.base import Tool

def my_tool_factory(ctx: AgentContext) -> Tool:
 rn MyCustomTool(workspace=ctx.workspace)

my_agent = AgentProfile(
    name="my_agent",
    description="Handles specific tasks",
    system_prompt="You are a specialized agent...",
    tool_factories=(my_tool_factory,),
    inline_skills=("skill_a",),
    loadable_skills=("skill_b", "skill_c"),
    model="gpt-4o",
    max_iterations=20,
)

# 注册到 ProfileRegistry
registry.register(my_agent)
```

Main agent 调用 subagent 时，数据流如下：

```
LLM 决定调用 subagent tool
    │
    ▼
SubagentRequest(task...", agent_type="my_agent")    ← Pydantic 校验
    │
    ▼
AgentFactory.build(profile) → AgentInstance
    │
    ▼
AgentExecutor.run(messages) → ExecutorResult           ← Pydantic 校验
    │
    ▼
SubagentResult(agent_type, content, tools_used, iterations)  ← Pydantic 校验
    │
    ▼
result.to_tool_response() → str 喂回 main agent LLM
```

---

## 9. 保持 dataclass 的运行时对象

这些对象有状态、有方法、有 Callable/AsyncGenerator，不是纯数据契约：

| 对象 | 位置 | 原因 |
|---|---|---|
| `LLMStreamChunk` | `providers/base.py` | streaming 热路径，每 token 创建一个 |
| `GenerationSettings` | `providers/base.py` | provider 内部配置 |
| `WorkflowExecution` | `core/tools/base.py` | 含 `AsyncGenerator` 句柄 |
| `AgentEvent` | `core/events.py` | 轻量信封，data 已被 Pydantic 校验 |
| `ExecutorHooks` | `core/executor.py` | 回调接口容器（11 个 Callable） |
| `Session` | `session/manager.py` | 有状态对象，有 `get_history()`/`clear()` |
| `ResponseAccumulator` | `core/events.py` | 有状态累加器 |
| `AgentContext` | `core/profile.py` | 含 config/runtime handle |
| `AgentInstance` | `core/profile.py` | 含 ToolRegistry 运行时对象 |
| `AgentProfile` | `core/profile.py` | 含 Callable 字段 |
| `SkillInfo` | `core/skills/loader.py` | skills 内部元数据，不跨模块 |

---

## 10. 数据流向总图

```
                         MessageList (TypedDict)
                              │
   ┌───────────┐              │              ┌───────────┐
   │  Provider  │──LLMResponse (Pydantic)──► │  Executor │──ExecutorResult (Pydantic)──►┌──────┐
   │  (OpenAI)  │  ToolCallRequest           │           │                              │ Loop │
   │  (Gemini)  │◄──MessageList──────────────│           │◄──MessageList────────────────│      │
   └───────────┘                             └─────┬─────┘                              └──┬───┘
                                                   │                                       │
                                    ToolResult     │     AgentEvent                        │
                                    (Pydantic)     │     (dataclass 信封                    │
                                                   │      + Pydantic payload)              │
                                              ┌────┴────┐                           ┌─────┴──────┐
                                              │  Tools  │                           │  Session   │
                                              │ (各开发者)│                           │  Manager   │
                                              └────┬────┘                           └─────┬────┘
                                          │                                      │
                                 SubagentRequest   │                           StoredMessageDoc
                                 SubagentResult    │                           SessionMetaDoc
                                   (Pydantic)      │                           ToolTraceDoc
                                              ┌────┴────┐                        (Pydantic)
                                              │Subagent │                             │
                                              │ (各开发者)│                      ┌─────┴──────┐
                                              └─────────┘                      │  MongoDB   │
                                                                               │  Redis     │
   ┌───────────┐   InboundMessage (Pydantic)   ┌──────┐                        └────────────┘
   │ Channels  │──────────────────────────────►│ Loop │
   │ (API/TG)  │◄──OutboundMessage (Pydantic)──│      │
   └───────────┘                               └──────┘
```

---

## 快速参考：import 路径

```python
# 推荐：从 schemas 包统一导入
from creato.schemas import (
    # Messages (TypedDict)
    Messat, ChatMessage, SystemMessage, UserMessage,
    AssistantMessage, ToolMessage, AgentDisplayMessage,
    StoredMessage, MessageDeltaData,
    ToolCallDict, ToolCallFunction,

    # Providers (Pydantic)
    LLMResponse, ToolCallRequest,

    # Tools (Pydantic)
    ToolResult, ToolEventPayload,
    SubagentRequest, SubagentResult,

    # Executor (Pydantic)
    ExecutorResult,

    # Bus (Pydantic)
    InboundMessage, OutboundMessage,

    # Events (Pydantic)
    AgentStartedData, AgentCompletedData, AgentFailedData,
    ToolStartedData, ToolCompletedData, ToolFailedData,
    ToolEventData, StepData,
    SubagentStartedData, SubagentCompletedData, SubagentToolCompletedData,
    AgentResponse,

    # Session (Pydantic)
    StoredMessageDoc, SessionMetaDoc, ToolTraceDoc,
)

# 向后兼容：旧路径仍然可用（通过 re-export）
from creato.providers.base import LLMResponse, ToolCallRequest
from creato.core.tools.base import ToolResult
from creato.bus.events import InboundMessage, OutboundMessage
```
