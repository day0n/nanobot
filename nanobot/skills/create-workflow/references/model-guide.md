# 节点级模型 ID 与参数（构建用）

本文件供 **create-workflow** 构建工作流时使用：需要为节点填写 `selectedModels`、`modelConfigs`、`model_options` 时查阅。**按节点类型（node.type）组织**；同一可读名称在不同节点下对应不同 API ID，必须以本表为准。

数据来源：`docs/dylan/模型映射.md`。未列出的节点类型（如 textToSpeech、videoUpscaler、backgroundEditor 等）使用 `node-configs.md` 中的默认模型与参数。

---

## 1. textGenerator

可选 `selectedModels`（任选其一或组合，需 `selectedModels.length > 0`）：

| API ID | 可读名称 |
|--------|----------|
| `google/gemini-3-pro-preview` | Gemini 3 Pro |
| `google/gemini-3-flash-preview` | Gemini 3 Flash |
| `google/gemini-2.0-flash` | Gemini 2.0 Flash |
| `openai/gpt-5.2-pro` | GPT 5.2 Pro |
| `openai/gpt-5.2` | GPT 5.2 |
| `openai/gpt-5` | GPT 5 |
| `openai/gpt-4o-2024-11-20` | GPT 4o |
| `openai/gpt-4o-mini` | GPT 4o Mini |

默认（node-configs）：`["openai/gpt-4o-mini"]`。多模态（图/音/视频）输入须用 Gemini 系列；GPT 4o 仅支持 text+image。

`model_options` 常用：`{ "attachments": [] }`。

---

## 2. scriptSplit

与 textGenerator 共用 text 类模型，默认推荐：`["openai/gpt-5.2"]`。`model_options`：`{ "attachments": [] }`。

---

## 3. imageMaker

可选 `selectedModels`（必填，需 `selectedModels.length > 0`）：

| API ID | 可读名称 | 备注 |
|--------|----------|------|
| `gemini-3-pro-image-preview` | Banana Pro | 写实、高分辨率 |
| `fal-ai/nano-banana` | Nano Banana | |
| `fal-ai/gemini-3.1-flash-image-preview` | Nano Banana 2 | |
| `fal-ai/imagen4/preview` | Imagen 4 | |
| `fal-ai/gpt-image-1.5` | GPT Image 1.5 | |
| `openai/gpt-image-1` | GPT Image 1 | |
| `xai/grok-imagine-image` | Grok Imagine | |
| `fal-ai/flux-2-pro` | Flux 2 Pro | |
| `fal-ai/flux-pro/v1.1` | Flux 1.1 Pro | |
| `fal-ai/bytedance/seedream/v5/lite/text-to-image` | Seedream 5.0 Lite | |
| `fal-ai/bytedance/seedream/v4.5/text-to-image` | Seedream 4.5 | |
| `fal-ai/bytedance/seedream/v4/text-to-image` | Seedream 4.0 | |
| `minimax/hailuo-image-01` | Hailuo Image 01 | 默认 |
| `fal-ai/fast-sdxl` | SDXL Fast | |

不推荐（comingSoon）：`fal-ai/bytedance/seedream/v5/text-to-image`（Seedream 5.0）。

附加字段：`lensStyleEnabled`: false，`lensStyle.*`: `"none"`。

---

## 4. videoMaker（图生视频）

**注意**：图生视频与文生视频的模型 ID 不同，不可混用。

可选 `selectedModels`（必填）：

