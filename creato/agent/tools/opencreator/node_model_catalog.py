"""Supplementary catalog data for GetNodeSpecTool.

Runtime defaults (selectedModels, modelConfigs, model_options, pin configs)
live in ``common.py`` and are the **single source of truth**.  This module only
adds information that ``common.py`` does not carry:

* Available model lists (all selectable models per node type)
* Human-readable special rules
* Connection limits per pin
* Node category mapping
* Prompt writing guides (per category)
* Workflow structure pattern templates
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Available models per node type (common.py only has the *default*)
# ---------------------------------------------------------------------------

AVAILABLE_MODELS: dict[str, list[dict[str, str]]] = {
    "textGenerator": [
        {"id": "google/gemini-3-pro-preview", "name": "Gemini 3 Pro"},
        {"id": "google/gemini-3-flash-preview", "name": "Gemini 3 Flash"},
        {"id": "google/gemini-2.0-flash", "name": "Gemini 2.0 Flash"},
        {"id": "openai/gpt-5.2-pro", "name": "GPT 5.2 Pro"},
        {"id": "openai/gpt-5.2", "name": "GPT 5.2"},
        {"id": "openai/gpt-5", "name": "GPT 5"},
        {"id": "openai/gpt-4o-2024-11-20", "name": "GPT 4o"},
        {"id": "openai/gpt-4o-mini", "name": "GPT 4o Mini", "note": "default"},
    ],
    "scriptSplit": [
        {"id": "openai/gpt-5.2", "name": "GPT 5.2", "note": "default"},
    ],
    "imageMaker": [
        {"id": "gemini-3-pro-image-preview", "name": "Banana Pro", "note": "realistic, high-res"},
        {"id": "fal-ai/nano-banana", "name": "Nano Banana"},
        {"id": "fal-ai/gemini-3.1-flash-image-preview", "name": "Nano Banana 2"},
        {"id": "fal-ai/imagen4/preview", "name": "Imagen 4"},
        {"id": "fal-ai/gpt-image-1.5", "name": "GPT Image 1.5"},
        {"id": "openai/gpt-image-1", "name": "GPT Image 1"},
        {"id": "xai/grok-imagine-image", "name": "Grok Imagine"},
        {"id": "fal-ai/flux-2-pro", "name": "Flux 2 Pro"},
        {"id": "fal-ai/flux-pro/v1.1", "name": "Flux 1.1 Pro"},
        {"id": "fal-ai/bytedance/seedream/v5/lite/text-to-image", "name": "Seedream 5.0 Lite"},
        {"id": "fal-ai/bytedance/seedream/v4.5/text-to-image", "name": "Seedream 4.5"},
        {"id": "fal-ai/bytedance/seedream/v4/text-to-image", "name": "Seedream 4.0"},
        {"id": "minimax/hailuo-image-01", "name": "Hailuo Image 01", "note": "default"},
        {"id": "fal-ai/fast-sdxl", "name": "SDXL Fast"},
        {"id": "fal-ai/bytedance/seedream/v5/text-to-image", "name": "Seedream 5.0", "note": "comingSoon, do not use"},
    ],
    "imageToImage": [
        {"id": "gemini-3-pro-image-preview", "name": "Banana Pro"},
        {"id": "fal-ai/nano-banana/edit", "name": "Nano Banana"},
        {"id": "fal-ai/gemini-3.1-flash-image-preview/edit", "name": "Nano Banana 2"},
        {"id": "fal-ai/gpt-image-1.5/edit", "name": "GPT Image 1.5"},
        {"id": "openai/gpt-image-1", "name": "GPT Image 1"},
        {"id": "fal-ai/flux-pro/kontext/multi", "name": "Flux Kontext"},
        {"id": "fal-ai/flux-2-pro/edit", "name": "Flux 2 Pro"},
        {"id": "fal-ai/gemini-flash-edit/multi", "name": "Gemini 2.0 Flash", "note": "default"},
        {"id": "fal-ai/qwen-image-edit-plus", "name": "Qwen Image Edit"},
        {"id": "fal-ai/bytedance/seedream/v5/lite/edit", "name": "Seedream 5.0 Lite"},
        {"id": "fal-ai/bytedance/seedream/v4.5/edit", "name": "Seedream 4.5"},
        {"id": "fal-ai/bytedance/seedream/v4/edit", "name": "Seedream 4.0"},
        {"id": "xai/grok-imagine-image/edit", "name": "Grok Imagine"},
        {"id": "fal-ai/bytedance/seedream/v5/edit", "name": "Seedream 5.0", "note": "comingSoon, do not use"},
    ],
    "videoMaker": [
        {"id": "fal-ai/sora-2/image-to-video", "name": "Sora 2"},
        {"id": "fal-ai/sora-2/image-to-video/pro", "name": "Sora 2 Pro"},
        {"id": "veo-3.1-fast-generate-preview/i2v", "name": "Veo 3.1 Fast"},
        {"id": "veo-3.1-generate-preview/i2v", "name": "Veo 3.1"},
        {"id": "fal-ai/veo3/fast/image-to-video", "name": "Veo 3 Fast"},
        {"id": "fal-ai/veo3/image-to-video", "name": "Veo 3"},
        {"id": "fal-ai/kling-video/v3/standard/image-to-video", "name": "Kling 3.0 Standard"},
        {"id": "fal-ai/kling-video/v3/pro/image-to-video", "name": "Kling 3.0 Pro"},
        {"id": "fal-ai/kling-video/o3/standard/image-to-video", "name": "Kling o3 Standard"},
        {"id": "fal-ai/kling-video/o3/pro/image-to-video", "name": "Kling o3 Pro"},
        {"id": "fal-ai/kling-video/v2.6/pro/image-to-video", "name": "Kling 2.6 Pro"},
        {"id": "fal-ai/bytedance/seedance/v1.5/pro/image-to-video", "name": "Seedance 1.5 Pro"},
        {"id": "fal-ai/bytedance/seedance/v1/lite/image-to-video", "name": "Seedance 1.0 Lite", "note": "default"},
        {"id": "fal-ai/minimax/hailuo-2.3/pro/image-to-video", "name": "Hailuo Video 2.3 Pro"},
        {"id": "fal-ai/minimax/hailuo-02/standard/image-to-video", "name": "Hailuo Video 02"},
        {"id": "fal-ai/wan/v2.6/image-to-video", "name": "Wan 2.6"},
        {"id": "fal-ai/wan-25-preview/image-to-video", "name": "Wan 2.5"},
        {"id": "fal-ai/vidu/q3/image-to-video", "name": "Vidu Q3"},
        {"id": "gen4_turbo", "name": "Runway Gen-4"},
        {"id": "ray-2", "name": "Luma Ray 2"},
        {"id": "xai/grok-imagine-video/image-to-video", "name": "Grok Imagine Video"},
        {"id": "doubao-seedance-2-0", "name": "Seedance 2.0", "note": "comingSoon, do not use"},
    ],
    "textToVideo": [
        {"id": "fal-ai/sora-2/text-to-video", "name": "Sora 2"},
        {"id": "fal-ai/sora-2/text-to-video/pro", "name": "Sora 2 Pro"},
        {"id": "veo-3.1-fast-generate-preview", "name": "Veo 3.1 Fast"},
        {"id": "veo-3.1-generate-preview", "name": "Veo 3.1"},
        {"id": "fal-ai/veo3/fast", "name": "Veo 3 Fast"},
        {"id": "fal-ai/veo3", "name": "Veo 3"},
        {"id": "fal-ai/kling-video/o3/pro/text-to-video", "name": "Kling o3 Pro"},
        {"id": "fal-ai/kling-video/v3/pro/text-to-video", "name": "Kling 3.0 Pro"},
        {"id": "fal-ai/kling-video/v3/standard/text-to-video", "name": "Kling 3.0 Standard"},
        {"id": "fal-ai/kling-video/v2.6/pro/text-to-video", "name": "Kling 2.6 Pro"},
        {"id": "wan/v2.6/text-to-video", "name": "Wan 2.6"},
        {"id": "fal-ai/vidu/q3/text-to-video", "name": "Vidu Q3"},
        {"id": "fal-ai/minimax/hailuo-02/standard/text-to-video", "name": "Hailuo Video 02", "note": "default"},
        {"id": "fal-ai/bytedance/seedance/v1/lite/text-to-video", "name": "Seedance 1.0 Lite"},
        {"id": "fal-ai/bytedance/seedance/v1.5/pro/text-to-video", "name": "Seedance 1.5 Pro"},
        {"id": "xai/grok-imagine-video/text-to-video", "name": "Grok Imagine Video"},
        {"id": "doubao-seedance-2-0-t2v", "name": "Seedance 2.0", "note": "comingSoon, do not use"},
    ],
    "videoToVideo": [
        {"id": "fal-ai/kling-video/o3/standard/video-to-video", "name": "Kling o3 Standard", "note": "default"},
    ],
    "imageAngleControl": [
        {"id": "fal-ai/qwen-image-edit-2511-multiple-angles", "name": "Qwen Image Edit Multiple Angles", "note": "default"},
    ],
    "relight": [
        {"id": "gemini-3-pro-image-preview", "name": "Banana Pro", "note": "default"},
    ],
    "videoLipSync": [
        {"id": "fal-ai/pixverse/lipsync", "name": "Pixverse Lipsync", "note": "default"},
        {"id": "fal-ai/sync-lipsync/v2", "name": "Sync. Lipsync 2.0"},
    ],
    "describeImage": [
        {"id": "google/gemini-3-pro-preview", "name": "Gemini 3 Pro"},
        {"id": "openai/gpt-4o-2024-11-20", "name": "GPT 4o", "note": "default"},
        {"id": "openai/gpt-5-mini", "name": "GPT 5 Mini"},
        {"id": "openai/gpt-5", "name": "GPT 5"},
    ],
}

# ---------------------------------------------------------------------------
# Nodes that require selectedModels.length > 0 (frontend hard check)
# ---------------------------------------------------------------------------

REQUIRES_SELECTED_MODELS: set[str] = {
    "textGenerator",
    "imageMaker",
    "describeImage",
    "videoMaker",
    "imageToImage",
    "klingMotionControl",
    "imageAngleControl",
    "voiceCloner",
}

# ---------------------------------------------------------------------------
# Special runtime rules (common.py handles implicitly; LLM needs explicitly)
# ---------------------------------------------------------------------------

SPECIAL_RULES: dict[str, list[str]] = {
    "textGenerator": ["多模态（图/音/视频）输入须用 Gemini 系列；GPT 4o 仅支持 text+image"],
    "textToSpeech": ["必须有已选语音（modelConfigs[modelId].voice_ids 或 model_options[modelId].selected_voices）"],
    "backgroundEditor": ["model_mode='Change BG' 时 inputText 不能为空；'Remove BG' 时可无 inputText"],
    "imageToImage": ["如果自己 inputText 有效，可跳过 text 必填 Pin"],
    "imageAudioToVideo": ["如果自己 inputText 有效，可跳过 text 必填 Pin；inputText 描述表情、风格、表演方式"],
    "klingMotionControl": ["character_orientation='image' 时上游视频时长 ≤10s，否则 ≤30s"],
    "videoMaker": ["图生视频与文生视频的模型 ID 不同，不可混用"],
    "textToVideo": ["文生视频与图生视频的模型 ID 不同，不可混用"],
}

# ---------------------------------------------------------------------------
# Connection limits per pin (common.py does not have this)
# ---------------------------------------------------------------------------

CONNECTION_LIMITS: dict[str, dict[str, int]] = {
    "scriptSplit": {"text": 1},
    "imageUpscaler": {"image": 1},
    "backgroundEditor": {"image": 1},
    "relight": {"image": 1},
    "imageAngleControl": {"image": 1},
    "videoUpscaler": {"video": 1},
    "videoToVideo": {"video": 1},
    "klingMotionControl": {"image": 1, "video": 1},
    "videoMaker": {"image": 4},
    "videoLipSync": {"video": 1, "audio": 1},
    "imageAudioToVideo": {"image": 1, "audio": 1},
}

# ---------------------------------------------------------------------------
# Node category mapping (for auto-attaching prompt guides)
# ---------------------------------------------------------------------------

NODE_CATEGORIES: dict[str, str] = {
    "textGenerator": "text",
    "scriptSplit": "text",
    "imageMaker": "image",
    "imageToImage": "image",
    "relight": "image",
    "imageAngleControl": "image",
    "imageUpscaler": "image",
    "backgroundEditor": "image",
    "textToVideo": "video",
    "videoMaker": "video",
    "videoToVideo": "video",
    "klingMotionControl": "video",
    "videoLipSync": "video",
    "imageAudioToVideo": "video",
    "videoUpscaler": "video",
    "textToSpeech": "audio",
    "musicGenerator": "audio",
    "voiceCloner": "audio",
}

# ---------------------------------------------------------------------------
# Prompt writing guides (per category)
# ---------------------------------------------------------------------------

PROMPT_GUIDES: dict[str, str] = {
    "text": """\
