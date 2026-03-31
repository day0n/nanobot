"""FastAPI SSE server for creato agent chat."""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING

import jwt
from fastapi import FastAPI, Header, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from loguru import logger
from pydantic import BaseModel

from creato.core.events import (
    AgentEvent,
    AgentResponse,
    ResponseAccumulator,
    agent_completed,
    agent_failed,
    agent_heartbeat,
    agent_started,
)
from creato.core.loop import AgentLoop
from creato.core.profile import AgentContext
from creato.core.factory import AgentFactory
from creato.core.skills import SkillsLoader
from creato.agents import discover_profiles

if TYPE_CHECKING:
    from creato.config.schema import Config
    from creato.providers.base import LLMProvider


@dataclass(slots=True)
class AuthenticatedAgentUser:
    user_id: str
    token: str


class ChatRequest(BaseModel):
    message: str
    session_id: str = "default"
    flow_id: str | None = None
    metadata: dict | None = None  # frontend-provided metadata (files, etc.)
    stream: bool = True  # default true for backwards compat


def _authenticate_agent_request(
    authorization: str | None,
    config: "Config",
) -> AuthenticatedAgentUser:
    """Authenticate API chat requests with the publisher-issued user JWT."""
    if not config.api.clerk_pem_public_key:
        raise HTTPException(status_code=401, detail="JWT auth is not configured on the server")

    if not authorization:
        raise HTTPException(status_code=401, detail="Authorization header is required")

    bearer_prefix = "Bearer "
    if not authorization.startswith(bearer_prefix):
        raise HTTPException(status_code=401, detail="Authorization header must use Bearer token")

    token = authorization[len(bearer_prefix):].strip()
    if not token:
        raise HTTPException(status_code=401, detail="Bearer token is required")

    try:
        payload = jwt.decode(
            token,
            config.api.clerk_pem_public_key,
            algorithms=["RS256"],
        )
    except jwt.ExpiredSignatureError as exc:
        raise HTTPException(status_code=401, detail="Token has expired") from exc
    except jwt.InvalidTokenError as exc:
        raise HTTPException(status_code=401, detail="Invalid token") from exc

    user_id = payload.get("sub")
    if not isinstance(user_id, str) or not user_id.strip():
        raise HTTPException(status_code=401, detail="Token missing subject")

    return AuthenticatedAgentUser(user_id=user_id, token=token)


