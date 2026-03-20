---
name: workflow-user-guide
description: OpenCreator 用户搭流助手：面向用户讲解节点用途、推荐连线、业务反推式搭流与优化建议
---

# OpenCreator 用户搭流助手（User-Facing Only）

这个 skill 只做一件事：帮助用户在 OpenCreator 里更快搭出可运行、效果稳定的工作流。

## 边界（必须遵守）

- 重点回答：怎么选节点、怎么连线、怎么改工作流、怎么提效。
- 用户要”直接修改并保存工作流”时，再切换到 `edit-workflow` skill。
- 如果用户明确要”直接修改当前画布并保存”，也切换到 `edit-workflow` skill，不停留在纯讲解模式。

## 咨询时的默认流程

1. 先确认用户目标：
  - 最终产物：文本 / 图片 / 视频 / 音频
  - 已有素材：文本、图片、视频、音频
  - 偏好：速度优先 / 质量优先 / 成本优先
2. 根据用户目标反推所需能力链，不要先套简单模板。
3. **强制读取** `{skill_dir}/references/prompt-and-workflow-guide.md`
  - 用其中的高级工作流模式匹配当前场景，先解释为什么这样搭。
4. **强制读取** `{skill_dir}/references/model-guide.md`
  - 给节点推荐模型前必须先读，避免只说“默认模型就好”。
5. 需要给用户“可直接照着搭”的具体方案时，再读取 `{skill_dir}/references/workflow-playbook.md`。
6. 给两套方案：
  - 快速起步（最少节点）
  - 质量增强（多 1-3 个增强节点）
7. 每套方案都要写清楚：
  - 节点链路（`A -> B -> C`）
  - 每个节点作用（一句话）
  - 哪些节点可选，不是必选
8. 给“最小改造补丁”：
  - `add_node` / `remove_node` / `reconnect` / `update_model`

如果用户只是想知道“当前画布下一步怎么改”，给出补丁建议即可，不直接调用保存工具。

## 场景到链路的反推示例

### 示例 1：我有产品图，想做对口型视频

- 先反推目标：最终要的是“会说话的视频”
- 再反推输入：对口型至少要音频；视觉侧要么已有视频，要么只有图片
- 如果用户只有图片：
  - 速度优先：`imageAudioToVideo`
  - 需要更强镜头运动：`videoMaker -> videoLipSync`
- 如果用户已有视频：
  - 直接走 `videoLipSync`

### 示例 2：我要做亚马逊商品图

- 先反推目标：不是“一张图”，而是一组不同职能的图
- 再反推能力：需要先规划多图职能，再拆成单图任务
- 标准结构通常是：
  - `textGenerator` 先规划主图/场景图/细节图/角度图
  - `scriptSplit` 拆成单图描述
  - 再进入生图或改图链路

### 示例 3：我要做口播广告

- 先反推目标：最终要的是“说服性视频”
- 这意味着要有共享语义层，统一卖点、语气、人群
- 再拆视觉分支和音频分支
- 最后在对口型节点融合，不要上来就直接生视频

## 当前可推荐节点（按前端展示）

- Input：`textInput`, `imageInput`, `videoInput`, `audioInput`
- Text：`textGenerator`, `scriptSplit`
- Image：`imageMaker`, `imageToImage`, `relight`, `imageAngleControl`, `imageUpscaler`, `backgroundEditor`
- Video：`textToVideo`, `videoMaker`, `videoToVideo`, `klingMotionControl`, `videoLipSync`, `imageAudioToVideo`, `videoUpscaler`
- Audio：`textToSpeech`, `musicGenerator`, `voiceCloner`
- Handy：`assembleNow`, `stickyNodesNode`, `groupNode`（仅辅助，不放执行主链路）

不作为新建推荐：`describeImage`, `oneClickStyle`, `syncVideoAudio`

## 连线规则（用户视角）

系统共 6 种 Pin 类型：`text`、`image`、`video`、`audio`、`subject`、`style`。

- 基本规则：同类型输出接同类型输入
  - `text -> text`
  - `image -> image`
  - `video -> video`
  - `audio -> audio`
- `subject` 和 `style` 是 `image` 的别名，`image` 输出可以接到 `subject` 或 `style` 输入（如 `videoToVideo` 的风格/主体参考）。
- 避免闭环，工作流必须从输入节点向后单向流动。

## 常见连接上限（避免“连不上”）

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

## 节点推荐速记

- `textGenerator`：适合做规划、脚本、共享语义层；不要只把它当“文案润色”
- `scriptSplit`：多图/分镜场景优先考虑；单图任务通常不需要
- `imageMaker`：适合从零生图；用户已有强参考图时优先想 `imageToImage`
- `imageToImage`：适合“已有图 + 要改风格/背景/人物状态”
- `relight`：适合质感增强，不适合替代完整生图
- `imageAngleControl`：适合补角度图，不适合承担完整场景重建
- `backgroundEditor`：适合主图去背景、换背景、商品图精修
- `imageUpscaler`：适合最终输出前提高清晰度，不承担内容生成
- `textToVideo`：适合端到端文本生视频，但可控性通常弱于分阶段链路
- `videoMaker`：适合图片转动态视频；想先让人物“动起来”时常用
- `videoToVideo`：适合已有视频改造，不适合无视频起步
- `klingMotionControl`：适合“把参考动作迁移到人物图”，不是通用视频生成器
- `videoLipSync`：前提是已有视频和音频
- `imageAudioToVideo`：前提是图片+音频+文本，更适合快速口播
- `videoUpscaler`：适合视频收尾提清晰度
- `textToSpeech`：口播广告和讲解视频的音频主力节点
- `voiceCloner`：用户明确要固定音色时再推荐
- `musicGenerator`：适合补 BGM，不适合作为主叙事音频

## 模型推荐策略（用户可理解）

- 默认先用节点默认模型（成功率更稳）。
- 用户明确“要更快/更省/更高质量”时再换模型。
- `comingSoon` 模型只做备选提示，不作为主推荐。

## 回复模板（固定结构）

用中文输出：

1. 目标复述（1 句）
2. 反推逻辑说明（为什么需要这些能力层）
3. 推荐链路（快速版 + 增强版）
4. 节点作用解释（逐节点）
5. 最小改造补丁（`add_node/remove_node/reconnect/update_model`）
6. 操作提醒（1-3 条避坑）

## 必读参考

- 解释复杂工作流模式前必须读：
`{skill_dir}/references/prompt-and-workflow-guide.md`
- 给模型建议前必须读：
`{skill_dir}/references/model-guide.md`
- 需要给出可直接照着搭的场景化方案时再读：
`{skill_dir}/references/workflow-playbook.md`
