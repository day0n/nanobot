# -*- coding: utf-8 -*-
"""Funboost broker connection configuration.

Funboost auto-imports this module from the project root at startup.
We read Redis connection settings from environment variables so that
the config is available before Pydantic Config is loaded.
"""

import os

from funboost.utils.simple_data_class import DataClassBase


class BrokerConnConfig(DataClassBase):
    REDIS_HOST = os.getenv("NANOBOT_REDIS__HOST", "localhost")
    REDIS_PASSWORD = os.getenv("NANOBOT_REDIS__PASSWORD", "")
    REDIS_PORT = int(os.getenv("NANOBOT_REDIS__PORT", "6379"))
    REDIS_DB = int(os.getenv("NANOBOT_REDIS__DB", "0"))
    REDIS_DB_FILTER_AND_RPC_RESULT = int(os.getenv("NANOBOT_REDIS__DB", "0"))
    REDIS_SSL = os.getenv("NANOBOT_REDIS__SSL", "false").lower() == "true"