def create_app(config: Config, provider: LLMProvider) -> FastAPI:
    """Create the FastAPI application."""
    from contextlib import asynccontextmanager

    from creato.sentry import init_sentry
    from creato.posthog import init_posthog, shutdown_posthog, identify_user
    from creato.database.mongo import (
        init_mongo,
        test_mongo,
        ensure_indexes,
        agent_sessions_col,
        agent_messages_col,
        agent_tool_traces_col,
        mongo_client,
    )
    import creato.database.mongo as _mongo_mod  # late-bound access to db
    from creato.database.redis import init_redis, test_redis, redis_client
    from creato.database.rabbitmq import (
        init_rabbitmq,
        start_mq_consumer,
        close_rabbitmq,
        get_reply_queue_name,
        set_dispatch_fn,
    )
    from creato.session.manager import SessionManager
    from creato.workflow.engine import WorkflowEngine
    from creato.workflow.task_publisher import run_flow
    from creato.workflow.event_bridge import dispatch as event_dispatch

    # Initialize Sentry before anything else
    init_sentry(config.sentry)

    # Initialize PostHog LLM Analytics
    init_posthog(config.posthog)

    # Initialize database connections (sync — creates clients, no I/O yet)
    init_mongo(config.mongodb.uri, config.mongodb.db, config.mongodb.agent_db)
    init_redis(config.redis.host, config.redis.port, config.redis.password, config.redis.db, config.redis.ssl)

    # Create WorkflowDAO (data access layer for workflow CRUD + results)
    from creato.database.mongo import (
        agent_sessions_col, agent_messages_col, agent_tool_traces_col,
        flow_col, flow_details_col, flow_version_col, results_col,
    )
    from creato.dao.workflow_dao import WorkflowDAO
    workflow_dao = WorkflowDAO(
        flow_col=flow_col,
        flow_details_col=flow_details_col,
        flow_version_col=flow_version_col,
        results_col=results_col,
        cloudfront_domain=config.api.cloudfront_domain,
    )

    # Create SessionManager with new three-collection schema
    from creato.database.redis import redis_client
    session_manager = SessionManager(
        sessions_col=agent_sessions_col,
        messages_col=agent_messages_col,
        tool_traces_col=agent_tool_traces_col,
        redis_client=redis_client,
    )

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        # Startup: test connections and create indexes
        await test_mongo()
        await test_redis()
        await ensure_indexes()

        # Startup: RabbitMQ consumer for workflow results
        mq_connection = None
        if cfg.workflow.deploy_id:
            init_rabbitmq(
                deploy_id=cfg.workflow.deploy_id,
                num_workers=cfg.rabbitmq.num_workers,
            )
            mq_connection = await start_mq_consumer(
                host=cfg.rabbitmq.host,
                port=cfg.rabbitmq.port,
                username=cfg.rabbitmq.username,
                password=cfg.rabbitmq.password,
                ssl=cfg.rabbitmq.ssl,
                prefetch_count=cfg.rabbitmq.prefetch_count,
                virtualhost=cfg.rabbitmq.virtualhost,
            )

            # Create WorkflowEngine and bind to app.state
            from creato.database.mongo import flow_task_col
            from creato.database.redis import redis_client as rc_for_engine
            app.state.workflow_engine = WorkflowEngine(
                redis_client=rc_for_engine,
                flow_task_col=flow_task_col,
                publish_fn=run_flow.publish,
                reply_queue=get_reply_queue_name(),
            )
            app.state.config = cfg
            set_dispatch_fn(event_dispatch)

            # Register RunWorkflowTool into the agent's tool registry
            from creato.core.tools.opencreator import ContinueWorkflowTool, RunWorkflowTool
            app.state.agent.tools.register(RunWorkflowTool(
                workflow_engine=app.state.workflow_engine,
                workflow_dao=workflow_dao,
            ))
            app.state.agent.tools.register(ContinueWorkflowTool(
                workflow_engine=app.state.workflow_engine,
                workflow_dao=workflow_dao,
            ))
            # Tool definitions are passed to the LLM on each call, so the model
            # discovers new tools automatically. But the system prompt also lists
            # tool names explicitly, so rebuild it with the updated registry.
            from creato.agents.main.prompt import build_main_system_prompt
            _allowed = list(main_profile.inline_skills) + list(main_profile.loadable_skills)
            _filtered = skills_loader.filtered(_allowed)
            app.state.agent.context._system_prompt_override = build_main_system_prompt(
                skills_loader=_filtered,
                tool_names=app.state.agent.tools.tool_names,
            )

            logger.info(f"Workflow engine ready, reply_queue={get_reply_queue_name()}")

        yield

        # Shutdown
        shutdown_posthog()
        if mq_connection:
            await close_rabbitmq()
        await app.state.agent.close_mcp()
        from creato.database.mongo import mongo_client
        from creato.database.redis import redis_client as rc
        if rc:
            await rc.close()
        if mongo_client:
            mongo_client.close()

    app = FastAPI(title="creato Agent API", version="0.1.0", lifespan=lifespan)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    cfg = config
    app.state.config = cfg
    # Create a lightweight summary provider for session titles & context compression
    from creato.providers.router import create_provider as _create_provider
    try:
        _summary_provider = _create_provider(cfg, model=cfg.agents.defaults.summary_model)
    except Exception:
        _summary_provider = None

    # Initialize long-term memory if enabled
    _memory = None
    if cfg.memory.enabled:
        from creato.core.memory.mem0_memory import Mem0Memory
        _openai_key = cfg.providers.openai.api_key or None
        _memory = Mem0Memory(
            mongo_uri=cfg.mongodb.uri,
            db_name=cfg.mongodb.agent_db,
            collection_name=cfg.memory.collection_name,
            embedding_model_dims=cfg.memory.embedding_model_dims,
            llm_model=cfg.memory.llm_model,
            embedder_model=cfg.memory.embedder_model,
            openai_api_key=_openai_key,
        )

    # Build Profile/Factory/Executor architecture
    profile_registry = discover_profiles()
    main_profile = profile_registry.get("main")
    if not main_profile:
        raise RuntimeError("Main agent profile not found — check creato/agents/main/")

    agent_context = AgentContext(
        workspace=cfg.workspace_path,
        web_search_config=cfg.tools.web.search,
        web_proxy=cfg.tools.web.proxy or None,
        api_config=cfg.api,
        exec_config=cfg.tools.exec,
        restrict_to_workspace=cfg.tools.restrict_to_workspace,
        workflow_dao=workflow_dao,
    )
    skills_loader = SkillsLoader()
    agent_factory = AgentFactory(
        context=agent_context,
        skills_loader=skills_loader,
        provider=provider,
        default_model=cfg.agents.defaults.model,
        profile_registry=profile_registry,
    )

    agent = AgentLoop(
        provider=provider,
        workspace=cfg.workspace_path,
        profile=main_profile,
        factory=agent_factory,
        model=cfg.agents.defaults.model,
        max_iterations=cfg.agents.defaults.max_tool_iterations,
        context_window_tokens=cfg.agents.defaults.context_window_tokens,
        web_search_config=cfg.tools.web.search,
        web_proxy=cfg.tools.web.proxy or None,
        api_config=cfg.api,
        exec_config=cfg.tools.exec,
        restrict_to_workspace=cfg.tools.restrict_to_workspace,
        session_manager=session_manager,
        mcp_servers=cfg.tools.mcp_servers,
        channels_config=cfg.channels,
        summary_provider=_summary_provider,
        memory=_memory,
        max_output_tokens=cfg.agents.defaults.max_tokens,
    )
    app.state.agent = agent

    # PostHog: background identify (fire-and-forget, skips if already cached)
    from creato.posthog import _identified_users

    async def _posthog_identify(user_id: str) -> None:
        if user_id in _identified_users:
            return  # Already identified this process, zero cost
        try:
            user_doc = await _mongo_mod.db["user"].find_one(
                {"user_id": user_id}, {"user_email": 1},
            )
            if user_doc and user_doc.get("user_email"):
                identify_user(user_id, user_doc["user_email"])
        except Exception:
            pass

    # ---- POST /v1/agent/chat — SSE streaming chat ----

    @app.post("/v1/agent/chat")
    async def chat(
        body: ChatRequest,
        authorization: str | None = Header(default=None),
        x_time_zone: str | None = Header(default=None, alias="X-Time-Zone"),
    ):
        auth_user = _authenticate_agent_request(authorization, cfg)

        # PostHog: identify user with email (fire-and-forget, never blocks chat)
        asyncio.create_task(_posthog_identify(auth_user.user_id))

        flow_id = body.flow_id.strip() if isinstance(body.flow_id, str) and body.flow_id.strip() else None

        # session_id is passed directly from frontend as the primary key
        session_id = body.session_id

        # Merge frontend metadata with flow_id
        request_metadata = dict(body.metadata or {})
        if flow_id:
            request_metadata["flow_id"] = flow_id

        # Private context for tools (not exposed to LLM prompt)
        private_context = {
            "auth_token": auth_user.token,
            "flow_id": flow_id,
            "time_zone": x_time_zone.strip() if isinstance(x_time_zone, str) and x_time_zone.strip() else None,
            "user_id": auth_user.user_id,
        }
        continue_workflow = request_metadata.get("continue_workflow")
        if isinstance(continue_workflow, dict):
            private_context["continue_workflow"] = continue_workflow

        async def event_stream():
            queue: asyncio.Queue[AgentEvent] = asyncio.Queue()

            async def on_progress(event: AgentEvent):
                await queue.put(event)

            async def run_agent():
                await queue.put(agent_started(session_id))
                try:
                    result = await app.state.agent.process_direct(
                        body.message,
                        session_key=session_id,
                        channel="api",
                        chat_id=auth_user.user_id,
                        on_progress=on_progress,
                        metadata=request_metadata or None,
                        private_context=private_context,
                        user_id=auth_user.user_id,
                        workflow_id=flow_id,
                    )
                    await queue.put(agent_completed(result or ""))
                except Exception as e:
                    logger.exception("Agent error")
                    await queue.put(agent_failed(str(e)))

            task = asyncio.create_task(run_agent())
            try:
                while True:
                    try:
                        event = await asyncio.wait_for(queue.get(), timeout=15)
                    except asyncio.TimeoutError:
                        yield f"data: {json.dumps(agent_heartbeat().to_dict(), ensure_ascii=False)}\n\n"
                        continue
                    yield f"data: {json.dumps(event.to_dict(), ensure_ascii=False)}\n\n"
                    if event.is_terminal:
                        break
            finally:
                task.cancel()

        if not body.stream:
            # Non-streaming: collect events, build AgentResponse
            accumulator = ResponseAccumulator()

            async def collect_events(event: AgentEvent):
                accumulator.feed(event)

            accumulator.feed(agent_started(session_id))
            try:
                result = await app.state.agent.process_direct(
                    body.message,
                    session_key=session_id,
                    channel="api",
                    chat_id=auth_user.user_id,
                    on_progress=collect_events,
                    metadata=request_metadata or None,
                    private_context=private_context,
                    user_id=auth_user.user_id,
                    workflow_id=flow_id,
                )
                accumulator.feed(agent_completed(result or ""))
            except Exception as e:
                logger.exception("Agent error")
                accumulator.feed(agent_failed(str(e)))
            return accumulator.build().to_dict()

        return StreamingResponse(
            event_stream(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",
            },
        )

    # ---- GET /v1/agent/sessions — lazy-loaded session list ----
    # Supports two modes:
    #   1. By workflow: GET /sessions?workflow_id=xxx  — get sessions for a specific canvas
    #   2. All sessions: GET /sessions                 — get all sessions for the user

    @app.get("/v1/agent/sessions")
    async def list_sessions(
        authorization: str | None = Header(default=None),
        workflow_id: str | None = Query(default=None, description="Filter sessions by workflow/flow ID"),
        limit: int = Query(default=10, ge=1, le=50),
        after: str | None = Query(default=None, description="Cursor: session_id of the last item from previous page"),
    ):
        auth_user = _authenticate_agent_request(authorization, cfg)
        return await session_manager.list_sessions(
            user_id=auth_user.user_id,
            workflow_id=workflow_id,
            limit=limit,
            after_session_id=after,
        )

    # ---- GET /v1/agent/sessions/{session_id}/messages — lazy-loaded by turn ----

    @app.get("/v1/agent/sessions/{session_id}/messages")
    async def get_session_messages(
        session_id: str,
        authorization: str | None = Header(default=None),
        turns: int = Query(default=10, ge=1, le=50),
        before_turn: int | None = Query(default=None, description="Cursor: return turns before this turn number"),
    ):
        auth_user = _authenticate_agent_request(authorization, cfg)
        # Verify the session belongs to this user
        session_doc = await session_manager._sessions_col.find_one({"_id": session_id})
        if not session_doc:
            raise HTTPException(status_code=404, detail="Session not found")
        if session_doc.get("user_id") != auth_user.user_id:
            raise HTTPException(status_code=403, detail="Access denied")

        return await session_manager.get_messages_page(
            session_id=session_id,
            turns=turns,
            before_turn=before_turn,
        )

    # ---- GET /health ----

    @app.get("/health")
    async def health():
        return {"status": "ok"}

    return app


def build_app() -> FastAPI:
    """Factory for uvicorn: ``uvicorn creato.api.server:build_app --factory``."""
    import os
    from pathlib import Path

    from creato.config.loader import load_config, set_config_path
    from creato.providers.router import create_provider

    config_file = os.environ.get("CREATO_CONFIG_FILE")
    if config_file:
        p = Path(config_file).expanduser().resolve()
        set_config_path(p)
        config = load_config(p)
    else:
        config = load_config()

    provider = create_provider(config)
    return create_app(config, provider)
