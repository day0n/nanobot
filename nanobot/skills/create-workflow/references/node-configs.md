# 节点配置速查表

## 节点类型总览

### 输入节点（4种）

| 节点类型 | 显示名称 | 输入 Pins | 输出 Pins | 默认模型 | themeColor |
|---------|---------|-----------|-----------|---------|------------|
| `textInput` | Text Input | — | text | — | `#484848` |
| `imageInput` | Image Input | — | image | — | `#000000` |
| `videoInput` | Video Input | — | video | — | `#000000` |
| `audioInput` | Audio Input | — | audio | — | `#000000` |

### 文本节点（3种）

| 节点类型 | 显示名称 | 输入 Pins | 输出 Pins | 默认模型 | themeColor |
|---------|---------|-----------|-----------|---------|------------|
| `textGenerator` | Text Generator | text(必), image, video, audio | text | `openai/gpt-4o-mini` | `rgba(4, 254, 6, 1)` |
| `scriptSplit` | Text Splitter | text(必) | text | `openai/gpt-4o-2024-11-20` | `rgba(4, 254, 6, 1)` |
| `describeImage` | Image Describer | image(必) | text | `openai/gpt-4o-2024-11-20` | `#217EFF` |

### 图像节点（7种）

| 节点类型 | 显示名称 | 输入 Pins | 输出 Pins | 默认模型 | themeColor |
|---------|---------|-----------|-----------|---------|------------|
| `imageMaker` | Image Generator | text(必) | image | `fal-ai/flux-pro/v1.1` | `#217EFF` |
| `imageToImage` | Image to Image | image(必), text(必) | image | `GPT Image 1` | `#217EFF` |
| `oneClickStyle` | Style Image Generator | text(必) | image | `LA Sunshine` | `#217EFF` |
| `imageUpscaler` | Image Upscaler | image(必) | image | — (无需选模型) | `#217EFF` |
| `backgroundEditor` | Background Editor | image(必), text | image | — | `#217EFF` |
| `relight` | Relight | image(必) | image | `gemini-3-pro-image-preview` | `#217EFF` |
| `imageAngleControl` | Image Angle Control | image(必) | image | `fal-ai/qwen-image-edit-2511-multiple-angles` | `#217EFF` |

### 视频节点（8种）

| 节点类型 | 显示名称 | 输入 Pins | 输出 Pins | 默认模型 | themeColor |
|---------|---------|-----------|-----------|---------|------------|
| `textToVideo` | Text to Video | text(必) | video | `fal-ai/minimax/hailuo-02/standard/text-to-video` | `#F662CC` |
| `videoMaker` | Image to Video | image(必), text | video | `fal-ai/bytedance/seedance/v1/lite/image-to-video` | `#F662CC` |
| `syncVideoAudio` | Add Sound to Video | video(必), text | video | — | `#F662CC` |
| `videoLipSync` | Lip Sync | video(必), audio(必) | video | `fal-ai/pixverse/lipsync` | `#F662CC` |
| `videoUpscaler` | Video Upscaler | video(必) | video | — (无需选模型) | `#F662CC` |
| `videoToVideo` | Video to Video | video(必), text(必), subject, style | video | — | `#F662CC` |
| `klingMotionControl` | Motion Control | image(必), video(必), text | video | — | `#F662CC` |
| `imageAudioToVideo` | Image Audio to Video | image(必), audio(必), text(必) | video | — | `#F662CC` |

### 音频节点（3种）

| 节点类型 | 显示名称 | 输入 Pins | 输出 Pins | 默认模型 | themeColor |
|---------|---------|-----------|-----------|---------|------------|
| `textToSpeech` | Text to Speech | text(必) | audio | `fish-audio/speech-1.6` | `#EAD701` |
| `voiceCloner` | Voice Cloner | audio(必), text(必) | audio | — | `#EAD701` |
| `musicGenerator` | Music Generator | text(必) | audio | — | `#EAD701` |

---

## Pin 连接规则

### 输出 Pin 类型

| 节点类别 | 输出 Pin ID | Pin 类型 |
|---------|------------|---------|
| 输入节点 / 文本生成 | `text` | text |
| 图像生成 | `image` | image |
| 视频生成 | `video` | video |
| 音频生成 | `audio` | audio |

### 连线匹配

Edge 的 `sourceHandle` 必须与 `targetHandle` **类型相同**：

- `text` → `text` ✓
- `image` → `image` ✓
- `video` → `video` ✓
- `audio` → `audio` ✓
- `text` → `image` ✗（类型不匹配）

---

## 节点数据模板（最小必填字段）

### 输入节点模板

```json
{
  "id": "textInput-1709472000000-a1b2",
  "type": "textInput",
  "position": { "x": 100, "y": 100 },
  "selected": false,
  "data": {
    "label": "Text Input",
    "description": "Put a string of text as input",
    "themeColor": "#484848",
    "selectedModels": [],
    "inputText": "在这里预填用户的初始输入内容（故事梗概、产品描述等）",
    "imageBase64": "",
    "inputAudio": "",
    "inputVideo": "",
    "status": "idle",
    "isSelectMode": false,
    "isNodeConnected": false
  }
}
```

