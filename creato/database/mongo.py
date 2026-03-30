"""MongoDB connection using Motor (async driver).

Connection pattern adapted from opencreator-publisher/database/mongo.py.

Two databases:
  - Main database (``db``): legacy collections (agent_sessions, agent_session_messages).
  - Agent database (``agent_db``): new three-collection schema for sessions, messages, and tool traces.
"""

import sys

from motor.motor_asyncio import AsyncIOMotorClient
from pymongo.server_api import ServerApi

from loguru import logger

# Module-level singletons, initialised by init_mongo()
mongo_client: AsyncIOMotorClient | None = None

# Legacy collections (kept for backward compatibility during transition)
db = None
agent_sessions_collection = None
agent_session_messages_collection = None

# New agent database collections (opencreator_agent)
agent_db = None
agent_sessions_col = None      # agent_sessions — session metadata
agent_messages_col = None      # agent_messages — all messages (user/agent/assistant/tool)
agent_tool_traces_col = None   # agent_tool_traces — tool execution traces

# Workflow execution collection (shared with publisher/consumer)
flow_task_col = None           # flow_task — workflow execution task records

# Workflow data collections (shared with publisher/consumer)
flow_col = None                # flow — 工作流主表（nodes, edges）
flow_details_col = None        # flow_details — 工作流详情（project_name）
flow_version_col = None        # flow_version — 版本历史快照
results_col = None             # results — 节点执行结果


def init_mongo(uri: str, db_name: str, agent_db_name: str = "opencreator_agent") -> None:
    """Create the Motor client and bind collections for both databases."""
    global mongo_client, db, agent_sessions_collection, agent_session_messages_collection
    global agent_db, agent_sessions_col, agent_messages_col, agent_tool_traces_col
    global flow_task_col
    global flow_col, flow_details_col, flow_version_col, results_col

    mongo_client = AsyncIOMotorClient(uri, server_api=ServerApi("1"))

    # Legacy database
    db = mongo_client[db_name]
    agent_sessions_collection = db["agent_sessions"]
    agent_session_messages_collection = db["agent_session_messages"]

    # New agent database
    agent_db = mongo_client[agent_db_name]
    agent_sessions_col = agent_db["agent_sessions"]
    agent_messages_col = agent_db["agent_messages"]
    agent_tool_traces_col = agent_db["agent_tool_traces"]

    # Workflow execution (shared main database)
    flow_task_col = db["flow_task"]

    # Workflow data (shared main database)
    flow_col = db["flow"]
    flow_details_col = db["flow_details"]
    flow_version_col = db["flow_version"]
    results_col = db["results"]


async def test_mongo() -> None:
    """Verify connectivity – exits the process on failure."""
    try:
        await db.list_collection_names()
        await agent_db.list_collection_names()
        logger.info("✅ MongoDB connected (main + agent)")
    except Exception as e:
        logger.error("❌ MongoDB connection failed: {}", e)
        sys.exit(1)


async def ensure_indexes() -> None:
    """Create required indexes (idempotent)."""
    # Legacy indexes
    await agent_sessions_collection.create_index(
        [("user_id", 1), ("updated_at", -1)],
        name="user_updated_idx",
    )
    await agent_session_messages_collection.create_index(
        [("session_key", 1), ("seq", 1)],
        name="session_seq_idx",
    )

    # --- New agent database indexes  agent_sessions: session list (lazy-load by user, sorted by updated_at)
    await agent_sessions_col.create_index(
        [("user_id", 1), ("updated_at", -1)],
        name="user_updated_idx",
    )
    # agent_sessions: find session by user + workflow
    await agent_sessions_col.create_index(
        [("user_id", 1), ("workflow_id", 1)],
        name="user_workflow_idx",
        partialFilterExpression={"workflow_id": {"$exists": True}},
    )

    # agent_messages: LLM context loading (all roles, ordered by seq)
    await agent_messages_col.create_index(
        [("session_id", 1), ("seq", -1)],
        name="session_seq_idx",
    )
    # agent_messages: frontend pagination (filter by role + turn)
    await agent_messages_col.create_index(
        [("session_id", 1), ("role", 1), ("turn", -1)],
        name="session_role_turn_idx",
    )

    # agent_tool_traces: traces for a session
    await agent_tool_traces_col.create_index(
        [("session_id", 1), ("started_at", -1)],
        name="session_started_idx",
    )
    # agent_tool_traces: performance analysis
    await agent_tool_traces_col.create_index(
        [("tool_name", 1), ("status", 1), ("duration_ms", -1)],
        name="tool_perf_idx",
    )
    # agent_tool_traces: auto-cleanup after 30 days
    await agent_tool_traces_col.create_index(
        [("completed_at", 1)],
        name="ttl_cleanup_idx",
        expireAfterSeconds=2592000,  # 30 days
    )
