---
name: edit-workflow
description: 在当前画布中编辑 OpenCreator 工作流
trigger: Before calling edit_workflow tool
---

# 编辑 OpenCreator 工作流

当用户在画布聊天中要求修改工作流时，使用本 skill。

## 触发条件

- 用户要求"帮我搭一个工作流"、"加几个节点"、"改一下流程"等
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
11. 删除节点时必须级联删除所有关联边（`edge.source` 或 `edge.target` 等于被删节点 ID）。
12. 替换或新增 `selectedModels` 时，必须同步更新 `modelConfigs`（新增模型要写入默认配置，删除旧模型要清理残留配置）。
13. 缺失关键素材时，不要硬搭流，必须先追问用户补齐。
14. 口播广告、多分镜、多图集这类非平凡场景，禁止直接套最小模板，必须先做业务反推。
15. `position.x` / `position.y` 必须是有限数字；不要传字符串、`null`、`NaN`、`Infinity`。
16. 普通节点的 `position` 一律按画布绝对坐标传入；不要把节点中心点当作坐标，也不要传相对偏移。

## 业务模式约束（必须遵守）

1. **口播/对口型场景**必须包含「共享语义层」：至少一个 `textGenerator` 分析节点将用户原始输入（产品图、URL、受众等）转化为可复用的 product_brief，供下游视觉分支和音频分支共享，保证信息一致。
2. **多图/分镜场景**必须走 `textGenerator -> scriptSplit -> 批量生图` 路径：先由文本节点按编号生成多图/多镜头描述集，再由 `scriptSplit` 拆成独立单条，再逐条输入 `imageMaker`。不要试图用一个 `imageMaker` 节点一次生成多张图。
3. **视觉分支与音频分支分离**：在需要人物+叙事的场景（口播、UGC 广告等），视觉生成链路和音频生成链路应各自独立，最终在融合节点（`videoLipSync` 或 `imageAudioToVideo`）合并。不要在中间节点混合视觉和音频逻辑。
4. **融合尽量放在最后一环**：`videoLipSync`、`imageAudioToVideo` 等融合节点应处于工作流末端。先锁定人物图像身份，再生成运动/音频，最后融合。

## 坐标传入规则

- `position` 表示节点左上角在画布中的绝对坐标：
  - 顶层节点直接传 `{x, y}`
  - 只有真的要做分组子节点时，才考虑 `parentId + 相对 position`
  - 当前 AI 搭流默认不要创建 `groupNode` / `stickyNodesNode` 子树
- 普通执行节点不要额外传 `measured`、`width`、`height`、`style.width`、`style.height`
  - 这些由前端测量
  - 只传 `position` 即可
- 编辑已有画布时：
  - 未修改节点保留原始 `position`
  - 修改内容但不改结构的节点，仍保留原始 `position`
  - 新增节点只给新增节点分配新坐标
- 新增顶层节点的横向排布建议：
  - 输入节点列：沿用现有输入列的 `x`
  - 第一列执行节点：放在输入列右侧，建议 `+460` 到 `+520`
  - 执行节点到下一执行节点：建议继续 `+520`
  - 这样能覆盖前端常见节点宽度（输入节点约 300，执行节点约 360）并留出安全间距
- 新增顶层节点的纵向排布建议：
  - 所有节点统一按 宽 `350`、高 `800` 估算，同列相邻节点 `nextY = prevY + 880`
  - 有 `measured` 数据时用 `measured.height` 替代 800
- 多分支场景：
  - 同一层分支优先上下展开，不要和主链横向挤在一起
  - 如果一个父节点分出多条支路，优先共用同一"下一列"，再按 `y` 方向错开
- 删除或重连时：
  - 不要为了"看起来整齐"而顺手改动无关节点坐标
  - 除非用户明确要求整理布局，否则只改受影响节点的位置

## 整理布局场景

当用户要求"整理布局"、"排列整齐"、"重新排版"时：

1. 调用 `get_workflow`，读取每个节点的 `measured` 尺寸
2. 按 DAG 拓扑分层，从左到右排列，列间距 `520`
3. 同层多节点从上到下：`nextY = prevY + 880`（有 measured 时用 `measured.height + 80`）
4. 只改 position，不改 data 和 edges

---

## 场景分析与反推搭流（核心流程，必须逐步执行）

在动手构造 nodes/edges 之前，**必须**完成以下反推流程。不要跳过任何步骤。

### 步骤 1：理解用户场景

