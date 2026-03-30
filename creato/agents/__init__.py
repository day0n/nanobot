"""Agent profile auto-discovery.

Scans sub-packages of `creato.agents` for modules that expose a
top-level ``PROFILE`` attribute (an ``AgentProfile`` instance) and
registers them into a ``ProfileRegistry``.
"""

from __future__ import annotations

import importlib
import logging
import pkgutil
from pathlib import Path

from creato.core.profile import AgentProfile, ProfileRegistry

logger = logging.getLogger(__name__)

_PACKAGE_DIR = Path(__file__).resolve().parent


def discover_profiles() -> ProfileRegistry:
    """Walk immediate sub-packages looking for a ``PROFILE`` object."""
    registry = ProfileRegistry()

    for info in pkgutil.iter_modules([str(_PACKAGE_DIR)]):
        if not info.ispkg:
            continue
        fqn = f"{__name__}.{info.name}"
        try:
            mod = importlib.import_module(fqn)
        except Exception:
            logger.warning("Failed to import agent package %s", fqn, exc_info=True)
            continue

        profile = getattr(mod, "PROFILE", None)
        if isinstance(profile, AgentProfile):
            registry.register(profile)
            logger.debug("Registered agent profile: %s", profile.name)
        else:
            logger.debug("Package %s has no PROFILE; skipped", fqn)

    return registry
