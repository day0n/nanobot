"""GetNodeSpecTool — on-demand node specifications for workflow construction."""

from __future__ import annotations

import json
from typing import Any

from creato.core.tools.base import Tool
from creato.core.tools.opencreator import common
from creato.core.tools.opencreator import node_model_catalog as catalog


class GetNodeSpecTool(Tool):
    """Return detailed specs for requested node types in a single batched call."""

    name = "get_node_spec"
    description = (
        "Get detailed specs (model tables, configs, prompt guidance) for specific node types. "
        "Call AFTER deciding which nodes to use (from the catalog in SKILL.md), "
        "BEFORE constructing node JSON for edit_workflow. "
        "Accepts multiple types in one call to minimize round trips. "
        "Optionally include workflow pattern templates for complex scenarios."
    )
    parameters = {
        "type": "object",
        "properties": {
            "node_types": {
                "type": "array",
                "items": {"type": "string"},
                "description": (
                    "List of node type names to get specs for, "
                    "e.g. ['imageMaker', 'textGenerator', 'textToSpeech']"
                ),
            },
            "patterns": {
                "type": "array",
                "items": {"type": "string"},
                "description": (
                    "Optional workflow pattern templates to include: "
                    "ugc-ad, video-lipsync, image-lipsync, multi-image"
                ),
            },
        },
        "required": ["node_types"],
    }

    async def execute(
        self,
        *,
        node_types: list[str],
        patterns: list[str] | None = None,
        **_: Any,
    ) -> str:
        if not node_types:
            return "Error: node_types must not be empty."

        # Validate node types against the runtime whitelist in common.py
        unknown = [nt for nt in node_types if nt not in common._SUPPORTED_NODE_TYPES]
        if unknown:
            return (
                f"Error: unknown node type(s): {', '.join(unknown)}.\n"
                f"Supported: {', '.join(sorted(common._SUPPORTED_NODE_TYPES))}"
            )

        parts: list[str] = []
        categories_seen: set[str] = set()

        for nt in node_types:
            parts.append(self._format_node_spec(nt))
            cat = catalog.NODE_CATEGORIES.get(nt)
            if cat:
                categories_seen.add(cat)

        # Auto-attach prompt guides for the categories used
        for cat in sorted(categories_seen):
            guide = catalog.PROMPT_GUIDES.get(cat)
            if guide:
                parts.append(guide)

        # Attach requested workflow pattern templates
        for p in patterns or []:
            template = catalog.WORKFLOW_PATTERNS.get(p)
            if template:
                parts.append(template)
            else:
                available = ", ".join(sorted(catalog.WORKFLOW_PATTERNS))
                parts.append(f"(Unknown pattern '{p}'. Available: {available})")

        # Always append construction guide (JSON templates, forbidden fields, etc.)
        parts.append(catalog.CONSTRUCTION_GUIDE)

        return "\n\n---\n\n".join(parts)

    # ------------------------------------------------------------------

    @staticmethod
    def _format_node_spec(node_type: str) -> str:
        """Format a single node type's spec as compact markdown."""
        meta = common._NODE_META.get(node_type, {})
        pins = common._NODE_PIN_CONFIGS.get(node_type, {})
        default_models = common._DEFAULT_SELECTED_MODELS.get(node_type, [])
        model_configs = common._DEFAULT_MODEL_CONFIGS.get(node_type, {})
        model_options = common._DEFAULT_MODEL_OPTIONS.get(node_type, {})
        extras = common._DEFAULT_NODE_EXTRAS.get(node_type, {})
        available = catalog.AVAILABLE_MODELS.get(node_type, [])
        rules = catalog.SPECIAL_RULES.get(node_type, [])
        limits = catalog.CONNECTION_LIMITS.get(node_type, {})
        requires = node_type in catalog.REQUIRES_SELECTED_MODELS

        display = meta.get("label", node_type)
        in_pins = ", ".join(pins.get("input", [])) or "—"
        out_pins = ", ".join(pins.get("output", [])) or "—"
        default_str = ", ".join(default_models) if default_models else "—"

        lines: list[str] = []
        lines.append(f"## {node_type} ({display})")
        header = f"Input: {in_pins} | Output: {out_pins}"
        if requires:
            header += " | Requires selectedModels"
        lines.append(header)
        lines.append(f"Default model: {default_str}")

        # Limits
        if limits:
            limit_parts = [f"{pin}≤{n}" for pin, n in limits.items()]
            lines.append(f"Connection limits: {', '.join(limit_parts)}")

        # Available models table
        if available:
            lines.append("")
            lines.append("Available models:")
            lines.append("| API ID | Name | Note |")
            lines.append("|--------|------|------|")
            for m in available:
                note = m.get("note", "")
                lines.append(f"| {m['id']} | {m['name']} | {note} |")

        # Default modelConfigs
        if model_configs:
            lines.append("")
            lines.append(f"Default modelConfigs: `{json.dumps(model_configs, ensure_ascii=False)}`")

        # Default model_options
        if model_options:
            lines.append(f"Default model_options: `{json.dumps(model_options, ensure_ascii=False)}`")

        # Extra fields
        if extras:
            flat = _flatten_extras(extras)
            lines.append(f"Extra fields: {flat}")

        # Special rules
        if rules:
            lines.append("")
            lines.append("Rules:")
            for r in rules:
                lines.append(f"- {r}")

        return "\n".join(lines)


def _flatten_extras(extras: dict[str, Any], prefix: str = "") -> str:
    """Flatten nested extras dict into a compact one-liner."""
    parts: list[str] = []
    for k, v in extras.items():
        key = f"{prefix}.{k}" if prefix else k
        if isinstance(v, dict):
            parts.append(_flatten_extras(v, key))
        else:
            parts.append(f"{key}={json.dumps(v)}")
    return ", ".join(parts)
