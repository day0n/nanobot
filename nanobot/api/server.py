"""FastAPI SSE server for nanobot agent chat."""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from typing import TYPE_CHECKING

import jwt
from fastapi import FastAPI
from fastapi import Header
from fastapi import HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from loguru import logger
from pydantic import BaseModel

from nanobot.agent.loop import AgentLoop
from nanobot.bus.queue import MessageBus

if TYPE_CHECKING:
    from nanobot.config.schema import Config
    from nanobot.providers.base import LLMProvider


@dataclass(slots=True)
class AuthenticatedAgentUser:
    user_id: str
    token: str


class ChatRequest(BaseModel):
    message: str
    session_id: str = "default"
    flow_id: str | None = None


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

    from nanobot.database.mongo import (
        init_mongo,
        test_mongo,
        ensure_indexes,
        agent_sessions_collection,
        agent_session_messages_collection,
        mongo_client,
    )
    from nanobot.database.redis import init_redis, test_redis, redis_client
    from nanobot.session.manager import SessionManager

    # Initialize database connections (sync — creates clients, no I/O yet)
    init_mongo(config.mongodb.uri, config.mongodb.db)
    init_redis(config.redis.host, config.redis.port, config.redis.password, config.redis.db, config.redis.ssl)

    # Create SessionManager synchronously (Motor/Redis clients don't do I/O at creation)
    from nanobot.database.mongo import agent_sessions_collection, agent_session_messages_collection
    from nanobot.database.redis import redis_client
    session_manager = SessionManager(agent_sessions_collection, agent_session_messages_collection, redis_client)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        # Startup: test connections and create indexes
        await test_mongo()
        await test_redis()
        await ensure_indexes()
        yield
        # Shutdown
        await app.state.agent.close_mcp()
        app.state.agent.stop()
        from nanobot.database.mongo import mongo_client
        from nanobot.database.redis import redis_client as rc
        if rc:
            await rc.close()
        if mongo_client:
            mongo_client.close()

    app = FastAPI(title="nanobot Agent API", version="0.1.0", lifespan=lifespan)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    cfg = config
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
    )
    app.state.agent = agent

    @app.post("/v1/agent/chat")
    async def chat(
        body: ChatRequest,
        authorization: str | None = Header(default=None),
        x_time_zone: str | None = Header(default=None, alias="X-Time-Zone"),
    ):
        auth_user = _authenticate_agent_request(authorization, cfg)
        flow_id = body.flow_id.strip() if isinstance(body.flow_id, str) and body.flow_id.strip() else None
        session_key = (
            f"api:{auth_user.user_id}:flow:{flow_id}:{body.session_id}"
            if flow_id
            else f"api:{auth_user.user_id}:{body.session_id}"
        )
        metadata = {"flow_id": flow_id} if flow_id else None
        private_context = {
            "auth_token": auth_user.token,
            "flow_id": flow_id,
            "time_zone": x_time_zone.strip() if isinstance(x_time_zone, str) and x_time_zone.strip() else None,
            "user_id": auth_user.user_id,
        }

        async def event_stream():
            queue: asyncio.Queue = asyncio.Queue()

            async def on_progress(content: str, *, tool_hint: bool = False, event_type: str | None = None):
                if event_type:
                    await queue.put({"type": event_type, "content": content})
                else:
                    resolved_type = "tool" if tool_hint else "progress"
                    await queue.put({"type": resolved_type, "content": content})

            async def run_agent():
                try:
                    result = await app.state.agent.process_direct(
                        body.message,
                        session_key=session_key,
                        channel="api",
                        chat_id=auth_user.user_id,
                        on_progress=on_progress,
                        metadata=metadata,
                        private_context=private_context,
                    )
                    await queue.put({"type": "done", "content": result or ""})
                except Exception as e:
                    logger.exception("Agent error")
                    await queue.put({"type": "error", "content": str(e)})

            task = asyncio.create_task(run_agent())
            try:
                while True:
                    event = await queue.get()
                    yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
                    if event["type"] in ("done", "error"):
                        break
            finally:
                task.cancel()

        return StreamingResponse(
            event_stream(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",
            },
        )

    @app.get("/v1/agent/sessions")
    async def list_sessions(
        authorization: str | None = Header(default=None),
    ):
        auth_user = _authenticate_agent_request(authorization, cfg)
        sessions = await session_manager.list_sessions(user_id=auth_user.user_id)
        return {"sessions": sessions}

    @app.get("/health")
    async def health():
        return {"status": "ok"}

    return app
