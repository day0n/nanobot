"""Configuration schema using Pydantic."""

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel
from pydantic_settings import BaseSettings


class Base(BaseModel):
    """Base model that accepts both camelCase and snake_case keys."""

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

class ChannelsConfig(Base):
    """Configuration for chat channels.

    Built-in and plugin channel configs are stored as extra fields (dicts).
    Each channel parses its own config in __init__.
    """

    model_config = ConfigDict(extra="allow")

    send_progress: bool = True  # stream agent's text progress to the channel
    send_tool_hints: bool = False  # stream tool-call hints (e.g. read_file("…"))


class AgentDefaults(Base):
    """Default agent configuration."""

    workspace: str = "~/.creato/workspace"
    model: str = "openai/gpt-4.1"
    max_tokens: int = 8192
    context_window_tokens: int = 65_536
    temperature: float = 0.1
    max_tool_iterations: int = 40
    reasoning_effort: str | None = None  # low / medium / high — enables LLM thinking mode
    summary_model: str = "openai/gpt-4o-mini"  # Lightweight model for session title generation


class AgentsConfig(Base):
    """Agent configuration."""

    defaults: AgentDefaults = Field(default_factory=AgentDefaults)


class VertexGeminiConfig(Base):
    """Vertex AI Gemini provider configuration (service account auth)."""

    oc_json: str = ""  # GOOGLE_OC_JSON — base64-encoded service account JSON
    project: str = ""  # GOOGLE_CLOUD_PROJECT
    location: str = "us-central1"  # GOOGLE_CLOUD_LOCATION


class ProviderConfig(Base):
    """LLM provider configuration."""

    api_key: str = ""
    api_base: str | None = None
    extra_headers: dict[str, str] | None = None  # Custom headers (e.g. APP-Code for AiHubMix)


class ProvidersConfig(Base):
    """Configuration for LLM providers.

    Each field name is a provider prefix used in model strings:
      "openai/gpt-4.1"  → providers.openai
      "vertex_gemini/gemini-3-pro" → providers.vertex_gemini
    """

    openai: ProviderConfig = Field(default_factory=ProviderConfig)
    vertex_gemini: VertexGeminiConfig = Field(default_factory=VertexGeminiConfig)


class GatewayConfig(Base):
    """Gateway/server configuration."""

    host: str = "0.0.0.0"
    port: int = 18790


class ApiServerConfig(Base):
    """creato API server configuration."""

    enabled: bool = False
    host: str = "0.0.0.0"
    port: int = 18791
    clerk_pem_public_key: str = ""  # Clerk RS256 PEM public key
    internal_api_base: str = ""  # e.g. "https://api-develop.opencreator.io"
    internal_api_key: str = ""  # Internal API key (plaintext, Base64 encoding handled internally)
    editor_base: str = ""  # e.g. "https://editor-dev.opencreator.io"


class WebSearchConfig(Base):
    """Web search tool configuration."""

    provider: str = "brave"  # brave, tavily, duckduckgo, searxng, jina
    api_key: str = ""
    base_url: str = ""  # SearXNG base URL
    max_results: int = 5


class WebToolsConfig(Base):
    """Web tools configuration."""

    proxy: str | None = (
        None  # HTTP/SOCKS5 proxy URL, e.g. "http://127.0.0.1:7890" or "socks5://127.0.0.1:1080"
    )
    search: WebSearchConfig = Field(default_factory=WebSearchConfig)


class ExecToolConfig(Base):
    """Shell exec tool configuration."""

    timeout: int = 60
    path_append: str = ""


class MCPServerConfig(Base):
    """MCP server connection configuration (stdio or HTTP)."""

    type: Literal["stdio", "sse", "streamableHttp"] | None = None  # auto-detected if omitted
    command: str = ""  # Stdio: command to run (e.g. "npx")
    args: list[str] = Field(default_factory=list)  # Stdio: command arguments
    env: dict[str, str] = Field(default_factory=dict)  # Stdio: extra env vars
    url: str = ""  # HTTP/SSE: endpoint URL
    headers: dict[str, str] = Field(default_factory=dict)  # HTTP/SSE: custom headers
    tool_timeout: int = 30  # seconds before a tool call is cancelled
    enabled_tools: list[str] = Field(default_factory=lambda: ["*"])  # Only register these tools; accepts raw MCP names or wrapped mcp_<server>_<tool> names; ["*"] = all tools; [] = no tools

