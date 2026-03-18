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


class ChatRequest(BaseModel):
    message: str
    session_id: str = "default"


def _authenticate_agent_request(
    authorization: str | None,
    config: "Config",
) -> AuthenticatedAgentUser:
    """Authenticate API chat requests with the publisher-issued user JWT.

    When no Clerk PEM public key is configured, auth is disabled for local/dev usage.
    """
    if not config.api.clerk_pem_public_key:
        return AuthenticatedAgentUser(user_id="api_user")

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

    return AuthenticatedAgentUser(user_id=user_id)


def create_app(config: Config, provider: LLMProvider) -> FastAPI:
    """Create the FastAPI application."""
    app = FastAPI(title="nanobot Agent API", version="0.1.0")

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
        mcp_servers=cfg.tools.mcp_servers,
        channels_config=cfg.channels,
    )
    app.state.agent = agent

    @app.on_event("shutdown")
    async def shutdown_event():
        await app.state.agent.close_mcp()
        app.state.agent.stop()

    @app.post("/v1/agent/chat")
    async def chat(
        body: ChatRequest,
        authorization: str | None = Header(default=None),
    ):
        auth_user = _authenticate_agent_request(authorization, cfg)
        session_key = f"api:{auth_user.user_id}:{body.session_id}"

        async def event_stream():
            queue: asyncio.Queue = asyncio.Queue()

            async def on_progress(content: str, *, tool_hint: bool = False):
                event_type = "tool" if tool_hint else "progress"
                await queue.put({"type": event_type, "content": content})

            async def run_agent():
                try:
                    result = await app.state.agent.process_direct(
                        body.message,
                        session_key=session_key,
                        channel="api",
                        chat_id=auth_user.user_id,
                        on_progress=on_progress,
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

    @app.get("/health")
    async def health():
        return {"status": "ok"}

    return app
