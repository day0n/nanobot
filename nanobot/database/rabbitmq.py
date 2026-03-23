"""RabbitMQ connection and consumer for workflow execution results.

Receives events from Consumer via RabbitMQ and dispatches them through
an injected callback (set_dispatch_fn). This module has no knowledge of
SSE, WebSocket, or any API-layer concerns.

Architecture: Consumer → RabbitMQ (reply_queue) → this module → dispatch_fn → event_bridge → SSE
"""

from __future__ import annotations

import asyncio
import hashlib
import json
from typing import Any, Callable, Awaitable

import aio_pika
from loguru import logger

# Module-level state, initialised by init_rabbitmq()
_mq_connection: aio_pika.abc.AbstractRobustConnection | None = None
_reply_queue_name: str = ""
_num_workers: int = 3
_worker_queues: dict[int, asyncio.Queue] = {}

# Injected event dispatcher — set by server.py at startup
_dispatch_fn: Callable[[str, dict[str, Any]], Awaitable[bool]] | None = None


def set_dispatch_fn(fn: Callable[[str, dict[str, Any]], Awaitable[bool]]) -> None:
    """Inject the event dispatch function. Called once from server.py at startup."""
    global _dispatch_fn
    _dispatch_fn = fn


def init_rabbitmq(deploy_id: str, num_workers: int = 3) -> None:
    """Set module-level config. Must be called before start_mq_consumer()."""
    global _reply_queue_name, _num_workers, _worker_queues
    _reply_queue_name = f"flow_result.{deploy_id}"
    _num_workers = num_workers
    _worker_queues = {i: asyncio.Queue() for i in range(_num_workers)}


def get_reply_queue_name() -> str:
    """Return the instance-level reply queue name."""
    return _reply_queue_name


async def start_mq_consumer(
    host: str,
    port: int,
    username: str,
    password: str,
    ssl: bool = True,
    prefetch_count: int = 1000,
) -> aio_pika.abc.AbstractRobustConnection:
    """Connect to RabbitMQ, declare reply queue, start worker tasks."""
    global _mq_connection

    _mq_connection = await aio_pika.connect_robust(
        host=host,
        port=port,
        login=username,
        password=password,
        ssl=ssl,
    )
    channel = await _mq_connection.channel()
    await channel.set_qos(prefetch_count=prefetch_count)

    queue = await channel.declare_queue(_reply_queue_name, durable=True)
    logger.info(f"RabbitMQ: listening on reply queue: {_reply_queue_name}")

    await queue.consume(_message_router, no_ack=False)

    for i in range(_num_workers):
        asyncio.create_task(_process_message_worker(i))
    logger.info(f"RabbitMQ: started {_num_workers} consumer workers")

    return _mq_connection


async def close_rabbitmq() -> None:
    """Gracefully close the RabbitMQ connection."""
    global _mq_connection
    if _mq_connection:
        await _mq_connection.close()
        _mq_connection = None
        logger.info("RabbitMQ: connection closed")


def _extract_ws_id(message: aio_pika.IncomingMessage) -> str:
    """Extract ws_id from message headers (handles bytes→str)."""
    ws_id = message.properties.headers.get("ws_id", b"")
    if isinstance(ws_id, bytes):
        ws_id = ws_id.decode("utf-8")
    return ws_id


async def _message_router(message: aio_pika.IncomingMessage) -> None:
    """Route message to the correct worker by MD5(ws_id) % NUM_WORKERS."""
    ws_id = _extract_ws_id(message)
    idx = int(hashlib.md5(ws_id.encode()).hexdigest(), 16) % _num_workers
    await _worker_queues[idx].put(message)


async def _process_message_worker(worker_idx: int) -> None:
    """Worker loop: dequeue messages and dispatch via injected callback."""
    while True:
        try:
            message = await _worker_queues[worker_idx].get()
            ws_id = _extract_ws_id(message)

            try:
                body = json.loads(message.body.decode())
                body.pop("mq_send_timestamp", None)
            except json.JSONDecodeError:
                logger.error(f"RabbitMQ: JSON dec for ws_id={ws_id}")
                await message.reject(requeue=False)
                continue

            if _dispatch_fn and await _dispatch_fn(ws_id, body):
                await message.ack()
            else:
                logger.debug(f"RabbitMQ: no listener for ws_id={ws_id}, rejecting")
                await message.reject(requeue=False)

        except asyncio.CancelledError:
            logger.info(f"RabbitMQ: worker {worker_idx} cancelled")
            break
        except Exception as e:
            logger.error(f"RabbitMQ: worker {worker_idx} error: {e}")