| API ID | 可读名称 |
|--------|----------|
| `fal-ai/sora-2/image-to-video` | Sora 2 |
| `fal-ai/sora-2/image-to-video/pro` | Sora 2 Pro |
| `veo-3.1-fast-generate-preview/i2v` | Veo 3.1 Fast |
| `veo-3.1-generate-preview/i2v` | Veo 3.1 |
| `fal-ai/veo3/fast/image-to-video` | Veo 3 Fast |
| `fal-ai/veo3/image-to-video` | Veo 3 |
| `fal-ai/kling-video/v3/standard/image-to-video` | Kling 3.0 Standard |
| `fal-ai/kling-video/v3/pro/image-to-video` | Kling 3.0 Pro |
| `fal-ai/kling-video/o3/standard/image-to-video` | Kling o3 Standard |
| `fal-ai/kling-video/o3/pro/image-to-video` | Kling o3 Pro |
| `fal-ai/kling-video/v2.6/pro/image-to-video` | Kling 2.6 Pro |
| `fal-ai/bytedance/seedance/v1.5/pro/image-to-video` | Seedance 1.5 Pro |
| `fal-ai/bytedance/seedance/v1/lite/image-to-video` | Seedance 1.0 Lite |
| `fal-ai/minimax/hailuo-2.3/pro/image-to-video` | Hailuo Video 2.3 Pro |
| `fal-ai/minimax/hailuo-02/standard/image-to-video` | Hailuo Video 02 |
| `fal-ai/wan/v2.6/image-to-video` | Wan 2.6 |
| `fal-ai/wan-25-preview/image-to-video` | Wan 2.5 |
| `fal-ai/vidu/q3/image-to-video` | Vidu Q3 |
| `gen4_turbo` | Runway Gen-4 |
| `ray-2` | Luma Ray 2 |
| `xai/grok-imagine-video/image-to-video` | Grok Imagine Video |

不推荐（comingSoon）：`doubao-seedance-2-0`（Seedance 2.0）。默认：`["fal-ai/bytedance/seedance/v1/lite/image-to-video"]`。

---

## 5. textToVideo（文生视频）

**注意**：文生视频与图生视频的模型 ID 不同。

可选 `selectedModels`：

| API ID | 可读名称 |
|--------|----------|
| `fal-ai/sora-2/text-to-video` | Sora 2 |
| `fal-ai/sora-2/text-to-video/pro` | Sora 2 Pro |
| `veo-3.1-fast-generate-preview` | Veo 3.1 Fast |
| `veo-3.1-generate-preview` | Veo 3.1 |
| `fal-ai/veo3/fast` | Veo 3 Fast |
| `fal-ai/veo3` | Veo 3 |
| `fal-ai/kling-video/o3/pro/text-to-video` | Kling o3 Pro |
| `fal-ai/kling-video/v3/pro/text-to-video` | Kling 3.0 Pro |
| `fal-ai/kling-video/v3/standard/text-to-video` | Kling 3.0 Standard |
| `fal-ai/kling-video/v2.6/pro/text-to-video` | Kling 2.6 Pro |
| `wan/v2.6/text-to-video` | Wan 2.6 |
| `fal-ai/vidu/q3/text-to-video` | Vidu Q3 |
| `fal-ai/minimax/hailuo-02/standard/text-to-video` | Hailuo Video 02 |
| `fal-ai/bytedance/seedance/v1/lite/text-to-video` | Seedance 1.0 Lite |
| `fal-ai/bytedance/seedance/v1.5/pro/text-to-video` | Seedance 1.5 Pro |
| `xai/grok-imagine-video/text-to-video` | Grok Imagine Video |

不推荐：`doubao-seedance-2-0-t2v`（Seedance 2.0，comingSoon）。默认：`["fal-ai/minimax/hailuo-02/standard/text-to-video"]`。

---

## 6. imageToImage

可选 `selectedModels`（必填）：

| API ID | 可读名称 |
|--------|----------|
| `gemini-3-pro-image-preview` | Banana Pro |
| `fal-ai/nano-banana/edit` | Nano Banana |
| `fal-ai/gemini-3.1-flash-image-preview/edit` | Nano Banana 2 |
| `fal-ai/gpt-image-1.5/edit` | GPT Image 1.5 |
| `openai/gpt-image-1` | GPT Image 1 |
| `fal-ai/flux-pro/kontext/multi` | Flux Kontext |
| `fal-ai/flux-2-pro/edit` | Flux 2 Pro |
| `fal-ai/gemini-flash-edit/multi` | Gemini 2.0 Flash |
| `fal-ai/qwen-image-edit-plus` | Qwen Image Edit |
| `fal-ai/bytedance/seedream/v5/lite/edit` | Seedream 5.0 Lite |
| `fal-ai/bytedance/seedream/v4.5/edit` | Seedream 4.5 |
| `fal-ai/bytedance/seedream/v4/edit` | Seedream 4.0 |
| `xai/grok-imagine-image/edit` | Grok Imagine |

