"""Skills loader for agent capabilities.

Skills are SKILL.md files with a flat frontmatter header. Each skill lives in
its own subdirectory under the built-in skills directory. The loader scans once
at init time and caches parsed ``SkillInfo`` objects — no repeated disk reads.

Supported frontmatter fields (all optional except ``name``)::

    ---
    name: weather
    description: Get current weather and forecasts.
    trigger: When user asks about weather
    emoji: 🌤️
    homepage: https://wttr.in
    always: true
    requires_bins: curl, jq
    requires_env: API_KEY
    install_hint: brew install curl
    ---

Only flat single-line ``key: value`` scalars are supported. Nested YAML,
multi-line values, and flow sequences are explicitly rejected.
"""

from __future__ import annotations

import os
import shutil
from dataclasses import dataclass
from pathlib import Path

from loguru import logger

# Skills directory is the parent of this file (agent/skills/)
BUILTIN_SKILLS_DIR = Path(__file__).parent

# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass(slots=True)
class SkillInfo:
    """Parsed skill — cached at init time, immutable thereafter."""

    name: str
    description: str
    trigger: str
    emoji: str
    homepage: str
    always: bool
    requires_bins: list[str]
    requires_env: list[str]
    install_hint: str
    content: str       # full SKILL.md with {skill_dir} resolved
    body: str          # content minus frontmatter, {skill_dir} resolved
    path: Path         # absolute path to SKILL.md
    skill_dir: Path    # parent directory of SKILL.md
    available: bool    # True when all requirements are met


# ---------------------------------------------------------------------------
# Frontmatter parser (flat single-line scalars only)
# ---------------------------------------------------------------------------

def _parse_frontmatter(text: str) -> tuple[dict[str, str], str]:
    """Parse frontmatter from markdown text.

    Returns ``(fields, body)`` where *fields* is a dict of string key-value
    pairs and *body* is the remaining content after the closing ``---``.

    Rules:
    - Opening ``---`` must be the very first line.
    - Closing ``---`` must appear on its own line.
    - Only ``key: value`` lines are accepted (flat scalars).
    - Blank lines and ``#`` comment lines inside the block are skipped.
    - Lines that don't match ``key: value`` are logged and skipped.
    - Values wrapped in matching quotes (``"`` or ``'``) are unquoted.
    - BOM (``\\ufeff``) at the start of the file is stripped.
    """
    # Strip BOM
    if text.startswith("\ufeff"):
        text = text[1:]

    # Normalise line endings
    text = text.replace("\r\n", "\n").replace("\r", "\n")

    if not text.startswith("---\n") and text != "---":
        return {}, text

    # Find closing ---
    close = text.find("\n---", 3)
    if close == -1:
        logger.warning("Frontmatter has no closing '---', treating entire file as body")
        return {}, text
    fm_block = text[4:close]                    # between opening and closing ---
    body = text[close + 4:].lstrip("\n")        # after closing ---\n

    fields: dict[str, str] = {}
    for line in fm_block.split("\n"):
        line = line.strip()
        if not line or line.startswith("#"):
            continue

        colon = line.find(":")
        if colon == -1:
            logger.debug("Skipping frontmatter line (no colon): {!r}", line)
            continue

        key = line[:colon].strip()
        value = line[colon + 1:].strip()

        # Reject values that look like nested structures (JSON objects/arrays,
        # YAML flow sequences).  These are not supported and almost certainly
        # indicate a leftover legacy format or a copy-paste mistake.
        if value and value[0] in ('{', '['):
            logger.warning(
                "Frontmatter value for '{}' looks like JSON/nested YAML — "
                "only flat scalars are supported. Skipping this field.",
                key,
            )
            continue

        # Unquote surrounding quotes
        if len(value) >= 2 and value[0] == value[-1] and value[0] in ('"', "'"):
            value = value[1:-1]

        fields[key] = value

    return fields, body


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse_csv(value: str) -> list[str]:
    """Split a comma-separated string into a trimmed list."""
    return [v.strip() for v in value.split(",") if v.strip()] if value else []


def _parse_bool(value: str) -> bool:
    """Parse a frontmatter boolean string. Only ``"true"`` (case-insensitive) is True."""
    return value.strip().lower() == "true"


def _check_requirements(bins: list[str], env_vars: list[str]) -> bool:
    """Return True if all required binaries and env vars are present."""
    return all(shutil.which(b) for b in bins) and all(os.environ.get(e) for e in env_vars)


def _format_missing(bins: list[str], env_vars: list[str]) -> str:
    """Human-readable list of missing requirements."""
    parts: list[str] = []
    for b in bins:
        if not shutil.which(b):
            parts.append(f"CLI: {b}")
    for e in env_vars:
        if not os.environ.get(e):
            parts.append(f"ENV: {e}")
    return ", ".join(parts)


