# Text to Video – Block Knowledge

## Overview

The Text to Video block generates videos from natural language descriptions.

Users provide a **creative instruction** describing the story, characters, motion, visual style, and (optionally) audio. The block then produces a complete video clip.

This block is commonly used for **UGC ads, storytelling, product videos, and creative content generation**.

---

## Input Modalities

| Modality | Description | Limits |
|---|---|---|
| **Text (required)** | Natural language description of the video content, including subject, motion, style, and scene | Should remain concise and structured |

---

## Output Modality

| Modality | Description | Use cases |
|---|---|---|
| **Video** | Generated video clip with motion, composition, and optional audio | Ads, storytelling, social content, product demos |

---

## Model Selection

This block supports multiple video generation models, each optimized for different scenarios:

### Sora 2
- Strong cinematic quality and motion realism  
- Supports **audio-visual synchronized output**  
- Suitable for storytelling and high-quality scenes  

### Veo 3.1 Fast
- Faster generation with stable motion  
- Supports **audio-visual synchronized output**  
- Good balance between speed and quality  

### Kling 3.0 Standard / Kling 2.6 Pro
- Strong performance in **Chinese prompts and cultural context**  
- Supports longer duration and flexible control  
- Audio options available (Standard supports audio modes)  

### Seedance 1.5 Pro
- Strong **visual consistency and stylization**  
- Performs well with structured inputs  
- Good for stylized content and controlled outputs  

---

## Key Capabilities Comparison

| Capability | Supported Models |
|---|---|
| **Audio + video generation** | Sora 2, Veo 3.1, Kling (Standard with audio enabled) |
| **Chinese prompt performance** | Kling series, Seedance |
| **Fast generation** | Veo 3.1 Fast |
| **Cinematic quality** | Sora 2 |

---

## Parameters

### Common Parameters

| Parameter | Options | Description |
|---|---|---|
| `aspect_ratio` | `16:9`, `9:16`, `1:1`, etc. | Controls video framing and layout |
| `duration` | e.g., `4s`, `5s`, `8s`, `12s`, `15s` | Length of the generated video |

---

### Model-Specific Parameters

#### Veo 3.1 Fast

| Parameter | Options | Description |
|---|---|---|
| `resolution` | `720p`, `1080p` | Output video quality |
| `duration` | `4s`, `6s`, `8s` | Short-form video generation |

---

#### Sora 2

| Parameter | Options | Description |
|---|---|---|
| `aspect_ratio` | `16:9`, `9:16` | Output format |
| `duration` | `8s`, `12s` | Video length |

---

#### Kling 3.0 Standard / 2.6 Pro

| Parameter | Options | Description |
|---|---|---|
| `aspect_ratio` | `16:9`, `9:16`, `1:1` | Video layout |
| `audio_mode` | `No Native Audio`, `Native Audio`, `Voice Control` | Controls audio generation |
| `duration` | `3s – 15s` (Standard), fixed options for Pro | Clip length |

---

#### Seedance 1.5 Pro

| Parameter | Options | Description |
|---|---|---|
| `aspect_ratio` | `16:9`, `9:16`, `1:1`, etc. | Framing |
| `resolution` | `480p`, `720p`, `1080p` | Output quality |
| `duration` | `4s – 12s` | Video length |

---

## Common Use Cases

- **UGC ad generation**  
  Short-form marketing videos with natural motion  

- **Storytelling / narrative clips**  
  Cinematic sequences from text  

- **Product videos**  
  Demonstrate product usage in dynamic scenes  

- **Social media content**  
  TikTok / Reels style vertical videos  

- **Creative prototyping**  
  Quickly visualize ideas before production  

---

## Limitations

- Motion consistency may vary depending on prompt complexity  
- Audio quality depends on model and selected mode  
- Longer duration clips may reduce visual stability  
- Most models generate **single-shot clips** (multi-shot workflows require chaining)  

---

## Role in Workflow

The Text to Video block acts as the **execution layer** for motion content.

Typical integrations:

- ← Text Generator (scripts / scene descriptions)  
- → Editing / stitching (multi-shot composition)  
- → Audio / voice generation (if not native)  