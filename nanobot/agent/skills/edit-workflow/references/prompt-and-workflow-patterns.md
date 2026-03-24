# Prompt 模板与工作流结构模板（构建用）

本文件包含关键业务链路模板。`create-workflow` 在搭建任何非平凡工作流前，必须先读取本文件第四章的高级工作流结构模板，再决定最终链路。

本文件供 **create-workflow** 在需要填写 `inputText` 或搭建复杂工作流结构时使用。包含结构化文字脚本规则、生图/生视频 prompt 模板与预设词库、4 个高级工作流结构模板（节点类型 + 连线 + IO）。

---

## 一、结构化文字脚本规则

### 1.1 输出格式要求

- 只输出结果，不输出解释、推理、「下面给出」等过渡语。
- 编号分块：每块对应一个执行目标（一图一镜），单块 ≤1500 中文字符；便于 scriptSplit 切割与下游并行执行。
- 一块一目标：一个图像描述=一张图，一个镜头描述=一个镜头。
- 块内自洽：每块可独立使用，不写「同上」「同上文」。

### 1.2 角色与 Master 指令模板

生成前为文本节点设定角色，格式示例：

```
你是 [具体角色]。任务是 [具体任务]。直接输出 [格式]。不解释、不赘述。每块不超过 1500 字。
```

**多图集（如亚马逊 listing）**：  
「你是专业亚马逊 listing 视觉设计师。任务是生成编号多图描述集供下游生图。每图标为 Image 01、Image 02…。每块自洽且仅描述一个图像目标。不解释不赘述，直接输出。每块不超过 1500 字。」

**分镜/镜头表**：  
「你是专业分镜师与商业片视觉策划。任务是生成编号分镜。每镜标为 Shot 01、Shot 02…。每镜仅描述一个画面时刻。不解释不赘述，直接输出。每块不超过 1500 字。」

**视频脚本逆向（JSON）**：  
「你是广告脚本分析师与短视频策略师。任务是分析参考视频并输出结构化 JSON 脚本。每场有 scene_id。分离 visual_description、dialogue、camera、editing_notes。不解释不赘述，直接输出。」

### 1.3 编号与拆分友好格式

- 使用稳定编号：`Image 01`、`Shot 01`、`Scene 01`。
- 若下游接 scriptSplit，严格按编号拆分，每块自洽。

---

## 二、生图 Prompt 模板与预设词库

### 2.1 结构模板（可填入 inputText）

```
[构图/景别]，[相机与镜头]，[光影与氛围]，[视觉效果/质感]，[风格/渲染]，[画质/比例]
```

示例（写实）：  
「三分法构图，35mm 镜头浅景深，柔和自然光黄金时刻，胶片颗粒与尘埃质感，电影感写实，2K 16:9」

### 2.2 预设词库（按模块，可直接拼接）

- **构图**：rule of thirds, eye-level shot, close-up, medium shot, wide shot, candid moment
- **镜头**：35mm lens, 50mm lens, 85mm portrait lens, shallow depth of field, macro lens, DSLR
- **光影**：soft natural daylight, golden hour sunlight, high-contrast cinematic lighting, studio softboxes, backlit silhouette, low-key moody lighting
- **质感**：photorealistic texture, film grain, dust particles, lens flare, bokeh
- **风格**：photorealistic, cinematic film look, fashion editorial, anime style, minimalist, UGC handheld style

生图节点（imageMaker/imageToImage）的 `inputText` 可直接使用上述模板与词库组合。

---

## 三、生视频 Prompt 模板与预设词库

### 3.1 结构模板

```
[相机与镜头]，[运动/物理]，[光影与氛围]，[视觉效果]，[风格/渲染]
```

一镜头=一个主动作+一个机位+一种光影。示例：  
「slow push-in, 35mm lens, leans forward slightly, golden hour lighting with soft shadows, dust particles in sunlight, cinematic film look」

### 3.2 预设词库

