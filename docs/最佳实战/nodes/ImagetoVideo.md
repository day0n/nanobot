# Image to Video – Block Knowledge

## Overview

The Image to Video block generates videos from a **static image**, transforming it into a dynamic scene with motion, camera movement, and optional audio.

Unlike Text to Video, this block uses the input image as the **visual anchor**, ensuring consistency in subject identity, composition, and style.

An optional text input can be provided to guide motion, camera behavior, or scene dynamics.

---

## Input Modalities

| Modality | Description | Limits |
|---|---|---|
| **Image (required)** | Base image used as the starting frame and visual reference | JPEG/PNG recommended, ≤10MB |
| **Text (optional)** | Optional control signal for motion, camera, or scene behavior | Keep concise |

---

## Output Modality

| Modality | Description | Use cases |
|---|---|---|
| **Video** | Generated video derived from the input image, with motion and optional audio | UGC ads, animation, cinematic shots |

---

## Model Selection

This block shares most models with Text to Video, with one additional motion-focused model:

### Sora 2
- High cinematic quality and motion realism  
- Supports **audio-visual synchronized output**  
- Strong for storytelling and smooth transitions  

### Veo 3.1 Fast
- Fast generation with stable motion  
- Supports **audio-visual synchronized output**  
- Good for iteration and short-form content  

### Kling 3.0 Standard / Kling 2.6 Pro
- Strong performance in **Chinese language and cultural context**  
- Flexible duration and control  
- Optional audio generation  

### Seedance 1.5 Pro
- Strong stylization and visual consistency  
- Performs well for controlled outputs  

### Hailuo Video 2.3 Pro
- Specialized in **camera movement and visual effects**  
- Strong performance in dynamic shots (zoom, pan, cinematic motion)  
- Ideal for expressive and stylized motion  

---

## Key Capabilities Comparison

| Capability | Supported Models |
|---|---|
| **Audio + video generation** | Sora 2, Veo 3.1, Kling (Standard with audio enabled) |
| **Chinese language performance** | Kling series, Seedance |
| **Camera motion & effects** | Hailuo Video 2.3 Pro |
| **Fast generation** | Veo 3.1 Fast |
| **Cinematic quality** | Sora 2 |

---

## Parameters

> Parameters are aligned with the Text to Video block.

### Common Parameters

| Parameter | Options | Description |
|---|---|---|
| `aspect_ratio` | `16:9`, `9:16`, `1:1`, etc. | Controls video framing |
| `duration` | e.g., `4s`, `5s`, `8s`, `12s`, `15s` | Length of the generated video |

---

### Model-Specific Parameters

#### Veo 3.1 Fast

| Parameter | Options | Description |
|---|---|---|
| `resolution` | `720p`, `1080p` | Output quality |
| `duration` | `4s`, `6s`, `8s` | Clip length |

---

#### Sora 2

| Parameter | Options | Description |
|---|---|---|
| `aspect_ratio` | `16:9`, `9:16` | Video format |
| `duration` | `8s`, `12s` | Clip length |

---

#### Kling 3.0 Standard / 2.6 Pro

| Parameter | Options | Description |
|---|---|---|
| `aspect_ratio` | `16:9`, `9:16`, `1:1` | Layout |
| `audio_mode` | `No Native Audio`, `Native Audio`, `Voice Control` | Audio generation control |
| `duration` | `3s – 15s` | Clip length |

---

#### Seedance 1.5 Pro

| Parameter | Options | Description |
|---|---|---|
| `aspect_ratio` | Multiple ratios | Framing |
| `resolution` | `480p`, `720p`, `1080p` | Quality |
| `duration` | `4s – 12s` | Clip length |

---

#### Hailuo Video 2.3 Pro

| Parameter | Options | Description |
|---|---|---|
| `aspect_ratio` | `16:9`, `9:16`, `1:1` | Video format |
| `duration` | Model-defined options | Clip length |

---

## Common Use Cases

- **Animate product images**  
  Add motion to static product visuals  

- **UGC video generation**  
  Turn influencer-style images into dynamic clips  

- **Cinematic shots from stills**  
  Generate camera movement from a single frame  

- **Ad creative iteration**  
  Produce multiple motion variations quickly  

- **Visual storytelling**  
  Bring illustrations or concept art to life  

---

## Limitations

- Motion consistency depends heavily on input image quality  
- Complex motion may reduce temporal stability  
- Audio quality varies by model  
- Most models generate **single-shot clips** (multi-shot requires chaining)  

---

## Role in Workflow

The Image to Video block acts as a **motion transformation layer**.

Typical integrations:

- ← Image Generator (base visual asset)  
- ← Text Generator (optional control signal)  
- → Editing / stitching (multi-shot workflows)  
- → Audio / voice generation (if not native)  