def _escape_xml(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


# ---------------------------------------------------------------------------
# Loader
# ---------------------------------------------------------------------------

class SkillsLoader:
    """Loader for platform built-in agent skills.

    All SKILL.md files are parsed once at construction time. Subsequent calls
    are pure dict lookups with zero disk I/O. Call :meth:`reload` to re-scan
    after on-disk changes (or restart the process).
    """

    def __init__(self, builtin_skills_dir: Path | None = None):
        self.builtin_skills = builtin_skills_dir or BUILTIN_SKILLS_DIR
        self._skills: dict[str, SkillInfo] = {}
        self._load_all()

    # -- Scanning & parsing --------------------------------------------------

    def _load_all(self) -> None:
        """Scan skill directories and parse every SKILL.md into a SkillInfo."""
        self._skills.clear()

        if not self.builtin_skills or not self.builtin_skills.exists():
            return

        for entry in sorted(self.builtin_skills.iterdir(), key=lambda p: p.name):
            if not entry.is_dir():
                continue
            skill_file = entry / "SKILL.md"
            if not skill_file.exists():
                continue  # positive signal: only dirs with SKILL.md are skills

            try:
                raw = skill_file.read_text(encoding="utf-8")
            except OSError as exc:
                logger.warning("Failed to read {}: {}", skill_file, exc)
                continue

            fields, body = _parse_frontmatter(raw)
            name = fields.get("name", "")

            # Name must match directory — otherwise load_skill("dir_name") and
            # load_skill("frontmatter_name") would diverge silently.
            if name and name != entry.name:
                logger.warning(
                    "Skill skipped: directory '{}' but frontmatter name is '{}' — they must match",
                    entry.name, name,
                )
                continue

            if not name:
                name = entry.name
                logger.debug("Skill '{}' has no name in frontmatter, using directory name", name)

            if not fields.get("description"):
                logger.warning("Skill '{}' has no description in frontmatter", name)

            # Detect legacy 'metadata' field — it was a JSON blob in the old
            # format and is no longer consumed.  Warn loudly so the author
            # migrates to flat fields (requires_bins, emoji, etc.).
            if "metadata" in fields:
                logger.warning(
                    "Skill '{}' still has a 'metadata' field in frontmatter. "
                    "This field is ignored — migrate to flat fields "
                    "(requires_bins, requires_env, emoji, always, install_hint).",
                    name,
                )

            requires_bins = _parse_csv(fields.get("requires_bins", ""))
            requires_env = _parse_csv(fields.get("requires_env", ""))

            # Resolve {skill_dir} placeholder uniformly for both load paths
            resolved_content = raw.replace("{skill_dir}", str(entry))
            resolved_body = body.replace("{skill_dir}", str(entry))

            self._skills[name] = SkillInfo(
                name=name,
                description=fields.get("description", ""),
                trigger=fields.get("trigger", ""),
                emoji=fields.get("emoji", ""),
                homepage=fields.get("homepage", ""),
                always=_parse_bool(fields.get("always", "")),
                requires_bins=requires_bins,
                requires_env=requires_env,
                install_hint=fields.get("install_hint", ""),
                content=resolved_content,
                body=resolved_body,
                path=skill_file,
                skill_dir=entry,
                available=_check_requirements(requires_bins, requires_env),
            )

        logger.debug("Loaded {} skill(s): {}", len(self._skills), list(self._skills))

    def reload(self) -> None:
        """Re-scan skill directories and rebuild the cache.

        Call this after modifying SKILL.md files on disk at runtime.
        Under normal operation a process restart achieves the same effect.
        """
        self._load_all()

    # -- Public API (signatures preserved for compatibility) ------------------

    def list_skills(self, filter_unavailable: bool = True) -> list[dict[str, str]]:
        """List all built-in skills.

        Returns list of dicts with ``name``, ``path``, ``source`` keys.
        """
        skills = [
            {"name": s.name, "path": str(s.path), "source": "builtin"}
            for s in self._skills.values()
        ]
        if filter_unavailable:
            return [s for s in skills if self._skills[s["name"]].available]
        return skills

    def load_skill(self, name: str) -> str | None:
        """Load full skill content by name (with ``{skill_dir}`` resolved)."""
        info = self._skills.get(name)
        return info.content if info else None

    def load_skills_for_context(self, skill_names: list[str]) -> str:
        """Load skills for direct injection into agent context (always-on path)."""
        parts = []
        for name in skill_names:
            info = self._skills.get(name)
            if info:
                parts.append(f"### Skill: {name}\n\n{info.body}")
        return "\n\n---\n\n".join(parts) if parts else ""

    def build_skills_summary(self) -> str:
        """Build XML summary of all skills for progressive loading."""
        if not self._skills:
            return ""

        lines = ["<skills>"]
        for info in self._skills.values():
            lines.append(f'  <skill available="{str(info.available).lower()}">')
            lines.append(f"    <name>{_escape_xml(info.name)}</name>")
            lines.append(f"    <description>{_escape_xml(info.description or info.name)}</description>")
            if info.trigger:
                lines.append(f"    <trigger>{_escape_xml(info.trigger)}</trigger>")
            if not info.available:
                missing = _format_missing(info.requires_bins, info.requires_env)
                if missing:
                    lines.append(f"    <requires>{_escape_xml(missing)}</requires>")
            lines.append("  </skill>")
        lines.append("</skills>")
        return "\n".join(lines)

    def get_always_skills(self) -> list[str]:
        """Get names of skills marked ``always: true`` that have met requirements."""
        return [name for name, info in self._skills.items() if info.always and info.available]

    def get_skill_metadata(self, name: str) -> dict | None:
        """Get flat metadata dict for a skill (legacy compatibility).

        Returns all frontmatter fields so callers can treat this as a
        complete metadata snapshot.
        """
        info = self._skills.get(name)
        if not info:
            return None
        return {
            "name": info.name,
            "description": info.description,
            "trigger": info.trigger,
            "emoji": info.emoji,
            "homepage": info.homepage,
            "always": str(info.always).lower(),
            "install_hint": info.install_hint,
            "requires_bins": ", ".join(info.requires_bins),
            "requires_env": ", ".join(info.requires_env),
            "available": str(info.available).lower(),
        }

    def get_skill_info(self, name: str) -> SkillInfo | None:
        """Get the typed SkillInfo object (preferred over get_skill_metadata)."""
        return self._skills.get(name)
