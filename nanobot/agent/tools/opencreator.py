"""OpenCreator platform tools."""

from __future__ import annotations

import base64
import json
import math
from copy import deepcopy
from typing import Any
from uuid import uuid4

import httpx
from loguru import logger

from nanobot.agent.request_context import get_request_context
from nanobot.agent.tools.base import Tool

_API_BASE = "https://api-develop.opencreator.io"
_EDITOR_BASE = "https://editor-dev.opencreator.io"
_NODE_WIDTH = 360.0
_DEFAULT_NODE_HEIGHT = 280.0

_SUPPORTED_NODE_TYPES = {
    "textInput",
    "imageInput",
    "videoInput",
    "audioInput",
    "textGenerator",
    "scriptSplit",
    "imageMaker",
    "imageToImage",
    "relight",
    "imageAngleControl",
    "imageUpscaler",
    "backgroundEditor",
    "textToVideo",
    "videoMaker",
    "videoToVideo",
    "klingMotionControl",
    "videoLipSync",
    "imageAudioToVideo",
    "videoUpscaler",
    "textToSpeech",
    "musicGenerator",
    "voiceCloner",
    "assembleNow",
    "stickyNodesNode",
    # compatibility types still recognized by frontend
    "describeImage",
    "oneClickStyle",
    "syncVideoAudio",
    "groupNode",
    "imageAnnotationNode",
    "videoAnnotationNode",
}

_INPUT_NODE_TYPES = {"textInput", "imageInput", "videoInput", "audioInput"}

_NODE_META: dict[str, dict[str, str]] = {
    "textInput": {"label": "Text Input", "description": "Input text content", "themeColor": "black"},
    "imageInput": {"label": "Image Input", "description": "Input image content", "themeColor": "black"},
    "videoInput": {"label": "Video Input", "description": "Input video content", "themeColor": "black"},
    "audioInput": {"label": "Audio Input", "description": "Input audio content", "themeColor": "black"},
    "textGenerator": {"label": "Text Generator", "description": "Generate high-quality text", "themeColor": "#9DFF9E"},
    "scriptSplit": {"label": "Text Splitter", "description": "Split long text into segments", "themeColor": "#9DFF9E"},
    "imageMaker": {"label": "Image Generator", "description": "Generate images from text", "themeColor": "#73ADFF"},
    "imageToImage": {"label": "Image to Image", "description": "Edit image with prompt", "themeColor": "#73ADFF"},
    "relight": {"label": "Relight", "description": "Relight the input image", "themeColor": "#73ADFF"},
    "imageAngleControl": {"label": "Image Angle Control", "description": "Change image angle", "themeColor": "#73ADFF"},
    "imageUpscaler": {"label": "Image Upscaler", "description": "Upscale image quality", "themeColor": "#73ADFF"},
    "backgroundEditor": {"label": "Background Editor", "description": "Edit image background", "themeColor": "#73ADFF"},
    "textToVideo": {"label": "Text to Video", "description": "Generate video from text", "themeColor": "#E781CA"},
    "videoMaker": {"label": "Image to Video", "description": "Generate video from image", "themeColor": "#E781CA"},
    "videoToVideo": {"label": "Video to Video", "description": "Edit video with AI", "themeColor": "#E781CA"},
    "klingMotionControl": {"label": "Motion Control", "description": "Transfer motion to image", "themeColor": "#E781CA"},
    "videoLipSync": {"label": "Video Lip Sync", "description": "Sync lip movement with audio", "themeColor": "#E781CA"},
    "imageAudioToVideo": {"label": "Image Audio to Video", "description": "Animate image with audio", "themeColor": "#E781CA"},
    "videoUpscaler": {"label": "Video Upscaler", "description": "Upscale video quality", "themeColor": "#E781CA"},
    "textToSpeech": {"label": "Text to Speech", "description": "Generate speech from text", "themeColor": "#F4CA11"},
    "musicGenerator": {"label": "Music Generator", "description": "Generate background music", "themeColor": "#F4CA11"},
    "voiceCloner": {"label": "Voice Cloner", "description": "Clone voice timbre", "themeColor": "#F4CA11"},
    "assembleNow": {"label": "Video Editor", "description": "Assemble media assets", "themeColor": "black"},
    "stickyNodesNode": {"label": "Sticky Notes", "description": "Canvas notes", "themeColor": "black"},
    "describeImage": {"label": "Image Describer", "description": "Describe image with text", "themeColor": "#9DFF9E"},
    "oneClickStyle": {"label": "Style Image Generator", "description": "Generate styled image", "themeColor": "#73ADFF"},
    "syncVideoAudio": {"label": "Add Sound to Video", "description": "Add sound to video", "themeColor": "#E781CA"},
}

