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
12. 缺失关键素材时，不要硬搭流，必须先追问用户补齐。
13. 口播广告、多分镜、多图集这类非平凡场景，禁止直接套最小模板，必须先做业务反推。

## 业务模式约束

- 口播广告 / UGC 场景：
  - 必须先有共享语义层，先统一卖点、人群、语气，再分视觉分支和音频分支。
  - 不要一上来就直接 `imageAudioToVideo` 或 `videoLipSync`。
- 对口型场景：
  - 用户已有视频时，优先 `videoLipSync`
  - 用户只有图片且速度优先时，优先 `imageAudioToVideo`
  - 用户只有图片但明确需要镜头运动时，优先 `videoMaker -> videoLipSync`
- 多图 / 组图 / 分镜场景：
  - 默认先走 `textGenerator -> scriptSplit -> 按条执行`
  - 除非用户明确只要单张图，否则不要直接用一个 `imageMaker` 覆盖整组需求
- 已有画布修改场景：
  - 未修改节点尽量保留原位置与原连线
  - 只对受影响区域做增删改，不要无故重做整图

## 场景分析与反推搭流

搭流时不要先想“套哪个模板”，而是先从最终产物反推：

1. 理解用户目标：
  - 最终产物是什么：文本 / 图片 / 视频 / 音频 / 多图集 / 口播广告
  - 用户已有素材是什么：文本、产品图、人物图、视频、音频、参考风格
  - 用户偏好：速度优先 / 质量优先 / 成本优先
2. 从最终产物反推所需能力：
  - 对口型：需要图片+音频+文本，或视频+音频
  - 多图集：需要先规划多张图的职能，再拆分为单图任务
  - 口播广告：需要共享语义层，再分视觉分支和音频分支，最后融合
3. 逐层往前推每个原子的输入来源：
  - 输入是用户直接提供
  - 还是前置节点生成
4. 发现关键输入缺失时，立刻追问，不要继续脑补。
5. 先确定抽象结构，再选节点、选模型、写 prompt。
6. 对已有画布的修改，先识别哪些节点必须保留，哪些节点需要新增/替换/删除，再生成整图。

## 场景决策速查

- 对口型场景：
  - 用户有现成视频，且重点是“视频说话”时，优先 `videoLipSync`
  - 用户只有人物/产品图，想快速产出，优先 `imageAudioToVideo`
  - 用户只有图，但还想要镜头运动或更强动态，再考虑 `videoMaker -> videoLipSync`
- 组图场景（如亚马逊 listing、多图海报、多分镜图）：
  - 标准结构优先是 `textGenerator -> scriptSplit -> 按条生图`
  - 不要直接一个 `textInput -> imageMaker` 企图生成整组图
- 口播广告场景：
  - 先做共享语义层（产品卖点/人群/情绪）
  - 再拆视觉分支和音频分支
  - 最后在对口型/融合节点合并
- 端到端场景：
  - 如果某个模型可直接产出最终结果，可简化链路
  - 但只有在它能稳定满足用户目标时才这样做，不要为了省节点牺牲可控性
- 已有画布编辑场景：
  - 优先识别可复用节点，而不是全部推倒重来
  - 只要用户没有明确要求整理画布，就尽量保留既有位置布局

## 编辑步骤

1. 先调用 `get_workflow`，拿到当前画布的完整 `nodes/edges/position`，把它当作唯一真实状态。
2. 用“场景分析与反推搭流”流程确定抽象结构，先回答：最终产物需要哪些原子能力，它们的输入从哪里来。
3. **必读** `{skill_dir}/references/prompt-and-workflow-patterns.md`
  - 任何非平凡工作流在确定结构前都必须读，重点是第四章高级工作流结构模板。
4. **必读** `{skill_dir}/references/model-guide.md`
  - 在给执行节点选择模型前必须读，不能只靠默认模型拍脑袋决定。
5. 按需读取 `{skill_dir}/references/node-configs.md`
  - 在填写 node data、handle、modelConfigs、连接限制时读取。
6. 如果用户缺失必须素材（如做对口型但没有音频，做商品图但没有产品描述），先追问，不要继续调用保存工具。
7. 在现有工作流上生成完整更新后的 `nodes`，未修改的节点尽量保留原位置；新增节点必须给出合理 `position`。
8. 按 pin 规则生成完整更新后的 `edges`。
9. 对复杂场景，优先让 prompt/脚本节点承担“规划”和“拆分”职责，不要把业务结构压缩成单个执行节点。
10. 调用前检查（见下方 checklist）。
11. 通过 `edit_workflow` 工具保存到当前画布。

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

## 必读参考（按阶段读取）

- 搭抽象结构阶段：
`{skill_dir}/references/prompt-and-workflow-patterns.md`
- 选模型阶段：
`{skill_dir}/references/model-guide.md`
- 填写节点 data / handle / modelConfigs 阶段：
`{skill_dir}/references/node-configs.md`
