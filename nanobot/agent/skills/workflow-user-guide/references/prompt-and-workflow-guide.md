# Prompt 工程与高级工作流模式（用户向）

本文件包含关键业务决策模式。`workflow-user-guide` 在回答任何非平凡场景前，必须先读取本文件第四章的高级工作流模式，再给出链路建议。

本文件面向**用户咨询**场景：用户问「prompt 怎么写 / 怎么设计复杂工作流」时使用。包含生图/生视频 prompt 框架、结构化文字脚本要点，以及 4 个高级工作流模式。

---

## 一、生图 Prompt 结构模板

一条合格的生图 prompt 建议包含（顺序可调）：

| 模块 | 说明 | 示例 |
|------|------|------|
| 构图/景别 | 画面布局与景别 | 三分法、特写、中景、全景 |
| 相机与镜头 | 模拟真实光学 | 35mm 镜头、浅景深、DSLR |
| 光影与氛围 | 光源与情绪 | 柔和的自然光、黄金时刻、电影感高对比 |
| 视觉效果/质感 | 颗粒、粒子、光晕等 | 胶片颗粒、尘埃、镜头光晕 |
| 风格/渲染 | 整体美学 | 电影感、时尚大片、动漫风格 |
| 画质/比例 | 分辨率与比例 | 2K、4:3、16:9 |

**可复用预设短语**（按模块）：

- **构图**：rule of thirds, eye-level shot, close-up, medium shot, wide shot, candid moment
- **镜头**：35mm lens, 50mm lens, 85mm portrait lens, shallow depth of field, macro lens
- **光影**：soft natural daylight, golden hour sunlight, high-contrast cinematic lighting, studio softboxes, backlit silhouette
- **质感**：photorealistic texture, film grain, dust particles, lens flare, bokeh
- **风格**：photorealistic, cinematic film look, fashion editorial, anime style, minimalist

**模型侧重**：Banana Pro 偏写实，多写相机/光影/质感；Seedream 5.0 Lite 偏风格化，用完整句子；GPT Image 1.5 简洁可控，可指定透明背景。

---

## 二、生视频 Prompt 结构模板

核心结构（导演思维，一镜头一动作一机位一光影）：

```
[相机与镜头] + [运动/物理] + [光影与氛围] + [视觉效果] + [风格/渲染] + [镜头结构可选]
```

**设计原则**：一镜头=一个主动作+一个机位+一种光影；用物理运动代替抽象动词；模块化、可复用；短 prompt 更自由，长 prompt 更可控。

**可复用预设**：

- **机位**：slow push-in, slow pull-out, pan left/right, tracking shot, static shot, close-up, medium shot, wide shot, low angle, eye-level；镜头：16mm/35mm/50mm/85mm lens, shallow depth of field
- **运动**：leans forward slightly, hair moves with wind, fabric reacts to motion, hand gestures emphasize speech
- **光影**：soft natural daylight, golden hour light, high contrast cinematic lighting, neon lighting, diffused studio lighting
- **风格**：cinematic film look, photorealistic, UGC handheld style, fashion editorial, film grain

**多镜头（如 Sora 2）**：按时间轴分镜，如 [00:00–00:03] Hook、[00:03–00:06] Build、[00:06–00:09] Peak、[00:09–00:12] Resolution；每段一个动作+一个机位+一种光影，避免多事件混在一镜。

---

## 三、结构化文字脚本规则摘要

当文本模型为下游生图/生视频提供脚本、分镜或多图描述时：

1. **只输出结果**：不解释、不推理、不加「下面给出」「如图所示」等过渡语。
2. **编号分块**：每个编号块对应一个执行目标（一图一镜）；单块建议 ≤1500 中文字符；便于 Text Splitter 切割与并行执行。
3. **一块一目标**：一个图像描述=一张图；一个镜头描述=一个镜头；不把多目标合并到一块。
4. **角色先行**：用「你是 [具体角色]。任务是 [具体任务]。直接输出 [格式]。不解释、不赘述。」明确角色与格式。
5. **输出格式**：多图/分镜用 `Image 01`/`Shot 01` 等编号；需要机器复用可用 JSON（scene_id、visual_description、dialogue、camera、lighting 等）。
6. **块内自洽**：每块可独立使用，不写「同上」「同上文」等交叉引用。

**Master 指令示例（多图集）**：  
「你是专业亚马逊 listing 视觉设计师。任务是生成编号多图描述集供下游生成。每图标为 Image 01、Image 02…。每块自洽且仅描述一个图像目标。不解释不赘述，直接输出。每块不超过 1500 字。」

---

## 四、高级工作流模式

### 4.1 UGC 口播广告（端到端，共享语义层）

**适用**：产品图+产品信息+目标人群 → 一条「人物+叙事」一致的 UGC 口播广告。

**核心思路**：先建**共享语义层**（如产品卖点/人群/情绪），再分叉为「视觉分支」与「旁白分支」，最后在**口播融合节点**合并。

**典型链路**：  
输入(产品图、URL、人群) → **分析节点 A**（产出 product_brief）→ 分支1：A→**UGC 描述 B**→**生图 D**→人物图；分支2：A→**脚本 C**→**TTS E**→音频。最后 **D 的输出 + E 的输出** → **图生口播 F**（imageAudioToVideo）→ 成片。

**要点**：A 的输出同时驱动视觉与文案，保证信息一致；融合只在最后一步；图像=身份锚点，脚本=说服层。

---

### 4.2 视频对口型（图→视频→对口型）

**适用**：需要先有人物动起来再对口型，对镜头运动与画面质量要求高。

**典型链路**：  
输入(达人画像、产品图、落地页) → **产品亮点提取 A** → 分支1：A→**UGC 描述 B**→**生图 D**→**图生视频 F**；分支2：A→**口播脚本 C**→**TTS E**→音频。**F 的视频 + E 的音频** → **videoLipSync G** → 最终口播视频。

**要点**：先锁定人物图（D），再动起来（F），最后对口型（G）；音频可单独换音色/语种，便于迭代。

---

### 4.3 图生对口型（图+音频直出，省节点）

**适用**：以速度与成本优先，不需要复杂镜头运动的口播。

**典型链路**：  
输入 → **分析 A** → 分支1：A→**描述 B**→**生图 D**；分支2：A→**脚本 C**→**TTS E**。**D 的图 + E 的音频** → **imageAudioToVideo F** → 成片（无中间 videoMaker）。

**要点**：少一层图生视频，更快更省；适合简单口播、高迭代；若需要强镜头语言则用 4.2。

---

### 4.4 组图场景（如亚马逊电商多图）

**适用**：一张产品图+文字描述 → 多张用途不同的商品图（主图、卖点、场景、细节等）。

**核心链路**：  
输入(产品图+产品描述) → **文本规划节点**（生成编号多图描述集，如 Image 01/02/03…）→ **Text Splitter**（按编号拆成单条）→ **按条生图**（每条对应一张图）→ 结果汇总/选择。

**要点**：每块一个图像目标，块内自洽；区分主图、卖点、场景、细节等职能；生图时可加相机/光影/写实类短语提升一致性。

---

## 五、模式选择速查

| 需求 | 推荐模式 |
|------|----------|
| 产品口播、要人物+叙事一致 | 4.1 或 4.2 |
| 要强镜头运动、高质量画面 | 4.2 视频对口型 |
| 快速出片、成本敏感、简单口播 | 4.3 图生对口型 |
| 多张商品图（主图/卖点/场景） | 4.4 组图 |

**通用原则**：先建共享语义层再分叉；视觉与文案同源；融合尽量放在最后一环；编号与一块一目标便于拆分与并行。
