# Video Modify – Block Knowledge

## Overview

The Video Modify block edits or extends an existing video clip based on a creative instruction.

It supports two primary modes:

- **Edit Shot** → Modify an existing video shot while preserving its core motion, timing, and structure
- **Next Shot** → Continue a given video clip into the next moment, generating a new follow-up shot based on the original footage and prompt

This block is designed for **shot-level video refinement and continuation**, making it useful for creative iteration, narrative expansion, and production-friendly video workflows.

---

## Input modalities

| Modality | Description | Limits |
|---|---|---|
| **Video (required)** | The source video used for editing or continuation. | Recommended input length: **3–10 seconds**. Clear motion and subject visibility improve results. |
| **Text (required)** | A creative instruction describing what to modify or how to continue the shot. | Be specific about subject, lighting, action, mood, or narrative continuation. |
| **Subject reference image (optional)** | An image used to preserve or guide subject appearance. | Use when identity consistency is important. |
| **Style reference image (optional)** | An image used to guide visual style, atmosphere, or scene language. | Use when visual consistency or stylization is important. |

> **Note:** The source video and prompt are required. Subject and style references are optional but strongly recommended when continuity matters.

---

## Output modality

| Modality | Description | Use cases |
|---|---|---|
| **Video** | A modified or extended video clip based on the original shot and instruction. | Shot revision, narrative continuation, iterative video production |

---

## Model selection

This block uses **Kling o3**.

### Kling o3

- Specialized for **video editing and continuation**
- Strong at:
  - Shot-level modification
  - Narrative continuation
  - Maintaining motion continuity
  - Preserving subject and style references
- Suitable for:
  - Revising an existing shot
  - Extending a scene into the next beat
  - Iterating on AI-generated video without restarting from zero

---

## Modes

### 1. Edit Shot

Modifies the existing source clip while keeping the original shot as the base.

#### Best for:
- Changing lighting
- Adjusting subject appearance
- Revising mood or atmosphere
- Tweaking action or scene elements
- Updating part of the plot without replacing the whole shot

#### Typical prompt examples:
- “Change the lighting to warm sunset tones while keeping the same camera movement.”
- “Keep the same scene, but make the character wear a black leather jacket.”
- “Turn this into a darker, cinematic night shot with neon reflections.”

---

### 2. Next Shot

Generates a new continuation shot based on the source clip and prompt.

#### Best for:
- Extending story progression
- Creating shot-to-shot continuity
- Generating the next narrative beat
- Building multi-shot scenes from short source clips

#### Typical prompt examples:
- “After this shot, the character turns around and starts running toward the train.”
- “Continue the scene with the product landing on a white studio table in slow motion.”
- “The next shot reveals the city skyline as the camera pulls back.”

---

## Parameters

### Core parameters

| Parameter | Options | Description |
|---|---|---|
| `mode` | `Edit Shot`, `Next Shot` | Determines whether the block edits the current shot or generates the next one. |
| `duration` | model-defined duration options (e.g. `5s`) | Controls the output clip length, especially relevant in **Next Shot** mode. |
| `keep_audio` | `on`, `off` | Determines whether the original audio should be preserved in the output. |

---

## Audio behavior

| Setting | Description |
|---|---|
| **Keep Audio = On** | Preserves the original audio track from the input video where supported by the edit. Useful when timing, speech, or ambient sound should remain consistent. |
| **Keep Audio = Off** | Outputs video without preserving the original audio. Useful when generating a silent continuation or planning to replace audio later. |

> **Note:** Audio continuity may depend on the type and extent of the video modification.

---

## Reference behavior

### Subject reference
Use a subject image when you want stronger identity preservation for a person, character, or object.

### Style reference
Use a style image when you want the output to follow a specific visual language, such as:
- cinematic realism
- anime
- editorial fashion
- product-commercial lighting
- fantasy / sci-fi scene tone

---

## Prompt structure guidance

For best results, prompts should clearly describe:

- **What should change or continue**
- **What should remain consistent**
- **Subject behavior or movement**
- **Scene atmosphere / lighting**
- **Narrative direction** (especially in Next Shot mode)

### Recommended structure

**Subject / Continuity** → **Action or Change** → **Environment / Lighting** → **Style / Tone**

#### Example:
“Keep the same woman and outfit, but change the scene to rainy nighttime street lighting with stronger reflections and a more cinematic mood.”

#### Next Shot example:
“Continue into the next shot: the same man opens the car door, steps out into the fog, and the camera slowly tracks backward.”

---

## Usage tips and best practices

1. **Be explicit about continuity**
   State what should remain unchanged: subject, outfit, camera style, environment, or tone.

2. **Use Edit Shot for controlled revision**
   Best when the current shot is mostly correct and only needs partial changes.

3. **Use Next Shot for progression**
   Best when the source clip should function as the first beat of a longer sequence.

4. **Keep prompts focused**
   Avoid trying to change subject, action, style, and plot all at once unless necessary.

5. **Use references when consistency matters**
   Subject and style images help reduce drift across revisions and continuations.

6. **Preserve audio only when needed**
   Keep audio on for continuity-sensitive edits; turn it off when creating a fresh visual continuation.

---

## Common use cases

- **Shot revision**
  Update lighting, subject details, props, or mood in an existing clip

- **Narrative continuation**
  Generate the next scene beat from a current shot

- **Ad video iteration**
  Quickly test alternative versions of the same core scene

- **Character consistency workflows**
  Keep the same subject while modifying visual details

- **Multi-shot sequence building**
  Turn short clips into longer structured video sequences

---

## Pending technical details

* Output continuity depends on source video clarity and motion stability
* Large changes in subject, environment, or camera logic may reduce consistency
* Audio preservation quality may vary depending on edit scope
* Future versions may support longer continuation chains or multi-shot planning