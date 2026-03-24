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

from creato.agent.events import (
    AgentEvent,
    AgentResponse,
    ResponseAccumulator,
    agent_completed,
    agent_failed,
    agent_heartbeat,
    agent_started,
)
from creato.agent.loop import AgentLoop
from creato.bus.queue import MessageBus

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
    from creato.posthog import init_posthog, shutdown_posthog
    from creato.database.mongo import (
        init_mongo,
        test_mongo,
        ensure_indexes,
        agent_sessions_col,
        agent_messages_col,
        agent_tool_traces_col,
        mongo_client,
    )
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

    # Create SessionManager with new three-collection schema
    from creato.database.mongo import agent_sessions_col, agent_messages_col, agent_tool_traces_col
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
            from creato.agent.tools.opencreator import RunWorkflowTool
            app.state.agent.tools.register(RunWorkflowTool(
                api_base=cfg.api.internal_api_base,
                workflow_engine=app.state.workflow_engine,
            ))
            app.state.agent._sync_tool_names()  # update prompt after dynamic tool registration

            logger.info(f"Workflow engine ready, reply_queue={get_reply_queue_name()}")

        yield

        # Shutdown
        shutdown_posthog()
        if mq_connection:
            await close_rabbitmq()
        await app.state.agent.close_mcp()
        app.state.agent.stop()
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
    # Resolve summary model API key from providers config
    _summary_key = (cfg.get_provider(cfg.agents.defaults.summary_model) or cfg.providers.openai).api_key or None
    agent = AgentLoop(
        bus=MessageBus(),
        provider=provider,
        workspace=cfg.workspace_path,
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
        summary_model=cfg.agents.defaults.summary_model,
        summary_api_key=_summary_key,
    )
    app.state.agent = agent

    # ---- POST /v1/agent/chat — SSE streaming chat ----

    @app.post("/v1/agent/chat")
    async def chat(
        body: ChatRequest,
        authorization: str | None = Header(default=None),
        x_time_zone: str | None = Header(default=None, alias="X-Time-Zone"),
    ):
        auth_user = _authenticate_agent_request(authorization, cfg)
        flow_id = body.flow_id.strip() if isinstance(body.flow_id, str) and body.flow_id.strip() else None

        # session_id is passed directly from frontend as the primary key
        session_id = body.session_id

        # Private context for tools (not exposed to LLM prompt)
        private_context = {
            "auth_token": auth_user.token,
            "flow_id": flow_id,
            "time_zone": x_time_zone.strip() if isinstance(x_time_zone, str) and x_time_zone.strip() else None,
            "user_id": auth_user.user_id,
        }

        # Merge frontend metadata with flow_id
        request_metadata = dict(body.metadata or {})
        if flow_id:
            request_metadata["flow_id"] = flow_id

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