_DEFAULT_SELECTED_MODELS: dict[str, list[str]] = {
    "textGenerator": ["openai/gpt-4o-mini"],
    "scriptSplit": ["openai/gpt-5.2"],
    "imageMaker": ["minimax/hailuo-image-01"],
    "imageToImage": ["fal-ai/gemini-flash-edit/multi"],
    "relight": ["gemini-3-pro-image-preview"],
    "imageAngleControl": ["fal-ai/qwen-image-edit-2511-multiple-angles"],
    "videoMaker": ["fal-ai/bytedance/seedance/v1/lite/image-to-video"],
    "videoLipSync": ["fal-ai/pixverse/lipsync"],
    "imageAudioToVideo": ["fal-ai/infinitalk"],
    "videoUpscaler": ["fal-ai/topaz/upscale/video"],
    "textToSpeech": ["fish-audio/speech-1.6"],
    "textToVideo": ["fal-ai/minimax/hailuo-02/standard/text-to-video"],
    "voiceCloner": ["fal-ai/qwen-3-tts/clone-voice/1.7b"],
    "videoToVideo": ["fal-ai/kling-video/o3/standard/video-to-video"],
    "klingMotionControl": ["fal-ai/kling-video/v2.6/standard/motion-control"],
    # compatibility defaults
    "describeImage": ["openai/gpt-4o-2024-11-20"],
    "oneClickStyle": ["LA Sunshine"],
}

_DEFAULT_MODEL_CONFIGS: dict[str, dict[str, dict[str, Any]]] = {
    "relight": {
        "gemini-3-pro-image-preview": {
            "light_x": 45,
            "light_y": 30,
            "light_color": "#fffbe6",
            "light_brightness": 70,
            "light_temperature": 5000,
            "light_quality": "product_studio",
            "aspect_ratio": "16:9",
        }
    },
    "imageAngleControl": {
        "fal-ai/qwen-image-edit-2511-multiple-angles": {
            "horizontal_angle": 0,
            "vertical_angle": 0,
            "zoom": 5,
            "lora_scale": 1,
        }
    },
    "textToSpeech": {
        "fish-audio/speech-1.6": {
            "voice_ids": ["Elon_Musk"],
        }
    },
    "klingMotionControl": {
        "fal-ai/kling-video/v2.6/standard/motion-control": {
            "character_orientation": "video",
            "keep_original_sound": True,
        }
    },
}

_DEFAULT_MODEL_OPTIONS: dict[str, dict[str, Any]] = {
    "backgroundEditor": {"model_mode": "Change BG"},
    "videoLipSync": {"loop_mode": "Cut-off"},
    "textGenerator": {"attachments": []},
    "scriptSplit": {"attachments": []},
    "imageUpscaler": {"upscale_factor": "2"},
    "videoUpscaler": {"upscale_factor": "2", "frames_per_second": 24},
    "musicGenerator": {"make_instrumental": False},
    "videoToVideo": {"node_mode": "edit-short", "duration": 5, "keep_audio": True},
    "textToSpeech": {},
}

_DEFAULT_NODE_EXTRAS: dict[str, dict[str, Any]] = {
    "imageMaker": {
        "lensStyleEnabled": False,
        "lensStyle": {
            "camera_style": "none",
            "lens_preset": "none",
            "focal_length": "none",
            "lighting_style": "none",
        },
    },
    "imageToImage": {
        "lensStyleEnabled": False,
        "lensStyle": {
            "camera_style": "none",
            "lens_preset": "none",
            "focal_length": "none",
            "lighting_style": "none",
        },
    },
    "assembleNow": {"assembleAssets": [], "assemblePayload": ""},
    "stickyNodesNode": {
        "stickyMode": "text",
        "stickyArrow": "center",
        "stickyRotation": 0,
        "backgroundColor": "#DDEEDB",
    },
}

