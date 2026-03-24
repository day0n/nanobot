"""Sentry SDK initialization and safe instrumentation helpers."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from loguru import logger

if TYPE_CHECKING:
    from creato.config.schema import SentryConfig

_initialized = False


# ---------------------------------------------------------------------------
# Safe span wrapper — all Sentry calls are no-op on failure
# ---------------------------------------------------------------------------

class SafeSpan:
    """Sentry span wrapper that never raises.

    Usage::

        with SafeSpan("gen_ai.request", "chat gemini-3") as span:
            span.set_data("gen_ai.request.model", "gemini-3")
            result = await do_llm_call()
            span.set_data("gen_ai.usage.input_tokens", 123)

    If Sentry is not initialized or any API call fails, every method is a
    silent no-op — business logic is never affected.
    """

    __slots__ = ("_span",)

    def __init__(self, op: str, name: str):
        try:
            import sentry_sdk
            self._span = sentry_sdk.start_span(op=op, name=name)
        except Exception:
            self._span = None

    def set_data(self, key: str, value: Any) -> None:
        try:
            if self._span:
                self._span.set_data(key, value)
        except Exception:
            pass

    def set_status(self, status: str) -> None:
        try:
            if self._span:
                self._span.set_status(status)
        except Exception:
            pass

    def __enter__(self) -> SafeSpan:
        try:
            if self._span:
                self._span.__enter__()
        except Exception:
            self._span = None
        return self

    def __exit__(self, *exc_info) -> None:
        try:
            if self._span:
                self._span.__exit__(None, None, None)
        except Exception:
            pass


class SafeTransaction(SafeSpan):
    """Sentry transaction wrapper (root span) that never raises."""

    def __init__(self, op: str, name: str):
        try:
            import sentry_sdk
            self._span = sentry_sdk.start_transaction(op=op, name=name)
        except Exception:
            self._span = None


def set_sentry_context(*, user_id: str = "", tags: dict[str, str] | None = None) -> None:
    """Set Sentry user and tags. Silent no-op on failure."""
    try:
        import sentry_sdk
        if user_id:
            sentry_sdk.set_user({"id": user_id})
        for k, v in (tags or {}).items():
            sentry_sdk.set_tag(k, v)
    except Exception:
        pass


# ---------------------------------------------------------------------------
# SDK initialization
# ---------------------------------------------------------------------------

def _before_send_transaction(event, hint):
    """Filter out health check transactions."""
    name = event.get("transaction", "")
    if name in ("/health", "/readyz"):
        return None
    return event


def _traces_sampler(sampling_context):
    """Dynamic sampling rate."""
    name = sampling_context.get("transaction_context", {}).get("name", "")
    if name in ("/health", "/readyz"):
        return 0
    return 1.0  # agent 请求量小，全量采样


def init_sentry(cfg: SentryConfig) -> None:
    """Initialize Sentry SDK.

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
            traces_sampler=_traces_sampler,
            profiles_sample_rate=cfg.profiles_sample_rate,
            send_default_pii=cfg.send_default_pii,
            integrations=[
                FastApiIntegration(transaction_style="endpoint"),
                LoguruIntegration(level="INFO", event_level="CRITICAL"),
                HttpxIntegration(),
                PyMongoIntegration(),
                RedisIntegration(),
            ],
            before_send_transaction=_before_send_transaction,
        )
        _initialized = True
        logger.info("Sentry initialized (env={}, server=agent)", cfg.environment)
    except Exception as e:
        logger.warning("Failed to initialize Sentry: {}", e)