## Text Prompt Guide

### 输出格式要求
- 只输出结果，不输出解释、推理、过渡语
- 编号分块：每块对应一个执行目标，单块 ≤1500 中文字符
- 一块一目标：一个图像描述=一张图，一个镜头描述=一个镜头
- 块内自洽：每块可独立使用，不写「同上」

### 角色设定模板
```
你是 [具体角色]。任务是 [具体任务]。直接输出 [格式]。不解释、不赘述。每块不超过 1500 字。
```

常用角色：
- 多图集：「你是专业亚马逊 listing 视觉设计师。任务是生成编号多图描述集。每图标为 Image 01、Image 02…」
- 分镜：「你是专业分镜师与商业片视觉策划。任务是生成编号分镜。每镜标为 Shot 01、Shot 02…」
- 口播脚本：「你是广告脚本分析师与短视频策略师。任务是分析参考视频并输出结构化脚本。」

### 编号格式
使用稳定编号：`Image 01`、`Shot 01`、`Scene 01`。若下游接 scriptSplit，严格按编号拆分。""",

    "image": """\
## Image Prompt Guide

### 结构模板
```
[构图/景别]，[相机与镜头]，[光影与氛围]，[视觉效果/质感]，[风格/渲染]，[画质/比例]
```

示例（写实）：
「三分法构图，35mm 镜头浅景深，柔和自然光黄金时刻，胶片颗粒与尘埃质感，电影感写实，2K 16:9」

