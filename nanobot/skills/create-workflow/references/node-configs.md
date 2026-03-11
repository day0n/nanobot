# OpenCreator Create-Workflow 参考（2026-03）

本文件用于 `create-workflow` skill 生成标准 `nodes/edges`。

## 1) 节点白名单（创建时优先）

### Input
- `textInput`
- `imageInput`
- `videoInput`
- `audioInput`

### Text
- `textGenerator`
- `scriptSplit`

### Image
- `imageMaker`
- `imageToImage`
- `relight`
- `imageAngleControl`
- `imageUpscaler`
- `backgroundEditor`

### Video
- `textToVideo`
- `videoMaker`
- `videoToVideo`
- `klingMotionControl`
- `videoLipSync`
- `imageAudioToVideo`
- `videoUpscaler`

### Audio
- `textToSpeech`
- `musicGenerator`
- `voiceCloner`

### Handy
- `assembleNow`
- `stickyNodesNode`

### 兼容旧流（新建不推荐）
- `describeImage`
- `oneClickStyle`
- `syncVideoAudio`

## 2) 句柄映射（Pin）

- `textInput`: out `text`
- `imageInput`: out `image`
- `videoInput`: out `video`
- `audioInput`: out `audio`
- `textGenerator`: in `text,image,video,audio`; out `text`
- `scriptSplit`: in `text`; out `text`
- `imageMaker`: in `text`; out `image`
- `imageToImage`: in `image,text`; out `image`
- `relight`: in `image`; out `image`
- `imageAngleControl`: in `image`; out `image`
- `imageUpscaler`: in `image`; out `image`
- `backgroundEditor`: in `image,text`; out `image`
- `textToVideo`: in `text`; out `video`
- `videoMaker`: in `image,text`; out `video`
- `videoToVideo`: in `video,text,subject,style`; out `video`
- `klingMotionControl`: in `image,video,text`; out `video`
- `videoLipSync`: in `video,audio`; out `video`
- `imageAudioToVideo`: in `image,audio,text`; out `video`
- `videoUpscaler`: in `video`; out `video`
- `textToSpeech`: in `text`; out `audio`
- `voiceCloner`: in `audio,text`; out `audio`
- `musicGenerator`: in `text`; out `audio`

连线规则：
- `text->text`
- `image->image`
- `video->video`
- `audio->audio`
- `subject/style` 输入按 `image` 兼容处理

## 3) 常见连接上限

- `scriptSplit.text = 1`
- `imageUpscaler.image = 1`
- `backgroundEditor.image = 1`
- `relight.image = 1`
- `imageAngleControl.image = 1`
- `videoUpscaler.video = 1`
- `videoToVideo.video = 1`
- `klingMotionControl.image = 1, video = 1`
- `videoMaker.image <= 4`
- `videoLipSync.video = 1, audio = 1`
- `imageAudioToVideo.image = 1, audio = 1`

## 4) 默认模型（关键节点）

- `textGenerator`: `openai/gpt-4o-mini`
- `scriptSplit`: `openai/gpt-5.2`
- `imageMaker`: `minimax/hailuo-image-01`
- `imageToImage`: `fal-ai/gemini-flash-edit/multi`
- `relight`: `gemini-3-pro-image-preview`
- `imageAngleControl`: `fal-ai/qwen-image-edit-2511-multiple-angles`
- `textToVideo`: `fal-ai/minimax/hailuo-02/standard/text-to-video`
- `videoMaker`: `fal-ai/bytedance/seedance/v1/lite/image-to-video`
- `videoToVideo`: `fal-ai/kling-video/o3/standard/video-to-video`
- `klingMotionControl`: `fal-ai/kling-video/v2.6/standard/motion-control`
- `videoLipSync`: `fal-ai/pixverse/lipsync`
- `imageAudioToVideo`: `fal-ai/infinitalk`
- `videoUpscaler`: `fal-ai/topaz/upscale/video`
- `textToSpeech`: `fish-audio/speech-1.6`
- `voiceCloner`: `fal-ai/qwen-3-tts/clone-voice/1.7b`

## 5) data 最小结构（执行节点）

```json
{
  "label": "Node Name",
  "description": "Node Description",
  "themeColor": "#73ADFF",
  "modelCardColor": "#73ADFF",
  "selectedModels": ["model-id"],
  "inputText": "",
  "imageBase64": "",
  "inputAudio": "",
  "inputVideo": "",
  "status": "idle",
  "isSelectMode": false,
  "isNodeConnected": false
}
```

输入节点要求：
- `selectedModels` 必须是 `[]`

建议附加字段（按节点）：
- `textGenerator` / `scriptSplit`：`model_options.attachments=[]`
- `backgroundEditor`：`model_options.model_mode="Change BG"`
- `videoLipSync`：`model_options.loop_mode="Cut-off"`
- `imageUpscaler`：`model_options.upscale_factor="2"`
- `videoUpscaler`：`model_options.upscale_factor="2"`, `frames_per_second=24`
- `musicGenerator`：`model_options.make_instrumental=false`
- `videoToVideo`：`model_options.node_mode="edit-short"`, `duration=5`, `keep_audio=true`

## 6) Node/Edge 模板

### Node
```json
{
  "id": "textGenerator-1710000000000-a1b2c3",
  "type": "textGenerator",
  "position": { "x": 500, "y": 100 },
  "selected": false,
  "data": {
    "label": "Text Generator",
    "description": "Generate high-quality text",
    "themeColor": "#9DFF9E",
    "modelCardColor": "#9DFF9E",
    "selectedModels": ["openai/gpt-4o-mini"],
    "inputText": "",
    "imageBase64": "",
    "inputAudio": "",
    "inputVideo": "",
    "status": "idle",
    "isSelectMode": false,
    "isNodeConnected": false,
    "model_options": { "attachments": [] }
  }
}
```

### Edge
```json
{
  "id": "edge-textInput-1-imageMaker-1-text-text",
  "source": "textInput-1",
  "target": "imageMaker-1",
  "sourceHandle": "text",
  "targetHandle": "text",
  "type": "customEdge",
  "animated": true
}
```

## 7) 布局建议（DAG）

- `x = 100 + layer * 400`
- `y = 100 + indexInLayer * 300`
- `layer` 从输入节点开始向右递增