_NODE_PIN_CONFIGS: dict[str, dict[str, list[str]]] = {
    "textInput": {"input": [], "output": ["text"]},
    "imageInput": {"input": [], "output": ["image"]},
    "audioInput": {"input": [], "output": ["audio"]},
    "videoInput": {"input": [], "output": ["video"]},
    "textGenerator": {"input": ["text", "image", "video", "audio"], "output": ["text"]},
    "describeImage": {"input": ["image"], "output": ["text"]},
    "scriptSplit": {"input": ["text"], "output": ["text"]},
    "imageMaker": {"input": ["text"], "output": ["image"]},
    "imageToImage": {"input": ["image", "text"], "output": ["image"]},
    "relight": {"input": ["image"], "output": ["image"]},
    "imageAngleControl": {"input": ["image"], "output": ["image"]},
    "oneClickStyle": {"input": ["text"], "output": ["image"]},
    "imageUpscaler": {"input": ["image"], "output": ["image"]},
    "backgroundEditor": {"input": ["image", "text"], "output": ["image"]},
    "videoMaker": {"input": ["image", "text"], "output": ["video"]},
    "textToVideo": {"input": ["text"], "output": ["video"]},
    "syncVideoAudio": {"input": ["video", "text"], "output": ["video"]},
    "videoLipSync": {"input": ["video", "audio"], "output": ["video"]},
    "videoUpscaler": {"input": ["video"], "output": ["video"]},
    "videoToVideo": {"input": ["video", "text", "subject", "style"], "output": ["video"]},
    "klingMotionControl": {"input": ["image", "video", "text"], "output": ["video"]},
    "imageAudioToVideo": {"input": ["image", "audio", "text"], "output": ["video"]},
    "textToSpeech": {"input": ["text"], "output": ["audio"]},
    "voiceCloner": {"input": ["audio", "text"], "output": ["audio"]},
    "musicGenerator": {"input": ["text"], "output": ["audio"]},
    "assembleNow": {"input": ["video", "audio", "image"], "output": ["video"]},
    "stickyNodesNode": {"input": [], "output": []},
    "groupNode": {"input": [], "output": []},
    "imageAnnotationNode": {"input": [], "output": []},
    "videoAnnotationNode": {"input": [], "output": []},
}

_HANDLE_ALIAS: dict[str, str] = {"subject": "image", "style": "image"}
_HANDLE_COMPATIBILITY: dict[str, set[str]] = {"subject": {"image"}, "style": {"image"}}


def _now_ms() -> int:
    from time import time
    return int(time() * 1000)


def _new_node_id(node_type: str) -> str:
    return f"{node_type}-{_now_ms()}-{uuid4().hex[:6]}"


def _as_str(value: Any, default: str = "") -> str:
    return value if isinstance(value, str) else default


def _as_bool(value: Any, default: bool = False) -> bool:
    return value if isinstance(value, bool) else default


def _as_number(value: Any, default: float) -> float:
    if isinstance(value, (int, float)):
        return float(value)
    return default


def _normalize_handle_type(handle_id: str) -> str:
    return _HANDLE_ALIAS.get(handle_id, handle_id)


def _is_handle_compatible(source_handle: str, target_handle: str) -> bool:
    source = _normalize_handle_type(source_handle)
    target = _normalize_handle_type(target_handle)
    if source == target:
        return True
    return source in _HANDLE_COMPATIBILITY.get(target_handle, set())


def _infer_target_handle(source_handle: str, target_handles: list[str]) -> str | None:
    for handle in target_handles:
        if _is_handle_compatible(source_handle, handle):
            return handle
    return None


