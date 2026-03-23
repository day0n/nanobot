# OpenCreator 用户搭流手册

> **⚠️ 强制读取提示**：本文件是用户搭流的基础操作手册。当用户询问基础节点连线、简单模板时，本文件 + SKILL.md 即可覆盖。涉及复杂场景（口播、对口型、组图）时，还需配合 `prompt-and-workflow-guide.md` 第四章。

此文档用于给用户提供"可直接照着搭"的指导

## 1) 先问清楚的 5 个问题

1. 你最终要产出什么：文本、图片（单张还是多张）、视频（是否需要口播）还是音频？
2. 你现在有什么素材：文案、图片、视频、音频？
3. 你更在意什么：速度、质量还是成本？
4. 视频是否需要口播/配音/背景音乐？
5. 你是否要保留某个参考风格（构图、光线、动作）？

## 2) 节点清单（用户版）

### Input
- `textInput`：输入创意、文案、脚本或指令
- `imageInput`：上传参考图、产品图、人物图
- `videoInput`：上传待改造视频
- `audioInput`：上传配音或参考音色

### Text
- `textGenerator`：扩写/改写内容，生成可用于图片或视频的提示词
- `scriptSplit`：把长文拆成镜头段，方便分镜生成

### Image
- `imageMaker`：文生图，适合先产出关键帧
- `imageToImage`：基于参考图做风格迁移或细节改造
- `relight`：重新打光，提升质感
- `imageAngleControl`：改视角（正面/俯拍/侧拍等）
- `backgroundEditor`：换背景、去背景
- `imageUpscaler`：放大与锐化

### Video
- `textToVideo`：文本直接生成视频
- `videoMaker`：图片生成视频（首帧动画）
- `videoToVideo`：输入原视频，按要求重绘/改造
- `klingMotionControl`：动作迁移（图 + 参考动作视频）
- `videoLipSync`：视频对口型（视频 + 音频）
- `imageAudioToVideo`：图片对口型（图片 + 音频 + 文本）
- `videoUpscaler`：视频高清化

### Audio
- `textToSpeech`：文本生成配音
- `voiceCloner`：克隆音色并输出语音
- `musicGenerator`：生成背景音乐

### Handy
- `assembleNow`：素材拼装编辑
- `stickyNodesNode`：画布注释
- `groupNode`：画布分组容器，把相关节点框在一起

说明：Handy 节点用于组织工作，不参与自动执行，不建议放在执行主链路里。

## 3) 连线规则（简化版）

系统共 6 种 Pin 类型：`text`、`image`、`video`、`audio`、`subject`、`style`。

- 只连同类：
  - `text -> text`
  - `image -> image`
  - `video -> video`
  - `audio -> audio`
- `subject` 和 `style` 是 `image` 的别名，`image` 输出可以接到 `subject` 或 `style` 输入（如 `videoToVideo` 的风格/主体参考）。

- 建议从左到右单向连线，不要回连到上游节点。

## 4) 常见"连不上"原因

- 超过连接上限（例如 `videoMaker` 最多接 4 张图）。
- 少接了必需输入（例如 `videoLipSync` 必须同时有视频和音频）。
- 输入类型不匹配（例如把 `text` 接到 `image` 输入）。

## 5) 场景模板（含反推逻辑）

### A. 快速文生图
- 适用：海报、封面、产品概念图
- 反推：最终产物=图片，用户只有文字想法 → 只需一步文本→图片
- 链路：`textInput -> imageMaker`

### B. 快速文生视频
- 适用：概念片、短广告草稿
- 反推：最终产物=视频，用户只有文字描述 → 一步文本→视频即可
- 链路：`textInput -> textToVideo`

### C. 图生视频（更可控）
- 适用：先定画面风格，再做动效
- 反推：最终产物=视频，但用户想控制画面 → 先生图锁定视觉身份，再图转视频
- 链路：`textInput -> imageMaker -> videoMaker`

### D. 分镜叙事视频
- 适用：剧情短片、分镜展示
- 反推：最终产物=多镜头视频 → 需要多张关键帧 → 需要多条 prompt → textGenerator 生成分镜脚本 → scriptSplit 拆成单条 → 逐条生图 → 逐张图转视频
- 链路：`textInput -> textGenerator -> scriptSplit -> imageMaker -> videoMaker`
- 关键：textGenerator 输出必须用编号（Shot 01/02/03），每块自洽，scriptSplit 才能正确拆分

### E. 视频改造升级
- 适用：老片风格重做、画面清晰度提升
- 反推：最终产物=改造后视频，用户已有原始视频 → videoToVideo 改风格 → videoUpscaler 提清晰度
- 链路：`videoInput + textInput -> videoToVideo -> videoUpscaler`

### F. UGC 口播广告（完整版，有产品图+产品信息）
- 适用：产品推广口播、UGC 风格广告
- 反推：最终产物=口播视频 → 需要图片/视频+音频 → 音频需要 TTS ← 需要脚本 ← 需要产品分析；图片需要 imageMaker ← 需要图片 prompt ← 需要产品分析 → 产品分析是共享语义层
- 快速版（图生对口型）：

```
textInput(产品信息) + imageInput(产品图)
  → textGenerator A（产品分析）
  → textGenerator B（图片 prompt）→ imageMaker D
  → textGenerator C（脚本）→ textToSpeech E
  → imageAudioToVideo F（D + E → 成片）
```

- 增强版（视频对口型，有镜头运动）：在 D 后加 `videoMaker`，末尾换 `videoLipSync`
- 关键：A 节点是共享语义层，保证视觉与文案同源

### G. 已有视频换配音/对口型
- 适用：讲解视频、多语言口播、配音替换
- 反推：最终产物=对口型视频，用户已有视频 → 不需要生图/生视频 → 只需 TTS + videoLipSync
- 链路：`textInput(脚本) -> textToSpeech`，`videoInput + audio -> videoLipSync`

### H. 亚马逊/电商多图套图
- 适用：亚马逊 listing、电商详情页多图
- 反推：最终产物=多张不同用途商品图 → 需要多条独立 prompt → textGenerator 按编号生成 → scriptSplit 拆分 → 每条送 imageMaker
- 链路：

```
textInput(产品描述) + imageInput(产品图)
  → textGenerator（角色：listing 视觉设计师，输出 Image 0
  → scriptSplit（按编号拆成单条）
  → imageMaker（每条独立生图）
```

- 关键：textGenerator 的角色设定和编号输出格式决定了下游质量

### I. 商品图精修
- 适用：电商主图、详情页图
- 反推：最终产物=精修后产品图，用户已有产品图 → 后处理链路：换背景→打光→高清化
- 链路：`imageInput -> backgroundEditor -> relight -> imageUpscaler`

## 6) 推荐策略（给用户解释时）

- 快速版：节点少、先跑通。
- 增强版：在快速版上加 1-3 个增强节点（打光/角度/高清化/口型同步）。
- 用户没特别要求时，优先推荐默认模型，保证稳定。

## 7) 输出建议（agent 回复格式）

1. 目标：一句话复述
2. 反推分析：简要说明推理链（最终产物需要什么 → 缺什么 → 怎么补）
3. 推荐链路：快速版 + 增强版
4. 节点说明：每个节点一句话
5. 最小改造补丁：`add_node/remove_node/reconnect/update_model`
6. 操作提醒：避免连线类型错误、缺失必填输入、超连接上限
