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

## 4) 常见“连不上”原因

- 超过连接上限（例如 `videoMaker` 最多接 4 张图）。
- 少接了必需输入（例如 `videoLipSync` 必须同时有视频和音频）。
- 输入类型不匹配（例如把 `text` 接到 `image` 输入）。



## 7) 输出建议（agent 回复格式）

1. 目标：一句话复述  
2. 推荐链路：快速版 + 增强版  
3. 节点说明：每个节点一句话  
4. 最小改造补丁：`add_node/remove_node/reconnect/update_model`  
5. 操作提醒：避免连线类型错误、缺失必填输入、超连接上限