明确以下三个要素：
- **最终产物**：文本 / 图片（单张 or 多张）/ 视频（是否需要口播）/ 音频
- **已有素材**：用户提供了什么——文本描述、产品图、人物图、视频片段、音频？
- **偏好**：速度优先 / 质量优先 / 成本优先

### 步骤 2：从最终产物反推所需能力

从最终输出向前倒推，问自己：
- 要产出这个最终产物，最后一个节点需要什么类型的输入？
- 这些输入从哪来——用户直接提供，还是需要前置节点生成？
- 如果需要前置生成，那个前置节点又需要什么输入？

**逐层往前推**，直到所有叶子节点的输入要么来自用户提供的素材（inputNode），要么来自纯文本提示词。

示例推理：
> 用户想做「对口型视频」，提供了「产品图」——
> → 对口型需要 视频+音频 或 图片+音频
> → 用户没有视频，也没有音频
> → 音频从哪来？需要 TTS ← 需要脚本 ← 需要产品分析
> → 图片/视频从哪来？需要生图 ← 需要图片 prompt ← 需要产品分析
> → 产品分析需要什么？产品图（用户已有）+ 产品信息（需追问用户）
> → 确定：用户还需要提供产品信息/URL

### 步骤 3：追问缺失素材

如果反推过程中发现用户没有提供某个**必须由用户提供**的素材（如产品图、参考视频、音色样本），**立即追问用户**，不要假设或跳过。

### 步骤 4：匹配场景结构模板

**>>> 强制读取 `{skill_dir}/references/prompt-and-workflow-patterns.md` 第四章"高级工作流结构模板" <<<**

将反推得到的抽象结构与该文件中的 4 个标准模板进行对照：
- 4.1 UGC 口播广告（共享语义层 + 图生口播）
- 4.2 视频对口型（图→视频→对口型）
- 4.3 图生对口型（图+音频直出）
- 4.4 组图（亚马逊风多图）

选择最匹配的模板作为骨架，再根据用户具体需求增减节点。如果没有现成模板匹配，用反推得到的结构自行组合。

### 步骤 5：为每个节点选择模型

**>>> 强制读取 `{skill_dir}/references/model-guide.md` <<<**

按 node.type 查表为每个执行节点填写正确的 `selectedModels` API ID。注意：
- 图生视频（videoMaker）与文生视频（textToVideo）的模型 ID 不同，不可混用
- 需要多模态输入的 textGenerator 必须选 Gemini 系列
- 优先用场景决策速查中的推荐组合（见下方）

### 步骤 6：精调提示词

**>>> 强制读取 `{skill_dir}/references/prompt-and-workflow-patterns.md` 第一~三章 <<<**

为每个需要 `inputText` 的节点编写提示词：
- `textGenerator` 节点：按结构化文字脚本规则设定角色（如「你是专业亚马逊 listing 视觉设计师」），指定输出格式（编号分块、一块一目标、块内自洽）
- `imageMaker` / `imageToImage` 节点：按生图 prompt 模板（构图+镜头+光影+质感+风格+画质）
- `videoMaker` / `textToVideo` 节点：按生视频 prompt 模板（机位+运动+光影+效果+风格）
- 对口型融合节点（`imageAudioToVideo`）：inputText 描述表情、风格、表演方式

---

## 场景决策速查

### 对口型：图生对口型 vs 视频对口型

| 条件 | 选择 | 链路 |
|------|------|------|
| 速度/成本优先，不需复杂镜头运动 | **图生对口型** `imageAudioToVideo` | 分析→描述→生图 + 分析→脚本→TTS → imageAudioToVideo |
| 需要人物动起来、有镜头语言 | **视频对口型** `videoMaker` + `videoLipSync` | 分析→描述→生图→图生视频 + 分析→脚本→TTS → videoLipSync |

两种路径都必须有**共享语义层保视觉与文案同源。

### 组图场景（电商多图、分镜）

标准路径：`textGenerator`（编号多图描述，如 Image 01/02/03）→ `scriptSplit`（拆成单条）→ 每条接 `imageMaker`

关键规则：
- textGenerator 输出必须用稳定编号（`Image 01`、`Shot 01`），每块自洽
- scriptSplit 严格按编号拆分
- 每个 imageMaker 接一条 scriptSplit 输出，prompt 独立

### UGC 口播广告（通用结构）

```
输入层（产品图 + 产品信息 + 目标人群）
  → 共享语义层：textGenerator A（产品分析 → product_brief）
  → 视觉分支：textGenerator B（图片 prompt）→ imageMaker D
  → 音频分支：textGenerator C（口播脚本）→ textToSpeech E
  → 融合：D + E → imageAudioToVideo F（或 D → videoMaker → videoLipSync）
```

