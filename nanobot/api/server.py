"""FastAPI SSE server for nanobot agent chat."""

from __future__ import annotations

import asyncio
import json
from typing import TYPE_CHECKING

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from loguru import logger
from pydantic import BaseModel

from nanobot.agent.loop import AgentLoop
from nanobot.bus.queue import MessageBus

if TYPE_CHECKING:
    from nanobot.config.schema import Config
    from nanobot.providers.base import LLMProvider


class ChatRequest(BaseModel):
    message: str
    session_id: str = "default"


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
        temperature=cfg.agents.defaults.temperature,
        max_tokens=cfg.agents.defaults.max_tokens,
        max_iterations=cfg.agents.defaults.max_tool_iterations,
        memory_window=cfg.agents.defaults.memory_window,
        reasoning_effort=cfg.agents.defaults.reasoning_effort,
        web_proxy=cfg.tools.web.proxy or None,
    )
    app.state.agent = agent

    @app.post("/v1/agent/chat")
    async def chat(body: ChatRequest):
        session_key = f"api:{body.session_id}"

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
                        chat_id="api_user",
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
