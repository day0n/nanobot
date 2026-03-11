---
name: create-workflow
description: 通过自然语言描述创建 OpenCreator 工作流，自动生成节点、连线、布局，然后调用 create_workflow 工具保存到指定用户账户
---

# 创建 OpenCreator 工作流

当用户要求创建工作流时，按以下步骤操作：

## Step 1: 确认必填信息

必须确认：
- **user_email** — 工作流归属用户的邮箱
- **workflow_name** — 工作流名称（可根据描述自动生成）

如果用户未提供邮箱，先询问。

## Step 2: 设计工作流结构

根据用户描述，确定：
1. 需要哪些节点类型（见下方节点速查表）
2. 节点间的数据流向（哪个输出 pin 连到哪个输入 pin）
3. 是否有并行分支

**常用工作流模板：**
- 文生图：`textInput → imageMaker`
- 文生视频：`textInput → textToVideo`
- 图生视频：`textInput → imageMaker → videoMaker`
- 完整内容：`textInput → textGenerator → imageMaker → videoMaker`（分支 `→ textToSpeech`）
- 分镜视频：`textInput → textGenerator → scriptSplit → imageMaker → videoMaker`

## Step 3: 生成 nodes 数组

节点结构：
```json
{
  "id": "{nodeType}-{13位时间戳}-{4位随机hex}",
  "type": "{nodeType}",
  "position": { "x": 0, "y": 0 },
  "selected": false,
  "data": {
    "label": "节点显示名称",
    "description": "节点描述",
    "themeColor": "#颜色",
    "selectedModels": ["模型ID"],
    "inputText": "prompt内容",
    "imageBase64": "",
    "inputAudio": "",
    "inputVideo": "",
    "status": "idle",
    "isSelectMode": false,
    "isNodeConnected": false
  }
}
```

**节点 ID 规则：** `{nodeType}-{13位时间戳}-{4位hex}`，每个节点时间戳+1

### 节点速查表

| 类型 | 显示名 | 输入 Pin | 输出 Pin | 默认模型 | themeColor |
|------|--------|---------|---------|---------|-----------|
| `textInput` | Text Input | — | text | — | `#484848` |
| `imageInput` | Image Input | — | image | — | `#000000` |
| `videoInput` | Video Input | — | video | — | `#000000` |
| `audioInput` | Audio Input | — | audio | — | `#000000` |
| `textGenerator` | Text Generator | text(必), image, video, audio | text | `openai/gpt-4o-mini` | `rgba(4, 254, 6, 1)` |
| `scriptSplit` | Text Splitter | text(必) | text | `openai/gpt-4o-2024-11-20` | `rgba(4, 254, 6, 1)` |
| `describeImage` | Image Describer | image(必) | text | `openai/gpt-4o-2024-11-20` | `#217EFF` |
| `imageMaker` | Image Generator | text(必) | image | `fal-ai/flux-pro/v1.1` | `#217EFF` |
| `imageToImage` | Image to Image | image(必), text(必) | image | `GPT Image 1` | `#217EFF` |
| `imageUpscaler` | Image Upscaler | image(必) | image | — | `#217EFF` |
| `textToVideo` | Text to Video | text(必) | video | `fal-ai/minimax/hailuo-02/standard/text-to-video` | `#F662CC` |
| `videoMaker` | Image to Video | image(必), text | video | `fal-ai/bytedance/seedance/v1/lite/image-to-video` | `#F662CC` |
| `syncVideoAudio` | Add Sound to Video | video(必), text | video | — | `#F662CC` |
| `videoUpscaler` | Video Upscaler | video(必) | video | — | `#F662CC` |
| `textToSpeech` | Text to Speech | text(必) | audio | `fish-audio/speech-1.6` | `#EAD701` |
| `musicGenerator` | Music Generator | text(必) | audio | — | `#EAD701` |

- 输入节点 `selectedModels` 为空数组 `[]`
- 结果型节点同时需要 `"modelCardColor"` 字段（值同 `themeColor`）

### inputText 填写规则

| 节点 | 是否必填 | 内容 |
|------|---------|------|
| `textInput` | **必填** | 预填场景示例内容（故事梗概、产品描述等） |
| `textGenerator` | **必填** | 具体的 LLM 指令 prompt |
| `scriptSplit` | **必填** | 拆分指令 |
| `imageMaker` | 有上游 text 时选填 | 无上游时必填完整 prompt；有上游时填风格补充（如 `anime style, 4k`） |
| `textToVideo` | 有上游 text 时选填 | 同上 |
| `videoMaker` | 选填 | 运镜/补充描述 |
| `textToSpeech` | 有上游 text 时选填 | 无上游时必填朗读文本 |
| `imageToImage` | **必填** | 图片编辑指令 |
| `describeImage` / `imageUpscaler` / `videoUpscaler` | 不填 | 上游自动处理 |

图片/视频生成类 prompt 建议用英文（效果更好）；文本生成类 prompt 跟随用户语言。

## Step 4: 生成 edges 数组

```json
{
  "id": "edge-{sourceId}-{targetId}",
  "source": "{sourceNodeId}",
  "target": "{targetNodeId}",
  "sourceHandle": "{输出pinID}",
  "targetHandle": "{输入pinID}",
  "type": "customEdge",
  "animated": true
}
```

**Pin 类型必须相同：** text→text ✓, image→image ✓, text→image ✗

## Step 5: 计算节点位置（DAG 布局）

1. 计算每个节点的 DAG 层级（入度为 0 → 第 0 层）
2. `x = 100 + layer × 400`
3. `y = 100 + indexInLayer × 300`

## Step 6: 调用工具保存

生成完整的 nodes 和 edges 后，调用 `create_workflow` 工具：
- `user_email`: 用户邮箱
- `workflow_name`: 工作流名称
- `nodes`: 完整节点数组
- `edges`: 完整连线数组

工具返回 flow_id 和编辑器 URL。

---

详细节点配置参考（含完整模型列表）可通过 read_file 工具读取：
`{skill_dir}/references/node-configs.md`