def _sanitize_selected_models(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    out: list[str] = []
    for item in value:
        if isinstance(item, str) and item.strip():
            out.append(item.strip())
    return out


def _normalize_node_data(node_type: str, raw_data: Any) -> dict[str, Any]:
    data = raw_data if isinstance(raw_data, dict) else {}
    meta = _NODE_META.get(node_type, {})

    normalized: dict[str, Any] = {
        "label": _as_str(meta.get("label"), node_type),
        "description": _as_str(meta.get("description"), ""),
        "themeColor": _as_str(meta.get("themeColor"), "black"),
        "modelCardColor": _as_str(meta.get("themeColor"), "black"),
        "selectedModels": [],
        "inputText": "",
        "imageBase64": "",
        "inputAudio": "",
        "inputVideo": "",
        "status": "idle",
        "isSelectMode": False,
        "isNodeConnected": False,
    }

    # Merge known default patches first, then user data.
    if node_type in _DEFAULT_NODE_EXTRAS:
        normalized.update(deepcopy(_DEFAULT_NODE_EXTRAS[node_type]))

    if node_type in _DEFAULT_SELECTED_MODELS:
        normalized["selectedModels"] = deepcopy(_DEFAULT_SELECTED_MODELS[node_type])

    if node_type in _DEFAULT_MODEL_OPTIONS:
        normalized["model_options"] = deepcopy(_DEFAULT_MODEL_OPTIONS[node_type])

    if node_type in _DEFAULT_MODEL_CONFIGS:
        normalized["modelConfigs"] = deepcopy(_DEFAULT_MODEL_CONFIGS[node_type])

    normalized.update(data)

    # Type-safe fixes after merge
    normalized["label"] = _as_str(normalized.get("label"), meta.get("label", node_type))
    normalized["description"] = _as_str(normalized.get("description"), meta.get("description", ""))
    normalized["themeColor"] = _as_str(normalized.get("themeColor"), meta.get("themeColor", "black"))
    normalized["modelCardColor"] = _as_str(
        normalized.get("modelCardColor"),
        _as_str(normalized.get("themeColor"), meta.get("themeColor", "black")),
    )
    normalized["inputText"] = _as_str(normalized.get("inputText"), "")
    normalized["imageBase64"] = _as_str(normalized.get("imageBase64"), "")
    normalized["inputAudio"] = _as_str(normalized.get("inputAudio"), "")
    normalized["inputVideo"] = _as_str(normalized.get("inputVideo"), "")
    normalized["status"] = _as_str(normalized.get("status"), "idle") or "idle"
    normalized["isSelectMode"] = _as_bool(normalized.get("isSelectMode"), False)
    normalized["isNodeConnected"] = _as_bool(normalized.get("isNodeConnected"), False)

    selected_models = _sanitize_selected_models(normalized.get("selectedModels"))
    if node_type in _INPUT_NODE_TYPES:
        selected_models = []
    elif not selected_models and node_type in _DEFAULT_SELECTED_MODELS:
        selected_models = deepcopy(_DEFAULT_SELECTED_MODELS[node_type])
    normalized["selectedModels"] = selected_models

    model_options = normalized.get("model_options")
    if not isinstance(model_options, dict):
        model_options = {}
    for key, default_val in _DEFAULT_MODEL_OPTIONS.get(node_type, {}).items():
        model_options.setdefault(key, deepcopy(default_val))
    normalized["model_options"] = model_options

    model_configs = normalized.get("modelConfigs")
    if not isinstance(model_configs, dict):
        model_configs = {}
    for model_id, cfg in _DEFAULT_MODEL_CONFIGS.get(node_type, {}).items():
        if model_id in selected_models:
            model_configs.setdefault(model_id, deepcopy(cfg))
    if model_configs:
        normalized["modelConfigs"] = model_configs
    elif "modelConfigs" in normalized:
        del normalized["modelConfigs"]

    return normalized


def _normalize_nodes(raw_nodes: Any) -> tuple[list[dict[str, Any]], dict[str, str], list[str]]:
    warnings: list[str] = []
    if not isinstance(raw_nodes, list):
        return [], {}, ["`nodes` is not a list."]

    normalized_nodes: list[dict[str, Any]] = []
    id_map: dict[str, str] = {}
    seen_ids: set[str] = set()

    for idx, raw in enumerate(raw_nodes):
        if not isinstance(raw, dict):
            warnings.append(f"nodes[{idx}] is not an object and was dropped.")
            continue

        node_type = _as_str(raw.get("type")).strip()
        if not node_type:
            warnings.append(f"nodes[{idx}] missing `type` and was dropped.")
            continue
        if node_type not in _SUPPORTED_NODE_TYPES:
            warnings.append(f"nodes[{idx}] type `{node_type}` is unsupported and was dropped.")
            continue

        raw_id = _as_str(raw.get("id")).strip()
        node_id = raw_id
        if not node_id or node_id in seen_ids:
            node_id = _new_node_id(node_type)
            if raw_id and raw_id in seen_ids:
                warnings.append(f"Duplicate node id `{raw_id}` found; regenerated as `{node_id}`.")
            elif not raw_id:
                warnings.append(f"nodes[{idx}] missing id; generated `{node_id}`.")

        seen_ids.add(node_id)
        if raw_id and raw_id not in id_map:
            id_map[raw_id] = node_id

        pos_raw = raw.get("position")
        x = 100.0 + (idx % 4) * 400.0
        y = 100.0 + (idx // 4) * 300.0
        if isinstance(pos_raw, dict):
            x = _as_number(pos_raw.get("x"), x)
            y = _as_number(pos_raw.get("y"), y)
        else:
            warnings.append(
                f"nodes[{idx}] missing `position`; applied fallback grid position ({int(x)}, {int(y)})."
            )

        node = {
            "id": node_id,
            "type": node_type,
            "position": {"x": x, "y": y},
            "selected": _as_bool(raw.get("selected"), False),
            "data": _normalize_node_data(node_type, raw.get("data")),
        }
        normalized_nodes.append(node)

    return normalized_nodes, id_map, warnings


def _estimate_node_height(node: dict[str, Any]) -> float:
    raw_height = node.get("height")
    if isinstance(raw_height, (int, float)) and raw_height > 0:
        return float(raw_height)

    style = node.get("style")
    if isinstance(style, dict):
        style_height = style.get("height")
        if isinstance(style_height, (int, float)) and style_height > 0:
            return float(style_height)

    data = node.get("data")
    if isinstance(data, dict):
        data_height = data.get("height")
        if isinstance(data_height, (int, float)) and data_height > 0:
            return float(data_height)

    return _DEFAULT_NODE_HEIGHT


def _find_position_issues(nodes: list[dict[str, Any]]) -> list[str]:
    warnings: list[str] = []
    if len(nodes) < 2:
        return warnings

    overlap_count = 0
    for idx, left in enumerate(nodes):
        lx = _as_number(left.get("position", {}).get("x"), 0.0)
        ly = _as_number(left.get("position", {}).get("y"), 0.0)
        lh = _estimate_node_height(left)

        for right in nodes[idx + 1 :]:
            rx = _as_number(right.get("position", {}).get("x"), 0.0)
            ry = _as_number(right.get("position", {}).get("y"), 0.0)
            rh = _estimate_node_height(right)

            same_spot = math.isclose(lx, rx, abs_tol=1.0) and math.isclose(ly, ry, abs_tol=1.0)
            overlaps_x = abs(lx - rx) < _NODE_WIDTH
            overlaps_y = abs(ly - ry) < max(lh, rh)

            if same_spot or (overlaps_x and overlaps_y):
                overlap_count += 1
                if overlap_count <= 8:
                    warnings.append(
                        f"Potential overlap detected between `{left['id']}` and `{right['id']}`."
                    )

    if overlap_count > 8:
        warnings.append(f"... and {overlap_count - 8} more potential overlaps.")

    return warnings


def _normalize_edges(
    raw_edges: Any,
    nodes_by_id: dict[str, dict[str, Any]],
    id_map: dict[str, str],
) -> tuple[list[dict[str, Any]], list[str]]:
    warnings: list[str] = []
    if not isinstance(raw_edges, list):
        return [], ["`edges` is not a list; using empty edge list."]

    normalized_edges: list[dict[str, Any]] = []
    dedupe_keys: set[tuple[str, str, str, str]] = set()

    for idx, raw in enumerate(raw_edges):
        if not isinstance(raw, dict):
            warnings.append(f"edges[{idx}] is not an object and was dropped.")
            continue

        source_raw = _as_str(raw.get("source")).strip()
        target_raw = _as_str(raw.get("target")).strip()
        source = id_map.get(source_raw, source_raw)
        target = id_map.get(target_raw, target_raw)

        if source not in nodes_by_id or target not in nodes_by_id:
            warnings.append(f"edges[{idx}] references unknown node(s) and was dropped.")
            continue

        source_type = _as_str(nodes_by_id[source].get("type"))
        target_type = _as_str(nodes_by_id[target].get("type"))
        source_handles = _NODE_PIN_CONFIGS.get(source_type, {}).get("output", [])
        target_handles = _NODE_PIN_CONFIGS.get(target_type, {}).get("input", [])

        if not source_handles or not target_handles:
            warnings.append(
                f"edges[{idx}] uses node without valid handles ({source_type} -> {target_type}); dropped."
            )
            continue

        source_handle = _as_str(raw.get("sourceHandle")).strip()
        if source_handle not in source_handles:
            source_handle = source_handles[0]

        target_handle = _as_str(raw.get("targetHandle")).strip()
        if target_handle not in target_handles or not _is_handle_compatible(source_handle, target_handle):
            inferred = _infer_target_handle(source_handle, target_handles)
            if not inferred:
                warnings.append(
                    f"edges[{idx}] handle mismatch ({source_handle} -> {target_handle}) and could not be fixed; dropped."
                )
                continue
            target_handle = inferred

        if not _is_handle_compatible(source_handle, target_handle):
            warnings.append(f"edges[{idx}] incompatible handles after normalization and was dropped.")
            continue

        dedupe_key = (source, target, source_handle, target_handle)
        if dedupe_key in dedupe_keys:
            continue
        dedupe_keys.add(dedupe_key)

        edge_id = _as_str(raw.get("id")).strip()
        if not edge_id:
            edge_id = f"edge-{source}-{target}-{source_handle}-{target_handle}-{idx}"

        normalized_edges.append(
            {
                "id": edge_id,
                "source": source,
                "target": target,
                "sourceHandle": source_handle,
                "targetHandle": target_handle,
                "type": "customEdge",
                "animated": True,
            }
        )

    return normalized_edges, warnings


class EditWorkflowTool(Tool):
    """Edit an OpenCreator workflow in the current canvas via the Internal API."""

    name = "edit_workflow"
    description = (
        "Update the workflow (nodes + edges) in the current canvas session. "
        "Requires an authenticated canvas context with flow_id and user_id (both provided automatically). "
        "The tool performs preflight normalization/validation to keep payloads frontend-compatible "
        "(node defaults, edge handle compatibility, dangling-edge cleanup). "
        "Each node MUST include a position with x/y coordinates for correct canvas layout."
    )
    parameters = {
        "type": "object",
        "properties": {
            "nodes": {
                "type": "array",
                "description": (
                    "Array of node objects. Each node MUST include type, id, position ({x, y}), and data. "
                    "Position is required for correct canvas layout — do NOT omit it. "
                    "The tool will auto-fill missing default fields in data and sanitize invalid values."
                ),
                "items": {"type": "object"},
            },
            "edges": {
                "type": "array",
                "description": (
                    "Array of edge objects with source/target/sourceHandle/targetHandle. "
                    "The tool will remove dangling edges, infer missing handles, and enforce compatible handle types."
                ),
                "items": {"type": "object"},
            },
        },
        "required": ["nodes", "edges"],
    }

    def __init__(
        self,
        api_base: str = "",
        internal_api_key: str = "",
        editor_base: str = _EDITOR_BASE,
    ):
        self.api_base = api_base.strip() or _API_BASE
        self.internal_api_key = internal_api_key.strip()
        self.editor_base = editor_base.rstrip("/") or _EDITOR_BASE

    def _auth_header(self) -> str:
        if not self.internal_api_key:
            raise ValueError("internal_api_key is not configured. Set NANOBOT_API__INTERNAL_API_KEY in .env.local.")
        return base64.b64encode(self.internal_api_key.encode("utf-8")).decode("ascii")

    async def execute(
        self,
        *,
        nodes: list,
        edges: list,
        **_: Any,
    ) -> str:
        request_context = get_request_context()
        user_id = request_context.get("user_id")
        flow_id = request_context.get("flow_id")

        if not isinstance(user_id, str) or not user_id.strip():
            return "Error: no authenticated user context. This tool requires a canvas session with a logged-in user."
        user_id = user_id.strip()

        if not isinstance(flow_id, str) or not flow_id.strip():
            return "Error: no flow_id in context. This tool requires an active canvas session with an existing workflow."
        flow_id = flow_id.strip()

        normalized_nodes, id_map, node_warnings = _normalize_nodes(nodes)
        if not normalized_nodes:
            warning_text = "\n".join(f"- {w}" for w in node_warnings[:20]) if node_warnings else ""
            return (
                "Error: no valid nodes left after preflight normalization.\n"
                "Please provide at least one valid node.\n"
                f"{warning_text}"
            )

        nodes_by_id = {n["id"]: n for n in normalized_nodes}
        normalized_edges, edge_warnings = _normalize_edges(edges, nodes_by_id, id_map)
        position_warnings = _find_position_issues(normalized_nodes)
        preflight_warnings = node_warnings + edge_warnings + position_warnings

        payload = {
            "user_id": user_id,
            "flow_id": flow_id,
            "nodes": normalized_nodes,
            "edges": normalized_edges,
        }
        headers = {
            "Content-Type": "application/json",
            "Authorization": self._auth_header(),
        }
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(
                    f"{self.api_base.rstrip('/')}/api/internal/workflow/edit",
                    headers=headers,
                    content=json.dumps(payload, ensure_ascii=False),
                )
        except Exception as e:
            logger.error("edit_workflow HTTP error: {}", e)
            return f"Error: HTTP request failed — {e}"

        if resp.status_code == 404:
            return "Error: workflow or user not found."

        if not resp.is_success:
            return f"Error: API returned {resp.status_code} — {resp.text[:500]}"

        try:
            data = resp.json()
        except Exception:
            return f"Error: Could not parse API response — {resp.text[:300]}"

        result_flow_id = data.get("flow_id") or data.get("data", {}).get("flow_id") or flow_id
        editor_url = f"{self.editor_base}/canvas/{result_flow_id}"

        # Emit workflow_update SSE event so the frontend can refresh the canvas
        on_progress = request_context.get("_on_progress")
        if callable(on_progress):
            try:
                await on_progress(
                    json.dumps({"flow_id": result_flow_id}, ensure_ascii=False),
                    event_type="workflow_update",
                )
            except Exception as e:
                logger.warning("Failed to emit workflow_update event: {}", e)

        message = (
            f"Workflow updated successfully!\n"
            f"  flow_id: {result_flow_id}\n"
            f"  Editor URL: {editor_url}\n"
            f"  Nodes: {len(normalized_nodes)}, Edges: {len(normalized_edges)}"
        )
        if preflight_warnings:
            preview = "\n".join(f"  - {w}" for w in preflight_warnings[:8])
            if len(preflight_warnings) > 8:
                preview += f"\n  - ... and {len(preflight_warnings) - 8} more"
            message += f"\nPreflight adjustments:\n{preview}"
        return message


class GetWorkflowTool(Tool):
    """Fetch the current OpenCreator workflow in the active canvas session."""

    name = "get_workflow"
    description = (
        "Fetch the complete current workflow from the active canvas session, including all nodes, "
        "edges, and their current positions. Use this before editing an existing workflow so "
        "unchanged nodes and layout can be preserved."
    )
    parameters = {
        "type": "object",
        "properties": {},
        "required": [],
    }

    def __init__(self, api_base: str = ""):
        self.api_base = api_base.strip() or _API_BASE

    async def execute(self, **_: Any) -> str:
        request_context = get_request_context()
        flow_id = request_context.get("flow_id")
        auth_token = request_context.get("auth_token")
        on_progress = request_context.get("_on_progress")

        if not isinstance(flow_id, str) or not flow_id.strip():
            return "Error: no flow_id in context. This tool requires an active canvas session."
        flow_id = flow_id.strip()

        if not isinstance(auth_token, str) or not auth_token.strip():
            return "Error: no authenticated user token in context."
        auth_token = auth_token.strip()

        headers = {
            "Authorization": f"Bearer {auth_token}",
        }

        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.get(
                    f"{self.api_base.rstrip('/')}/api/v2/flow/project/{flow_id}",
                    headers=headers,
                )
        except Exception as e:
            logger.error("get_workflow HTTP error: {}", e)
            return f"Error: HTTP request failed — {e}"

        if resp.status_code == 404:
            return "Error: workflow not found."

        if not resp.is_success:
            return f"Error: API returned {resp.status_code} — {resp.text[:500]}"

        try:
            payload = resp.json()
        except Exception:
            return f"Error: Could not parse API response — {resp.text[:300]}"

        data = payload.get("data") if isinstance(payload, dict) else None
        if not isinstance(data, dict):
            return "Error: workflow response missing `data` object."

        nodes = data.get("nodes")
        edges = data.get("edges")
        if not isinstance(nodes, list) or not isinstance(edges, list):
            return "Error: workflow response missing valid `nodes` or `edges`."

        project_name = None
        details = data.get("details")
        if isinstance(details, dict):
            project_name = details.get("project_name")

        result = {
            "flow_id": data.get("flow_id", flow_id),
            "project_name": project_name,
            "nodes": nodes,
            "edges": edges,
        }

        if callable(on_progress):
            try:
                await on_progress(
                    json.dumps(
                        {
                            "flow_id": result["flow_id"],
                            "project_name": project_name,
                            "node_count": len(nodes),
                            "edge_count": len(edges),
                        },
                        ensure_ascii=False,
                    ),
                    event_type="get_workflow",
                )
            except Exception as e:
                logger.warning("Failed to emit get_workflow event: {}", e)

        return json.dumps(result, ensure_ascii=False, indent=2)
