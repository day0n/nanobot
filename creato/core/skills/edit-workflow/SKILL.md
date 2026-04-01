---
name: edit-workflow
description: 在当前画布中编辑 OpenCreator 工作流
trigger: Before calling edit_workflow tool
---

# 编辑 OpenCreator 工作流

当用户在画布聊天中要求修改工作流时，使用本 skill。
如果用户只是问建议或询问节点用法，不要直接调用 `edit_workflow`。
工具会自动从当前画布会话获取 `user_id` 和 `flow_id`，不需要手动传入。

## 强约束

1. 仅使用下方节点目录中的节点。不使用废弃节点。
2. `node.type` 是节点类型的唯一可信来源。
3. 每个节点必须有 `position: {x, y}`（有限数字，绝对坐标）。
4. 连线只允许类型兼容的 Pin。
5. 所有 edge 的 source/target 必须存在于 nodes，不允许重复 node id。
6. 工作流保持 DAG（不要闭环）。
7. 执行节点必须有合法 `selectedModels`（输入节点除外）。
8. 删除节点时必须级联删除关联边。
9. 替换 `selectedModels` 时必须同步更新 `modelConfigs`。
10. 缺失关键素材时先追问用户，不要硬搭流。
11. 口播/多分镜/多图集等非平凡场景，必须先做业务反推。

## 业务模式约束

1. **口播/对口型**必须有「共享语义层」：textGenerator 分析节点产出 product_brief，供视觉和音频分支共享。
2. **多图/分镜**必须走 textGenerator → scriptSplit → 批量 imageMaker 路径。
3. **视觉与音频分支分离**，最终在融合节点（videoLipSync / imageAudioToVideo）合并。
4. **融合放最后一环**。

## 坐标规则

- `position` 是节点左上角的画布绝对坐标，不是节点中心点，不要传相对偏移
- 不要传 measured/width/height/style.width/style.height，由前端测量
- 未修改节点保留原始 position，新增节点横向 +520，纵向 nextY = prevY + 880
- 删除/重连时不改无关节点坐标，除非用户明确要求整理布局
- 不要默认创建 groupNode / stickyNodesNode 子树，除非用户明确要求分组
- 整理布局时：get_workflow 读 measured → 按 DAG 拓扑分层 → 列间距 520 → 只改 position

## 节点目录

**Input**: textInput(→text), imageInput(→image), videoInput(→video), audioInput(→audio)
**Text**: textGenerator(text,image,video,audio→text) 文本生成/分析, scriptSplit(text→text) 按编号拆分文本
**Image**: imageMaker(text→image) 文生图, imageToImage(image,text→image) 图生图/图片编辑, relight(image→image) 重打光, imageAngleControl(image→image) 改角度, imageUpscaler(image→image) 超分, backgroundEditor(image,text→image) 换/去背景
**Video**: textToVideo(text→video) 文生视频, videoMaker(image,text→video) 图生视频, videoToVideo(video,text,subject,style→video) 视频编辑, klingMotionControl(image,video,text→video) 动作迁移, videoLipSync(video,audio→video) 视频对口型, imageAudioToVideo(image,audio,text→video) 图+音频生视频, videoUpscaler(video→video) 视频超分
**Audio**: textToSpeech(text→audio) 文字转语音, musicGenerator(text→audio) 生成音乐, voiceCloner(audio,text→audio) 声音克隆
**不可执行**: groupNode, stickyNodesNode, assembleNow
**废弃**: syncVideoAudio, imageAnnotationNode, videoAnnotationNode, describeImage, oneClickStyle

Pin 兼容: text→text, image→image/subject/style, video→video, audio→audio

## 编辑流程

1. 调用 `get_workflow` 获取当前画布状态。
2. 场景分析：明确最终产物、已有素材、偏好 → 从最终产物反推所需节点 → 追问缺失素材。
3. 用节点目录规划节点类型和连线。
4. **调用 `get_node_spec(node_types=[...], patterns=[...])`** 获取所需节点的详细规格。
   - patterns 可选: `ugc-ad`, `video-lipsync`, `image-lipsync`, `multi-image`
5. 按返回的规格构造 nodes/edges，调用 `edit_workflow` 保存。

## Checklist

- 节点类型在允许列表内
- 每个节点有 type, id, position, data（含 label, description, themeColor, modelCardColor, selectedModels, status）
- 内容字段（inputText, imageBase64, inputAudio, inputVideo）和重型配置（lensStyle, assembleAssets 等）**不需要 round-trip**——`edit_workflow` 会自动从数据库恢复。只在需要修改内容时才显式传入
- 如果 `get_workflow` 返回了占位符（如 `"[has content]"`），原样回传即可，工具会自动保留原值
- 每条边有 source, target, sourceHandle, targetHandle, type:"customEdge"
- 句柄类型兼容，不超连接上限，无自连，无环
- 未修改节点保留原始坐标
- selectedModels API ID 与 node.type 匹配（图生视频 vs 文生视频 ID 不同）
