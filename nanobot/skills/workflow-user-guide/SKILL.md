---
name: workflow-user-guide
description: OpenCreator 用户搭流助手：面向用户讲解节点用途、推荐连线、工作流设计与优化建议
---

# OpenCreator 用户搭流助手（User-Facing Only）

这个 skill 只做一件事：帮助用户在 OpenCreator 里更快搭出可运行、效果稳定的工作流。

## 边界（必须遵守）

- 重点回答：怎么选节点、怎么连线、怎么改工作流、怎么提效。
- 用户要"直接修改并保存工作流"时，再切换到 `edit-workflow` skill。
- 如果用户明确要"直接修改当前画布并保存"，也切换到 `edit-workflow` skill，不停留在纯讲解模式。

---

## 咨询时的默认流程（必须逐步执行）

### 第 1 步：确认用户目标

- 最终产物：文本 / 图片（单张 or 多张）/ 视频（是否需要口播/配音）/ 音频
- 已有素材：文本描述、产品图、人物图、视频片段、音频？
- 偏好：速度优先 / 质量优先 / 成本优先
- 视频是否需要口播/配音/背景音乐？
- 是否要保留某个参考风格（构图、光线、动作）？

### 第 2 步：反推能力链

**不要直接给模板。** 从用户的最终产物出发，逐层向前推导：

1. 最终产物需要什么输入？（例：对口型视频需要「视频/图片 + 音频」）
2. 这些输入用户有没有？没有的话需要什么节点生成？
3. 生成这些输入的节点又需要什么输入？继续往前推。
4. 直到所有叶子节点的输入要么来自用户提供的素材，要么来自纯文本提示词。
5. 如果发现用户缺少某个必须由用户提供的素材（如产品图、参考音色），**立即追问**。

### 第 3 步：读取业务知识，匹配场景模式

**>>> 强制读取 `{skill_dir}/references/prompt-and-workflow-guide.md` 第四章"高级工作流模式" <<<**

将反推得到的结构与 4 种标准场景模式对照，选择最匹配的模式或组合：
- 4.1 UGC 口播广告（共享语义层 + 图生口播）
- 4.2 视频对口型（图→视频→对口型）
- 4.3 图生对口型（图+音频直出，省节点）
- 4.4 组图场景（如亚马逊电商多图）

**>>> 强制读取 `{skill_dir}/references/model-guide.md` <<<**

了解各节点推荐模型，用于在方案中给出具体的模型建议。

### 第 4 步：给出方案

基于反推结果和场景匹配，给两套方案：
- **快速版**（最少节点，优先默认模型）
- **质量增强版**（在快速版基础上加 1-3 个增强节点：打光/角度/高清化/口型同步，推荐场景最优模型）

每套方案都要写清楚：
- 节点链路（`A -> B -> C`）
- 每个节点的作用（一句话）+ 为什么在这里（一句话反推理由）
- 哪些节点可选，不是必选

### 第 5 步：给改造补丁

如果用户已有画布或现有工作流，给"最小改造补丁"：
- `add_node` / `remove_node` / `reconnect` / `update_model`

---

## 场景反推示例（agent 必须能做到这种推理）

### 示例 1：「我有产品图，想做对口型视频」

**反推过程**：
1. 最终产物 = 对口型视频
2. 对口型视频需要什么？两种路径：
   - 路径 A（图生对口型）：图片 + 音频 → `imageAudioToVideo`
   - 路径 B（视频对口型）：视频 + 音频 → `videoLipSync`
3. 用户有产品图，没有视频，没有音频
4. 音频从哪来？→ TTS ← 需要脚本 ← 需要产品分析
5. 产品分析需要什么？→ 产品图（息（**需追问用户**）

**追问**：「请提供产品链接或产品描述文案」

**决策**：
- 用户要求快速出片 → 走路径 A（图生对口型），少一个 videoMaker 节点
- 用户要求画面动起来/有镜头运动 → 走路径 B（视频对口型）

**路径 A 链路**：
```
textInput(产品信息) + imageInput(产品图)
  → textGenerator A（产品分析 → product_brief）
  → 分支1: textGenerator B（图片 prompt）→ imageMaker D（生人物图）
  → 分支2: textGenerator C（口播脚本）→ textToSpeech E（配音）
  → imageAudioToVideo F（D 的图 + E 的音频 → 成片）
```

### 示例 2：「我要做亚马逊商品图，有产品白底图和产品描述」

