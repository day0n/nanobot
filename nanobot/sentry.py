"""Sentry SDK initialization for the opencreator_agent."""

from __future__ import annotations

from typing import TYPE_CHECKING

from loguru import logger

if TYPE_CHECKING:
    from nanobot.config.schema import SentryConfig

_initialized = False


def before_send_transaction(event, hint):
    """Filter out health check transactions."""
    name = event.get("transaction", "")
    if name in ("/health", "/readyz"):
        return None
    return event


def traces_sampler(sampling_context):
    """Dynamic sampling rate."""
    name = sampling_context.get("transaction_context", {}).get("name", "")
    if name in ("/health", "/readyz"):
        return 0
    return 1.0  # agent 请求量小，全量采样


def init_sentry(cfg: SentryConfig) -> None:
    """Initialize Sentry SDK with AI Agents module support.

    No-op if DSN is empty or already initialized.
    """
    global _initialized
    if _initialized or not cfg.dsn:
        logger.info("Sentry skipped (dsn={})", "set" if cfg.dsn else "empty")
        return

    try:
        import sentry_sdk
        from sentry_sdk.integrations.fastapi import FastApiIntegration
        from sentry_sdk.integrations.loguru import LoguruIntegration
        from sentry_sdk.integrations.httpx import HttpxIntegration
        from sentry_sdk.integrations.pymongo import PyMongoIntegration
        from sentry_sdk.integrations.redis import RedisIntegration

        sentry_sdk.init(
            dsn=cfg.dsn,
            environment=cfg.environment,
            server_name="agent",
            traces_sampler=traces_sampler,
            profiles_sample_rate=cfg.profiles_sample_rate,
            send_default_pii=cfg.send_default_pii,
            integrations=[
                FastApiIntegration(transaction_style="endpoint"),
                LoguruIntegration(level="INFO", event_level="CRITICAL"),
                HttpxIntegration(),
                PyMongoIntegration(),
                RedisIntegration(),
            ],
            before_send_transaction=before_send_transaction,
        )
        _initialized = True
        logger.info("Sentry initialized (env={}, server=agent)", cfg.environment)
    except Exception as e:
        logger.warning("Failed to initialize Sentry: {}", e)