### 已有画布编辑场景

- 优先识别可复用节点，而不是全部推倒重来
- 只要用户没有明确要求整理画布，就尽量保留既有位置布局
- 未修改节点尽量保留原位置与原连线
- 只对受影响区域做增删改，不要无故重做整图

### 模型推荐组合（按场景）

| 场景 | 生图推荐 | 图生视频推荐 | TTS 推荐 |
|------|----------|------------|----------|
| 写实 UGC 口播 | Banana Pro | Seedance 1.5 Pro 或 Sora 2 | Fish Audio 或 ElevenLabs v2 |
| 风格化/设计感 | Seedream 5.0 Lite | Seedance 1.5 Pro | Fish Audio |
| 快速出片 | Hailuo Image 01（默认） | Veo 3.1 Fast | Fish Audio |
| 中文/本土化 | Banana Pro | Kling 3.0 Standard | Minimax Speech 2.8 HD |
| 亚马逊商品图 | Banana Pro 或 GPT Image 1.5 | — | — |

---

## 编辑步骤

1. 先调用 `get_workflow`，拿到当前画布的完整 `nodes/edges/position`，把它当作唯一真实状态。
2. 用上方"场景分析与反推搭流"流程确定抽象结构，先回答：最终产物需要哪些原子能力，它们的输入从哪里来。
3. **必读** `{skill_dences/prompt-and-workflow-patterns.md`
  - 任何非平凡工作流在确定结构前都必须读，重点是第四章高级工作流结构模板。
4. **必读** `{skill_dir}/references/model-guide.md`
  - 在给执行节点选择模型前必须读，不能只靠默认模型拍脑袋决定。
5. 按需读取 `{skill_dir}/references/node-configs.md`
  - 在填写 node data、handle、modelConfigs、连接限制时读取。
6. 如果用户缺失必须素材（如做对口型但没有音频，做商品图但没有产品描述），先追问，不要继续调用保存工具。
7. 对已有画布的修改，先识别哪些节点必须保留，哪些节点需要新增/替换/删除，再生成整图。
8. 在现有工作流上生成完整更新后的 `nodes`，未修改的节点尽量保留原位置；新增节点必须给出合理 `position`。
9. 按 pin 规则生成完整更新后的 `edges`。
10. 新增节点定坐标时，先找锚点节点：
  - 接在某节点后面，就放在该节点右侧一列
  - 作为并行分支，就放在同一下一列但改 `y`
  - 只是改 prompt / model / data，不要改坐标
11. 对复杂场景，优先让 prompt/脚本节点承担"规划"和"拆分"职责，不要把业务结构压缩成单个执行节点。
12. 调用前检查（见下方 checklist）。
13. 通过 `edit_workflow` 工具保存到当前画布。

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
6. 坐标校验：
  - 每个节点都有 `position: {x, y}`
  - `x/y` 是数字，不是字符串
  - 未修改节点是否保留了原始坐标
  - 新增节点是否与锚点保持合理列间距，且没有明显重叠风险
7. 口播/对口型场景是否有共享语义层节点。
8. 多图/分镜场景是否走 textGenerator → scriptSplit → imageMaker 路径。
9. 每个 textGenerator 节点的 inputText 是否设定了角色与输出格式。
10. 生图/生视频节点的 inputText 是否遵循 prompt 模板结构。
11. selectedModels 的 API ID 是否与 node.type 匹配（图生视频 vs 文生视频 ID 不同）。

---

## 必读参考（按阶段读取）

以下参考文件必须在对应阶段读取，不可跳过。

| 阶段 | 必读文件 | 读什么 |
|------|----------|--------|
| 步骤 4：匹配场景结构 | `{skill_dir}/references/prompt-and-workflow-patterns.md` | 第四章：4 个高级工作流结构模板（节点、连线、IO、依赖） |
| 步骤 5：选模型 | `{skill_dir}/references/model-guide.md` | 按 node.type 查 API ID，填 selectedModels 和 modelConfigs |
| 步骤 6：写提示词 | `{skill_dir}/references/prompt-and-workflow-patterns.md` | 第一~三章：结构化文字脚本规则、生图/生视频 prompt 模板与词库 |
| 编辑步骤 5：构造 nodes | `{skill_dir}/references/node-configs.md` | 节点白名单、句柄映射、连接上限、data 最小结构、edge 模板 |
