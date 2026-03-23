"""Sentry SDK initialization for the opencreator_agent."""

from __future__ import annotations

from typing import TYPE_CHECKING

from loguru import logger

if TYPE_CHECKING:
    from nanobot.config.schema import SentryConfig

_initialized = False


def init_sentry(cfg: SentryConfig) -> None:
    """Initialize Sentry SDK with AI Agents module support.

    No-op if DSN is empty or already initialized.
    """
    global _initialized
    if _initialized or not cfg.dsn:
        return

    try:
        import sentry_sdk

        sentry_sdk.init(
            dsn=cfg.dsn,
            environment=cfg.environment,
            traces_sample_rate=cfg.traces_sample_rate,
            profiles_sample_rate=cfg.profiles_sample_rate,
            send_default_pii=cfg.send_default_pii,
            enable_tracing=True,
        )
        _initialized = True
        logger.info("Sentry initialized (env={})", cfg.environment)
    except Exception as e:
        logger.warning("Failed to initialize Sentry: {}", e)