- **机位**：slow push-in, slow pull-out, pan left, pan right, tracking shot, static shot, close-up, medium shot, wide shot, low angle, eye-level
- **镜头**：16mm/35mm/50mm/85mm lens, shallow depth of field
- **运动**：leans forward slightly, hair moves with wind, fabric reacts to motion, hand gestures emphasize speech
- **光影**：soft natural daylight, golden hour light, high contrast cinematic lighting, neon lighting, diffused studio lighting
- **风格**：cinematic film look, photorealistic, UGC handheld style, fashion editorial, film grain

多镜头（如 Sora 2）可按时段分镜：`[00:00–00:03] Hook`、`[00:03–00:06] Build`、`[00:06–00:09] Peak`、`[00:09–00:12] Resolution`，每段一个动作+一个机位+一种光影。

---

## 四、高级工作流结构模板

### 4.1 UGC 口播广告（共享语义层 + 图生口播）

**输入**：产品图(image)、产品 URL(text)、目标人群(text)。

**节点与连线**：

- A `textGenerator`：输入 product_url + target_audience → 输出 product_brief（痛点/卖点/情绪）。
- B `textGenerator`：输入 product_brief + product_image + target_audience → 输出 ugc_image_prompt。
- C `textGenerator`：输入 product_brief + target_audience → 输出 script。
- D `imageMaker` 或 `imageToImage`：输入 product_image + ugc_image_prompt → 输出 character_image。
- E `textToSpeech`：输入 script → 输出 audio。
- F `imageAudioToVideo`：输入 character_image + audio + script（或节点 inputText）→ 输出 final_video。

**依赖**：B、C 依赖 A；D 依赖 B；E 依赖 C；F 依赖 D、E。边：A→B，A→C，A+图+人群→B，图+B→D，A+人群→C，C→E，D+E+文本→F。

### 4.2 视频对口型（图→视频→对口型）

**输入**：达人画像描述(text)、产品图(image)、落地页(text)。

**节点与连线**：

- A `textGenerator`：产品亮点提取 → product_brief。
- B `textGenerator`：UGC 视觉描述 → ugc_image_prompt（输入 A + 图 + 描述）。
- C `textGenerator`：口播脚本 → script（输入 A）。
- D `imageMaker`/`imageToImage`：输入 图 + B 输出 → influencer_image。
- E `textToSpeech`：输入 C 输出 → voice_audio。
- F `videoMaker`：输入 D 输出 + 可选 motion 文本 → base_video。
- G `videoLipSync`：输入 F 输出 + E 输出 → final_lip_sync_video。

**依赖**：B、C 依赖 A；D 依赖 B；E 依赖 C；F 依赖 D；G 依赖 F、E。

### 4.3 图生对口型（图+音频直出）

**输入**：同上，但不需要中间视频。

**节点**：A 分析 → B 描述 → C 脚本；D 生图（图+B）；E TTS（C）；F `imageAudioToVideo`（D 的图 + E 的音频 + 台词）。无 videoMaker、无 videoLipSync。

**依赖**：B、C 依赖 A；D 依赖 B；E 依赖 C；F 依赖 D、E。

### 4.4 组图（亚马逊风多图）

**输入**：产品图(image)、产品描述(text)。

**节点与连线**：

- A `textGenerator`：角色「亚马逊 listing 视觉设计师」，输出编号多图描述（Image 01、Image 02…），每块一图、自洽。
- B `scriptSplit`：输入 A 输出，按编号拆成单条。
- C 多个 `imageMaker`（或单节点多次执行）：每条 B 输出对应一张图；可共用同一 selectedModels，每条 prompt 独立。

**依赖**：B 依赖 A；各 C 依赖 B 对应条。连线：A→B；B 各条→各 C。结果汇总为多张图，供选择/下载。

---

## 五、建图时注意

- 所有边的 `sourceHandle`/`targetHandle` 需类型兼容（text→text, image→image 等）；subject/style 视为 image。
- 遵守 node-configs 中的连接上限（如 scriptSplit.text=1，imageUpscaler.image=1，videoLipSync.video=1 且 audio=1）。
- 建边前校验：无自连、类型兼容、目标 Pin 未超限、无环。
- 需要选模型时查阅本 skill 的 `model-guide.md`，按节点类型填写 `selectedModels` 的 API ID。
