"""Funboost Redis Stream publisher for workflow task submission.

Declares the same queue and function signature as Publisher/Consumer
to ensure message format compatibility. Only the publish() method is
used — the function body is empty (Consumer has the actual implementation).
"""

import os
from typing import Any, List, Optional

from funboost import boost, BoosterParams, BrokerEnum, ConcurrentModeEnum


@boost(
    BoosterParams(
        queue_name=os.getenv("CREATO_WORKFLOW__RUN_FLOW_QUEUE", "run_flow"),
        max_retry_times=0,
        concurrent_mode=ConcurrentModeEnum.ASYNC,
        broker_kind=BrokerEnum.REDIS_STREAM,
        concurrent_num=1_000,
    )
)
async def run_flow(
    flow_task_id: str,
    flow_run_type: str,
    flow_run_id: str,
    dag: dict,
    ws_id: str,
    user_selection: Any = None,
    start_ids: List[str] | None = None,
    end_ids: List[str] | None = None,
    user_id: Optional[str] = None,
    trace_id: Optional[str] = None,
    sentry_trace: Optional[str] = None,
    sentry_baggage: Optional[str] = None,
    publish_timestamp: Optional[float] = None,
    reply_queue: Optional[str] = None,
):
    """Publish flow task to Redis Stream. Body is empty — Consumer executes."""
    pass