### 预设词库
- **构图**：rule of thirds, eye-level shot, close-up, medium shot, wide shot, candid moment
- **镜头**：35mm lens, 50mm lens, 85mm portrait lens, shallow depth of field, macro lens, DSLR
- **光影**：soft natural daylight, golden hour sunlight, high-contrast cinematic lighting, studio softboxes, backlit silhouette, low-key moody lighting
- **质感**：photorealistic texture, film grain, dust particles, lens flare, bokeh
- **风格**：photorealistic, cinematic film look, fashion editorial, anime style, minimalist, UGC handheld style""",

    "video": """\
## Video Prompt Guide

### 结构模板
```
[相机与镜头]，[运动/物理]，[光影与氛围]，[视觉效果]，[风格/渲染]
```

一镜头=一个主动作+一个机位+一种光影。示例：
「slow push-in, 35mm lens, leans forward slightly, golden hour lighting with soft shadows, dust particles in sunlight, cinematic film look」

### 预设词库
- **机位**：slow push-in, slow pull-out, pan left, pan right, tracking shot, static shot, close-up, medium shot, wide shot, low angle, eye-level
- **镜头**：16mm/35mm/50mm/85mm lens, shallow depth of field
- **运动**：leans forward slightly, hair moves with wind, fabric reacts to motion, hand gestures emphasize speech
- **光影**：soft natural daylight, golden hour light, high contrast cinematic lighting, neon lighting, diffused studio lighting
- **风格**：cinematic film look, photorealistic, UGC handheld style, fashion editorial, film grain

