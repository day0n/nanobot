"""MongoDB connection using Motor (async driver).

Connection pattern adapted from opencreator-publisher/database/mongo.py.
"""

import sys

from motor.motor_asyncio import AsyncIOMotorClient
from pymongo.server_api import ServerApi

from loguru import logger

# Module-level singletons, initialised by init_mongo()
mongo_client: AsyncIOMotorClient | None = None
db = None
agent_sessions_collection = None
agent_session_messages_collection = None


def init_mongo(uri: str, db_name: str) -> None:
    """Create the Motor client and bind the sessions collections."""
    global mongo_client, db, agent_sessions_collection, agent_session_messages_collection
    mongo_client = AsyncIOMotorClient(uri, server_api=ServerApi("1"))
    db = mongo_client[db_name]
    agent_sessions_collection = db["agent_sessions"]
    agent_session_messages_collection = db["agent_session_messages"]


async def test_mongo() -> None:
    """Verify connectivity – exits the process on failure."""
    try:
        await db.list_collection_names()
        logger.info("✅ MongoDB connected")
    except Exception as e:
        logger.error("❌ MongoDB connection failed: {}", e)
        sys.exit(1)


async def ensure_indexes() -> None:
    """Create required indexes (idempotent)."""
    await agent_sessions_collection.create_index(
        [("user_id", 1), ("updated_at", -1)],
        name="user_updated_idx",
    )
    await agent_session_messages_collection.create_index(
        [("session_key", 1), ("seq", 1)],
        name="session_seq_idx",
    )
