# OpenCreator 用户搭流手册

此文档用于给用户提供“可直接照着搭”的指导

## 1) 先问清楚的 5 个问题

1. 你最终要产出什么：文本、图片、视频还是音频？
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

说明：Handy 节点用于组织工作，不建议放在自动执行主链路里。

## 3) 连线规则（简化版）

- 只连同类：
  - `text -> text`
  - `image -> image`
  - `video -> video`
  - `audio -> audio`
- `videoToVideo` 的 `subject/style` 可以接图片。
- 建议从左到右单向连线，不要回连到上游节点。

## 4) 常见“连不上”原因

- 超过连接上限（例如 `videoMaker` 最多接 4 张图）。
- 少接了必需输入（例如 `videoLipSync` 必须同时有视频和音频）。
- 输入类型不匹配（例如把 `text` 接到 `image` 输入）。

## 5) 场景模板（可直接复用）

### A. 快速文生图
- 链路：`textInput -> imageMaker`
- 适用：海报、封面、产品概念图

### B. 快速文生视频
- 链路：`textInput -> textToVideo`
- 适用：概念片、短广告草稿

### C. 图生视频（更可控）
- 链路：`textInput -> imageMaker -> videoMaker`
- 适用：先定画面风格，再做动效

### D. 分镜叙事视频
- 链路：`textInput -> textGenerator -> scriptSplit -> imageMaker -> videoMaker`
- 适用：剧情短片、分镜展示

### E. 视频改造升级
- 链路：`videoInput + textInput -> videoToVideo -> videoUpscaler`
- 适用：老片风格重做、画面清晰度提升

### F. 真人视频配音口播
- 链路：`textInput -> textToSpeech`，`videoInput + audio -> videoLipSync`
- 适用：讲解视频、多语言口播

### G. 图片数字人口播
- 链路：`textInput -> textToSpeech`，`imageInput + audio + text -> imageAudioToVideo`
- 适用：虚拟主播、商品讲解人像

### H. 商品图精修
- 链路：`imageInput -> backgroundEditor -> relight -> imageUpscaler`
- 适用：电商主图、详情页图

## 6) 推荐策略（给用户解释时）

- 快速版：节点少、先跑通。
- 增强版：在快速版上加 1-3 个增强节点（打光/角度/高清化/口型同步）。
- 用户没特别要求时，优先推荐默认模型，保证稳定。

## 7) 输出建议（agent 回复格式）

1. 目标：一句话复述  
2. 推荐链路：快速版 + 增强版  
3. 节点说明：每个节点一句话  
4. 最小改造补丁：`add/remove/reconnect/update_model`  
5. 操作提醒：避免连线类型错误、缺失必填输入、超连接上限
