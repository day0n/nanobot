---
name: create-workflow
description: 在当前画布中编辑 OpenCreator 工作流
---

# 编辑 OpenCreator 工作流

当用户在画布聊天中要求创建或修改工作流时，使用本 skill。

## 触发条件

- 用户要求"帮我搭一个工作流"、"创建一个文生图流程"等
- 用户要求修改当前画布中的工作流

如果用户只是问建议或询问节点用法，不要直接调用 `edit_workflow`。

## 上下文

工具会自动从当前画布会话获取 `user_id` 和 `flow_id`，不需要手动传入。
本工具只能在已认证的画布会话中使用。

## 强约束（必须遵守）

1. 仅使用前端已支持节点（详见 references）。
2. 不使用废弃节点：`syncVideoAudio`, `imageAnnotationNode`, `videoAnnotationNode`、`describeImage`、`oneClickStyle`。
3. `node.type` 是节点类型的唯一可信来源，不要依赖 `data.type`。
4. **每个节点必须有 `position: {x, y}`**，用于画布布局。从左到右排列，间距建议 x 方向 400px，y 方向 300px。
5. 连线只允许类型兼容的 Pin：`text->text`, `image->image`, `video->video`, `audio->audio`。
  `subject`/`style` 是 `image` 的别名，因此 `image` 输出可以接到 `subject` 或 `style` 输入。
6. 所有 edge 的 `source` 和 `target` 必须都存在于 nodes。
7. 不允许重复 node id。
8. 工作流保持 DAG（不要闭环）。
9. 执行节点必须有合法 `selectedModels`（输入节点除外）。
10. `groupNode`、`stickyNodesNode`、`assembleNow` 是不可执行节点，不参与自动执行链路。
11. 替换或新增 `selectedModels` 时，必须同步更新 `modelConfigs`。

## 编辑步骤

1. 先调用 `get_workflow`，拿到当前画布的完整 `nodes/edges/position`，把它当作唯一真实状态。
2. 基于用户目标给出一个清晰链路（`A -> B -> C`）。
3. 在现有工作流上生成完整更新后的 `nodes`，**每个节点必须包含 position**；未修改的节点尽量保留原位置。
4. 按 pin 规则生成完整更新后的 `edges`。
5. 调用前检查（见下方 checklist）。
6. 通过 `edit_workflow` 工具保存到当前画布。

## 调用前 Checklist

1. 节点类型是否都在允许列表里。
2. 每个节点必须包含：
  - `type`, `id`, `position: {x, y}`
  - `data` 至少含：`label`, `description`, `themeColor`, `modelCardColor`
  - `data` 中：`selectedModels`, `inputText`, `imageBase64`, `inputAudio`, `inputVideo`
  - `data` 中：`status`, `isSelectMode`
  - 不要写入 `isNodeConnected`、`isTextPinConnected`、`isImagePinConnected` 等前端派生字段
3. 所有边都有：
  - `source`, `target`, `sourceHandle`, `targetHandle`
  - `type: "customEdge"`
4. 句柄类型匹配，且不超过连接上限。
5. 建边前 4 项校验：不自连、类型兼容、目标 Pin 未超最大连线数、无环。

## 常用模板

- 文生图：`textInput -> imageMaker`
- 文生视频：`textInput -> textToVideo`
- 图生视频：`textInput -> imageMaker -> videoMaker`
- 分镜视频：`textInput -> textGenerator -> scriptSplit -> imageMaker -> videoMaker`
- 视频改造：`videoInput + textInput -> videoToVideo -> videoUpscaler`
- 口播视频：`textInput -> textToSpeech`, `videoInput + audio -> videoLipSync`

## 进阶参考（按需读取）

根据构建需要，读取对应参考文件：

- 需要选模型、设参数时：
`{skill_dir}/references/model-guide.md`
- 需要填写 inputText 或搭建复杂工作流结构时：
`{skill_dir}/references/prompt-and-workflow-patterns.md`
- 节点结构、句柄、连线等基础契约：
`{skill_dir}/references/node-configs.md`