多镜头可按时段分镜：`[00:00–00:03] Hook`、`[00:03–00:06] Build`、`[00:06–00:09] Peak`、`[00:09–00:12] Resolution`""",
}

# ---------------------------------------------------------------------------
# Workflow structure pattern templates
# ---------------------------------------------------------------------------

WORKFLOW_PATTERNS: dict[str, str] = {
    "ugc-ad": """\
## Pattern: UGC 口播广告（共享语义层 + 图生口播）

**输入**：产品图(image)、产品 URL/信息(text)、目标人群(text)

**节点与连线**：
- A `textGenerator`：输入 product_url + target_audience → 输出 product_brief（痛点/卖点/情绪）
- B `textGenerator`：输入 product_brief + product_image + target_audience → 输出 ugc_image_prompt
- C `textGenerator`：输入 product_brief + target_audience → 输出 script
- D `imageMaker` 或 `imageToImage`：输入 product_image + ugc_image_prompt → 输出 character_image
- E `textToSpeech`：输入 script → 输出 audio
- F `imageAudioToVideo`：输入 character_image + audio + script → 输出 final_video

**依赖**：B、C 依赖 A；D 依赖 B；E 依赖 C；F 依赖 D、E

**推荐模型组合**：
| 风格 | 生图 | TTS |
|------|------|-----|
| 写实 UGC | Banana Pro | Fish Audio |
| 风格化 | Seedream 5.0 Lite | Fish Audio |
| 快速出片 | Hailuo Image 01 | Fish Audio |""",

    "video-lipsync": """\
