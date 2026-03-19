"""Redis connection using redis-py async.

Connection pattern adapted from opencreator-publisher/database/redis.py.
"""

import sys

from redis.asyncio import ConnectionPool, Redis
from redis.asyncio.connection import SSLConnection
from redis.exceptions import AuthenticationError, TimeoutError

from loguru import logger

# Module-level singleton, initialised by init_redis()
redis_client: Redis | None = None


def init_redis(
    host: str = "localhost",
    port: int = 6379,
    password: str = "",
    db: int = 0,
    ssl: bool = False,
) -> None:
    """Create the async Redis client with connection pooling."""
    global redis_client

    connection_kwargs: dict = {
        "host": host,
        "port": port,
        "db": db,
        "max_connections": 256,
        "decode_responses": True,
    }
    if password:
        connection_kwargs["password"] = password
    if ssl:
        connection_kwargs["connection_class"] = SSLConnection
        connection_kwargs["ssl_cert_reqs"] = None  # No client cert verification (AWS ElastiCache)

    pool = ConnectionPool(**connection_kwargs)
    redis_client = Redis(connection_pool=pool)


async def test_redis() -> None:
    """Verify connectivity – exits the process on failure."""
    try:
        await redis_client.ping()
        logger.info("✅ Redis connected")
    except TimeoutError:
        logger.error("❌ Redis connection timeout")
        sys.exit(1)
    except AuthenticationError:
        logger.error("❌ Redis authentication failed")
        sys.exit(1)
    except Exception as e:
        logger.error("❌ Redis connection error: {}", e)
        sys.exit(1)
