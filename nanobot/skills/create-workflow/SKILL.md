---
name: create-workflow
description: 创建并保存 OpenCreator 工作流
---

# 创建 OpenCreator 工作流

当用户明确要求“创建并保存工作流”时，使用本 skill。

## 触发条件

- 用户要“直接创建并保存到账号”
- 或用户明确要在当前画布里直接落到工作流

如果用户只是问建议，不要直接调用 `create_workflow`。

## 必填信息

1. `workflow_name`

如果当前是已登录的画布聊天，会自动使用当前账号和 `flow_id` 上下文，不需要询问邮箱。
只有在没有认证画布上下文的旧兼容场景里，才需要 `user_email`。

## 强约束（必须遵守）

1. 仅使用前端已支持节点（详见 references）。
2. 新建工作流不使用兼容旧节点：`describeImage`, `oneClickStyle`, `syncVideoAudio`。
3. 连线只允许同类型：`text->text`, `image->image`, `video->video`, `audio->audio`。  
   例外：`videoToVideo` 的 `subject/style` 允许接 `image`。
4. 所有 edge 的 `source` 和 `target` 必须都存在于 nodes。
5. 不允许重复 node id。
6. 工作流保持 DAG（不要闭环）。
7. 执行节点必须有合法 `selectedModels`（输入节点除外）。

## 创建步骤

1. 基于用户目标给出一个清晰链路（`A -> B -> C`）。
2. 按节点模板构造 `nodes`（先完整再优化）。
3. 按 pin 规则构造 `edges`。
4. 调用前检查（见下方 checklist）。
5. 通过 `create_workflow` 工具保存。

## 调用前 Checklist

1. 节点类型是否都在允许列表里。
2. 每个节点 data 至少含：
   - `label`, `description`, `themeColor`, `modelCardColor`
   - `selectedModels`, `inputText`, `imageBase64`, `inputAudio`, `inputVideo`
   - `status`, `isSelectMode`, `isNodeConnected`
3. 所有边都有：
   - `source`, `target`, `sourceHandle`, `targetHandle`
   - `type: "customEdge"`, `animated: true`
4. 句柄类型匹配，且不超过连接上限。

## 常用模板

- 文生图：`textInput -> imageMaker`
- 文生视频：`textInput -> textToVideo`
- 图生视频：`textInput -> imageMaker -> videoMaker`
- 分镜视频：`textInput -> textGenerator -> scriptSplit -> imageMaker -> videoMaker`
- 视频改造：`videoInput + textInput -> videoToVideo -> videoUpscaler`
- 口播视频：`textInput -> textToSpeech`, `videoInput + audio -> videoLipSync`

---

完整节点、默认模型、句柄映射、连接上限、JSON 模板：
`{skill_dir}/references/node-configs.md`