## Pattern: 视频对口型（图→视频→对口型）

适用：需要人物动起来、有镜头语言的场景

**输入**：达人画像描述(text)、产品图(image)、落地页(text)

**节点与连线**：
- A `textGenerator`：产品亮点提取 → product_brief
- B `textGenerator`：UGC 视觉描述 → ugc_image_prompt（输入 A + 图 + 描述）
- C `textGenerator`：口播脚本 → script（输入 A）
- D `imageMaker`/`imageToImage`：输入 图 + B 输出 → influencer_image
- E `textToSpeech`：输入 C 输出 → voice_audio
- F `videoMaker`：输入 D 输出 + 可选 motion 文本 → base_video
- G `videoLipSync`：输入 F 输出 + E 输出 → final_lip_sync_video

**依赖**：B、C 依赖 A；D 依赖 B；E 依赖 C；F 依赖 D；G 依赖 F、E

**推荐模型组合**：
| 生图 | 图生视频 | TTS |
|------|----------|-----|
| Banana Pro | Seedance 1.5 Pro 或 Sora 2 | Fish Audio |""",

    "image-lipsync": """\
## Pattern: 图生对口型（图+音频直出）

**输入**：同视频对口型，但不需要中间视频

**节点**：
- A `textGenerator`：分析 → product_brief
- B `textGenerator`：描述 → ugc_image_prompt
- C `textGenerator`：脚本 → script
- D `imageMaker`/`imageToImage`：图 + B → character_image
- E `textToSpeech`：C → audio
- F `imageAudioToVideo`：D 的图 + E 的音频 + 台词 → final_video

无 videoMaker、无 videoLipSync。

**依赖**：B、C 依赖 A；D 依赖 B；E 依赖 C；F 依赖 D、E

**推荐模型组合**：同 UGC 口播广告（无需图生视频环节）""",

    "multi-image": """\
## Pattern: 组图（亚马逊风多图）

**输入**：产品图(image)、产品描述(text)

**节点与连线**：
- A `textGenerator`：角色「亚马逊 listing 视觉设计师」，输出编号多图描述（Image 01、Image 02…），每块一图、自洽
- B `scriptSplit`：输入 A 输出，按编号拆成单条
- C 多个 `imageMaker`：每条 B 输出对应一张图；可共用同一 selectedModels，每条 prompt 独立

**依赖**：B 依赖 A；各 C 依赖 B 对应条

**推荐模型**：生图用 Banana Pro 或 GPT Image 1.5""",
}

# ---------------------------------------------------------------------------
# Node/Edge construction guide (appended to every get_node_spec output)
# ---------------------------------------------------------------------------

CONSTRUCTION_GUIDE = """\
## Node JSON 模板

```json
{
  "id": "{nodeType}-{timestamp}-{nanoid(6)}",
  "type": "textGenerator",
  "position": { "x": 500, "y": 100 },
  "selected": false,
  "data": {
    "label": "Text Generator",
    "description": "Generate high-quality text",
    "themeColor": "#04FE06",
    "modelCardColor": "#04FE06",
    "selectedModels": ["openai/gpt-4o-mini"],
    "inputText": "",
    "imageBase64": "",
    "inputAudio": "",
    "inputVideo": "",
    "status": "idle",
    "isSelectMode": false,
    "workflowId": "<当前workflowId>",
    "model_options": { "attachments": [] }
  }
}
```

## Edge JSON 模板

```json
{
  "id": "customEdge-{sourceId}-{targetId}-{sourceHandle}-{targetHandle}",
  "source": "textInput-1",
  "target": "imageMaker-1",
  "sourceHandle": "text",
  "targetHandle": "text",
  "type": "customEdge"
}
```

## 禁写字段

不要写入以下前端派生字段：`isNodeConnected`, `isTextPinConnected`, `isImagePinConnected`, `estimatedTime`, `local_file`

## 输入节点有效性条件

- textInput: inputText 去除 HTML 标签后仍有非空文本
- imageInput: imageBase64 非空
- audioInput: inputAudio 非空
- videoInput: inputVideo 非空（额外字段：inputVideoPoster 封面, inputVideoDuration 时长毫秒）

## groupNode 默认字段（仅在用户明确要求分组时使用，不要主动创建）

label, inputHint, backgroundColor（不可执行，仅视觉容器，position 使用绝对坐标）
"""