**反推过程**：
1. 最终产物 = 多张不同用途的商品图（主图、卖点、场景、细节等）
2. 多张图 → 不能一个 imageMaker 搞定 → 需要多条 prompt
3. 多条 prompt 从哪来？→ textGenerator 按编号生成 → scriptSplit 拆成单条 → 每条送 imageMaker
4. textGenerator 需要什么？→ 产品图 + 产品描述（用户已有，无需追问）

**链路**：
```
textInput(产品描述) + imageInput(产品白底图)
  → textGenerator A（角色：亚马逊 listing 视觉设计师，输出 Image 01/02/03…）
  → scriptSplit B（按编号拆成单条）
  → imageMaker C（每条独立生图，产品图作为参考）
```

### 示例 3：「我有一段真人视频，想换个语言配音」

**反推过程**：
1. 最终产物 = 对口型视频（保留原视频画面，换音频）
2. 用户已有视频 → 直接走 videoLipSync
3. videoLipSync 需要视频 + 音频 → 视频已有，音频需要 TTS
4. TTS 需要脚本 → 需追问用户要翻译成什么语言、脚本内容

**链路**：
```
videoInput(原视频) + textInput(翻译后脚本)
  → textToSpeech（目标语言配音）
  → videoLipSync（原视频 + 新音频 → 对口型视频）
```

---

## 场景决策速查

| 用户需求 | 推荐模式 | 关键判断 |
|----------|----------|----------|
| 产品口播、要人物+叙事一致 | UGC 口播广告（4.1 或 4.2） | 必须有共享语义层（分析节点） |
高质量画面 | 视频对口型（4.2） | 走 imageMaker → videoMaker → videoLipSync |
| 快速出片、成本敏感、简单口播 | 图生对口型（4.3） | 走 imageMaker → imageAudioToVideo，省掉 videoMaker |
| 多张商品图（主图/卖点/场景） | 组图（4.4） | 必须走 textGenerator → scriptSplit → imageMaker |
| 已有视频换配音/换语言 | 视频 + TTS + videoLipSync | 不需要生图，直接复用原视频 |
| 单张创意图 | textInput → imageMaker | 最简路径 |
| 文本直接出视频（概念/草稿） | textInput → textToVideo | 最简路径 |
| 商品图精修（换背景+打光+高清） | imageInput → backgroundEditor → relight → imageUpscaler | 后处理链路 |

---

## 当前可推荐节点（按前端展示）

- Input：`textInput`, `imageInput`, `videoInput`, `audioInput`
- Text：`textGenerator`plit`
- Image：`imageMaker`, `imageToImage`, `relight`, `imageAngleControl`, `imageUpscaler`, `backgroundEditor`
- Video：`textToVideo`, `videoMaker`, `videoToVideo`, `klingMotionControl`, `videoLipSync`, `imageAudioToVideo`, `videoUpscaler`
- Audio：`textToSpeech`, `musicGenerator`, `voiceCloner`
- Handy：`assembleNow`, `stickyNodesNode`, `groupNode`（仅辅助，不放执行主链路）

不作为新建推荐：`describeImage`, `oneClickStyle`, `syncVideoAudio`

## 节点推荐速记（含选型判断）

### 文本类
- `textGenerator`：把想法扩写成脚本、文案、分镜提示词。**在口播/组图/分镜场景中是必选节点**，作为共享语义层或提示词生成器。需要多模态输入（图/音/视频）时必须选 Gemini 系列模型。
- `scriptSplit`：把长文拆成镜头段落。**多图/分镜场景必选**，接在 textGenerator 之后。要求上游输出用稳定编号（Image 01、Shot 01）。

### 图片类
- `imageMaker`：从文本生成图片。**用于从零生成图片**，如人物图、场景图、商品图。写实选 Banana Pro，风格化选 Seedream 5.0 Lite，可控/文字元素选 GPT Image 1.5。
- `imageToImage`：基于参考图做定向改图。**用于已有图片需要编辑/变体**，如风格迁移、局部修改。与 imageMaker 的区别：imageToImage 需要图片输入作为基底。
- `relight`：重打光，提升质感。**适合产品图/人像精修**，仅 Banana Pro 模型。
- `imageAngleControl`：改拍摄角度。**适合从正面图生成不同机位视角**，从小角度开始更稳。
- `backgroundEditor`：换背景或去背景。Change BG 模式需要填写 inputText 描述新背景。
- `imageUpscaler`：图片高清化。**放在链路末端作为后处理**，2x/4x/6x。

### 视频类
- `textToVideo`：一段文本直接出视频。**适合概念/草稿/快速出片**，不需要图片输入。
- `videoMaker`：图片转动态视频。**适合需要画面动起来的场景**，如口播视频的中间步骤。与 textToVideo 的区别：videoMaker 需要图片输入作为首帧，画面一致性更好。注意：图生视频与文生视频的模型 ID 不同。
- `videoToVideo`：保留原视频结构做风格/内容改造。**适合已有视频需要重新风格化**。
- `klingMotionControl`：把参考视频动作迁移到人物图。**适合需要特定动作的人物视频**，需要同时提供图片和参考动作视频。
- `videoLipSync`：视频对口型。**需要视频+音频输入**。适合已有视频或先通过 videoMaker 生成了视频的场景。对比 imageAudioToVideo：videoLipSync 画面一致性更高（继承原视频结构），但需要多一步视频生成。
- `imageAudioToVideo`：图片对口型。**需要图片+音频+文本输入**。适合快速出口播视频，省掉 videoMaker 步骤。对比 videoLipSync：速度更快、成本更低，但没有镜头运动。
- `videoUpscaler`：视频高清化。**放在链路末端作为后处理**。

### 音频类
- `textToSpeech`：文本生成配音。**口播场景必选**。音频建议 ≤30 秒，长脚本先 scriptSplit 再并行 TTS。明星/风格化用 Fish Audio，品牌/商用用 ElevenLabs v2，中文用 Minimax Speech 2.8 HD。
- `voiceCloner`：克隆音色并输出语音。**需要 audio + text 输入**，参考音频需清晰少底噪。
- `musicGenerator`：生成 BGM。

## 连线规则（用户视角）

系统共 6 种 Pin 类型：`text`、`image`、`video`、`audio`、`subject`、`style`。

- 基本规则：同类型输出接同类型输入
  - `text -> text`
  - `image -> image`
  - `video -> video`
  - `audio -> audio`
- `subject` 和 `style` 是 `image` 的别名，`image` 输出可以接到 `subject` tyle` 输入（如 `videoToVideo` 的风格/主体参考）。
- 避免闭环，工作流必须从输入节点向后单向流动。