不推荐：`fal-ai/bytedance/seedream/v5/edit`（Seedream 5.0，comingSoon）。默认：`["fal-ai/gemini-flash-edit/multi"]`。若节点自带 `inputText` 有效，text 必填 Pin 可视为已满足。

---

## 7. describeImage（兼容旧流，新建不推荐）

可选：`google/gemini-3-pro-preview`（Gemini 3 Pro）、`openai/gpt-4o-2024-11-20`（GPT 4o）、`openai/gpt-5-mini`、`openai/gpt-5`。需 `selectedModels.length > 0`。

---

## 8. imageAngleControl

仅支持：`fal-ai/qwen-image-edit-2511-multiple-angles`（Qwen Image Edit Multiple Angles）。必填 `selectedModels`。

推荐 `modelConfigs`：

```json
{
  "fal-ai/qwen-image-edit-2511-multiple-angles": {
    "horizontal_angle": 0,
    "vertical_angle": 0,
    "zoom": 5,
    "lora_scale": 1
  }
}
```

---

## 9. videoLipSync

可选：`fal-ai/pixverse/lipsync`（Pixverse Lipsync）、`fal-ai/sync-lipsync/v2`（Sync. Lipsync 2.0）。默认：`["fal-ai/pixverse/lipsync"]`。`model_options`：`{ "loop_mode": "Cut-off" }`。

---

## 10. relight

仅支持：`gemini-3-pro-image-preview`（Banana Pro）。默认：`["gemini-3-pro-image-preview"]`。

推荐 `modelConfigs`（与 node-configs 对齐，字段名以实际节点为准）：

```json
{
  "gemini-3-pro-image-preview": {
    "light_x": 45,
    "light_y": 30,
    "light_color": "#fffbe6",
    "light_brightness": 70,
    "light_temperature": 5000,
    "light_quality": "product_studio",
    "aspect_ratio": "16:9"
  }
}
```

---

## 11. 无独立模型选择器的节点（用 node-configs 默认值）

以下节点在映射中无单独模型列表，构建时使用 `node-configs.md` 的默认 `selectedModels` / `model_options` / `modelConfigs` 即可：

- **imageUpscaler**：`model_options`: `{ "upscale_factor": "2" }`（允许 `"2"`/`"4"`/`"6"`）
- **backgroundEditor**：`model_options`: `{ "model_mode": "Change BG" }`；Change BG 时 `inputText` 必填
- **videoToVideo**：默认 `["fal-ai/kling-video/o3/standard/video-to-video"]`，`model_options`: `{ "node_mode": "edit-short", "duration": 5, "keep_audio": true }`
- **videoUpscaler**：默认 `["fal-ai/topaz/upscale/video"]`，`model_options`: `{ "upscale_factor": "2", "frames_per_second": 24 }`
- **klingMotionControl**：默认 `["fal-ai/kling-video/v2.6/standard/motion-control"]`，`modelConfigs` 见 node-configs；`character_orientation === "image"` 时视频时长 ≤10s
- **textToSpeech**：默认 `["fish-audio/speech-1.6"]`，须设 `voice_ids` 或 `selected_voices`
- **musicGenerator**：默认 `selectedModels`: `[]`，`model_options`: `{ "make_instrumental": false }`
- **voiceCloner**：默认 `["fal-ai/qwen-3-tts/clone-voice/1.7b"]`，需 `selectedModels.length > 0`
- **imageAudioToVideo**：默认 `["fal-ai/infinitalk"]`；若节点 `inputText` 有效，text 必填 Pin 可视为已满足

---

## 12. 强制 selectedModels 校验的节点

以下节点前端会强制 `selectedModels.length > 0`，构建时必须填写至少一个有效 API ID：  
textGenerator、imageMaker、describeImage、videoMaker、imageToImage、klingMotionControl、imageAngleControl、voiceCloner。

---

## 13. 同步规则

- 修改 `selectedModels` 时，须同步维护 `modelConfigs` 中对应 modelId 的配置，避免缺键导致运行异常。
- 输入节点 `selectedModels` 必须为 `[]`。