### 文本生成节点模板（textGenerator）

```json
{
  "id": "textGenerator-1709472000001-c3d4",
  "type": "textGenerator",
  "position": { "x": 500, "y": 100 },
  "selected": false,
  "data": {
    "label": "Text Generator",
    "description": "Turn your ideas to high-quality text content",
    "themeColor": "rgba(4, 254, 6, 1)",
    "modelCardColor": "rgba(4, 254, 6, 1)",
    "selectedModels": ["openai/gpt-4o-mini"],
    "inputText": "你是一个专业文案写手。请将用户提供的内容改写为...\n\n要求：\n1. ...\n2. ...",
    "imageBase64": "",
    "inputAudio": "",
    "inputVideo": "",
    "status": "idle",
    "isSelectMode": false,
    "isNodeConnected": false,
    "isTextInput": true
  }
}
```

### 图片生成节点模板（imageMaker）

```json
{
  "id": "imageMaker-1709472000002-e5f6",
  "type": "imageMaker",
  "position": { "x": 900, "y": 100 },
  "selected": false,
  "data": {
    "label": "Image Generator",
    "description": "Turn your words into beautiful images",
    "themeColor": "#217EFF",
    "modelCardColor": "#217EFF",
    "selectedModels": ["fal-ai/flux-pro/v1.1"],
    "inputText": "如果无上游 text 连线，这里写完整的图片生成 prompt；如果有上游 text 连线，这里写风格补充（如 anime style, cinematic, 4k）",
    "imageBase64": "",
    "inputAudio": "",
    "inputVideo": "",
    "status": "idle",
    "isSelectMode": false,
    "isNodeConnected": false,
    "isImageInput": true,
    "isTextInput": true
  }
}
```

### Edge 模板

```json
{
  "id": "edge-textInput-1709472000000-a1b2-imageMaker-1709472000002-e5f6",
  "source": "textInput-1709472000000-a1b2",
  "target": "imageMaker-1709472000002-e5f6",
  "sourceHandle": "text",
  "targetHandle": "text",
  "type": "customEdge",
  "animated": true
}
```

---

## 常用模型 ID 参考

### 文本模型
| 模型 | selectedModels 值 |
|------|-----------------|
| GPT-4o | `openai/gpt-4o-2024-11-20` |
| GPT-4o Mini | `openai/gpt-4o-mini` |
| Claude 3.5 Sonnet | `anthropic/claude-3-5-sonnet-20241022` |
| Gemini 2.0 Flash | `google/gemini-2.0-flash-001` |

### 图像模型
| 模型 | selectedModels 值 |
|------|-----------------|
| Flux Pro 1.1 | `fal-ai/flux-pro/v1.1` |
| GPT Image 1 | `GPT Image 1` |
| Hailuo Image 01 | `minimax/hailuo-image-01` |

### 视频模型（文生视频）
| 模型 | selectedModels 值 |
|------|-----------------|
| Hailuo 02 | `fal-ai/minimax/hailuo-02/standard/text-to-video` |
| Veo 3 | `fal-ai/veo3/fast` |
| Wan 2.1 | `fal-ai/wan/v2.1/1.3b/text-to-video` |

### 视频模型（图生视频）
| 模型 | selectedModels 值 |
|------|-----------------|
| Seedance Lite | `fal-ai/bytedance/seedance/v1/lite/image-to-video` |
| Kling 1.6 Pro | `fal-ai/kling-video/v1.6/pro/image-to-video` |
| Runway Gen3 | `Runway Gen3` |

### 音频模型
| 模型 | selectedModels 值 |
|------|-----------------|
| Fish Audio 1.6 | `fish-audio/speech-1.6` |

---

## 布局参数

```
起始位置:  (100, 100)
列间距:    400px（水平方向，layer 之间）
行间距:    300px（垂直方向，同层节点之间）

布局方向:  从左到右（DAG 层级）
Layer 0:   入度为 0 的节点（通常是输入节点）
Layer N:   依赖 Layer 0..N-1 的节点
```

### 布局示例

```
文生图→图生视频 工作流:

Layer 0 (x=100)     Layer 1 (x=500)     Layer 2 (x=900)
┌──────────┐        ┌──────────┐        ┌──────────┐
│textInput  │──text──│imageMaker│──image──│videoMaker│
│(100, 100) │        │(500, 100)│        │(900, 100)│
└──────────┘        └──────────┘        └──────────┘

并行分支 工作流:

Layer 0 (x=100)     Layer 1 (x=500)
┌──────────┐        ┌──────────┐
│textInput  │──text──│imageMaker│
│(100, 100) │   │    │(500, 100)│
└──────────┘   │    └──────────┘
               │    ┌──────────────┐
               └text│textToSpeech  │
                    │(500, 400)    │
                    └──────────────┘
```