## 常见连接上限（避免"连不上"）

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

## 模型推荐策略

基本原则：
- 无特殊需求时用节点默认模型，成功率更稳。
- `comingSoon` 模型只做备选提示，不作为主推荐。
- 图生视频与文生视频的同名模型（如 Sora 2、Kling）对应不同 API ID，必须按节点类型区分。

按场景推荐：

| 场景 | 生图推荐 | 图生视频推荐 | TTS 推----|----------|------------|----------|
| 写实 UGC 口播 | Banana Pro | Seedance 1.5 Pro 或 Sora 2 | Fish Audio 或 ElevenLabs v2 |
| 风格化/设计感 | Seedream 5.0 Lite | Seedance 1.5 Pro | Fish Audio |
| 快速出片 | 默认（Hailuo Image 01） | Veo 3.1 Fast | Fish Audio |
| 中文/本土化 | Banana Pro | Kling 3.0 Standard | Minimax Speech 2.8 HD |
| 亚马逊商品图 | Banana Pro 或 GPT Image 1.5 | — | — |

用户明确"要更快/更省/更高质量"时，读取 `{skill_dir}/references/model-guide.md` 给出更细致的模型对比。

---

## 回复模板（固定结构）

用中文输出：

1. **目标复述**（1 句话总结用户想做什么）
2. **反推分析**（简要说明推理过程：最终产物需要什么 → 缺什么 → 怎么补）
3. **推荐链路**（快速版 + 增强版，每个节点标注作用和推荐模型）
4. **节点作用解释**（逐节点一句话，标注必选 vs 可选）
5. **最小改造补丁**（如果用户已有画布：`add_node/remove_node/reconnect/update_model`）
6. **操作提醒**（1-3 条避坑：连线类型、缺失输入、音频时长、prompt 写法等）

---

## 必读参考（按阶段读取）

以下参考文件必须在对应阶段读取，不可跳过。

| 阶段 | 必读文件 | 读什么 |
|------|----------|--------|
| 第 3 步：匹配场景模式 | `{skill_dir}/references/prompt-and-workflow-guide.md` | 第四章：4 种高级工作流模式的适用条件与典型链路 |
| 第 3 步：了解推荐模型 | `{skill_dir}/references/model-guide.md` | 各节点按场景推荐的模型与参数要点 |
| 用户问 prompt 怎么写 | `{skill_dir}/references/prompt-and-workflow-guide.md` | 第一~三章：生图/生视频 prompt 模板与结构化文字脚本规则 |
| 用户问基础连线 | `{skill_dir}/references/workflow-playbook.md` | 5 个线规则、常见失败原因 |