class ToolsConfig(Base):
    """Tools configuration."""

    web: WebToolsConfig = Field(default_factory=WebToolsConfig)
    exec: ExecToolConfig = Field(default_factory=ExecToolConfig)
    restrict_to_workspace: bool = False  # If true, restrict all tool access to workspace directory
    mcp_servers: dict[str, MCPServerConfig] = Field(default_factory=dict)


class RabbitMQConfig(Base):
    """RabbitMQ connection configuration (for workflow result consumption)."""

    host: str = ""
    port: int = 5671
    username: str = ""
    password: str = ""
    ssl: bool = True  # AWS MQ requires SSL
    num_workers: int = 3  # MD5 hash routing workers for message ordering
    prefetch_count: int = 1000


class SentryConfig(Base):
    """Sentry monitoring configuration."""

    dsn: str = ""  # Sentry DSN, empty = disabled
    environment: str = "development"  # e.g. "production", "staging"
    profiles_sample_rate: float = 0.0  # 0.0 ~ 1.0
    send_default_pii: bool = False


class WorkflowConfig(Base):
    """Workflow execution configuration."""

    deploy_id: str = ""  # Instance identifier, e.g. "agent-prod-1". Must be fixed, not random.
    run_flow_queue: str = "run_flow"  # Redis Stream queue name (same as Publisher/Consumer)


class MemoryConfig(Base):
    """Long-term memory configuration (mem0-based)."""

    enabled: bool = False  # Master switch — set CREATO_MEMORY__ENABLED=true to activate
    collection_name: str = "memories"  # Collection in agent_db for storing memories
    embedding_model_dims: int = 1536  # Embedding dimensions (1536 for text-embedding-3-small)
    llm_model: str = "gpt-4o-mini"  # Cheap model for memory extraction
    embedder_model: str = "text-embedding-3-small"  # Embedding model
    search_limit: int = 5  # Max memories to retrieve per query


class MongoDBConfig(Base):
    """MongoDB connection configuration."""

    uri: str = "mongodb://localhost:27017"  # MongoDB Atlas URI (mongodb+srv://...)
    db: str = "opencreator"  # Main database (used by publisher/consumer)
    agent_db: str = "opencreator_agent"  # Separate database for agent sessions/messages/traces


class RedisConfig(Base):
    """Redis connection configuration."""

    host: str = "localhost"
    port: int = 6379
    db: int = 0
    password: str = ""
    ssl: bool = False  # AWS ElastiCache requires SSL


class PostHogConfig(Base):
    """PostHog LLM Analytics configuration."""

    api_key: str = ""  # PostHog project API key, empty = disabled
    host: str = "https://us.i.posthog.com"
    enabled: bool = True  # Master switch (still requires api_key)
    privacy_mode: bool = False  # If true, redact input/output content from events


class Config(BaseSettings):
    """Root configuration for creato."""

    agents: AgentsConfig = Field(default_factory=AgentsConfig)
    channels: ChannelsConfig = Field(default_factory=ChannelsConfig)
    providers: ProvidersConfig = Field(default_factory=ProvidersConfig)
    gateway: GatewayConfig = Field(default_factory=GatewayConfig)
    tools: ToolsConfig = Field(default_factory=ToolsConfig)
    api: ApiServerConfig = Field(default_factory=ApiServerConfig)
    mongodb: MongoDBConfig = Field(default_factory=MongoDBConfig)
    memory: MemoryConfig = Field(default_factory=MemoryConfig)
    redis: RedisConfig = Field(default_factory=RedisConfig)
    rabbitmq: RabbitMQConfig = Field(default_factory=RabbitMQConfig)
    workflow: WorkflowConfig = Field(default_factory=WorkflowConfig)
    sentry: SentryConfig = Field(default_factory=SentryConfig)
    posthog: PostHogConfig = Field(default_factory=PostHogConfig)

    @property
    def workspace_path(self) -> Path:
        """Get expanded workspace path."""
        return Path(self.agents.defaults.workspace).expanduser()

    model_config = ConfigDict(env_prefix="CREATO_", env_nested_delimiter="__")
