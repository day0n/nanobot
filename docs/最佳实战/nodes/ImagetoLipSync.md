# Image to Lip Sync – Block Knowledge

## Overview

The Image to Lip Sync block generates a talking video from a **single image and a speech audio input**.

It animates the character in the image, synchronizing mouth movements with the provided audio to produce a realistic speaking video.

Compared to Video to Lip Sync, this block requires **no source video**, making it ideal for turning static images into expressive, speaking characters.

This block is commonly used for **AI avatars, UGC ads, talking portraits, and content localization**.

---

## Input modalities

| Modality | Description | Limits |
|---|---|---|
| **Image (required)** | A character image with a clearly visible face and mouth region. | Frontal or semi-frontal faces recommended. Clear facial structure improves quality. |
| **Audio (required)** | Speech audio that drives lip movement. | Recommended ≤ **30 seconds** for better speed and stability. |
| **Text (required)** | Instruction describing expression, style, or performance (e.g., emotion, tone, acting). | Helps guide facial animation and overall delivery. |

> **Note:** The image defines *who speaks*, and the audio defines *what is being said*.

---

## Output modality

| Modality | Description | Use cases |
|---|---|---|
| **Video** | A generated talking video where the character speaks the input audio. | AI avatar, ads, talking portraits |

---

## Model

### Infinite Talk

- Specialized for **image-driven facial animation and lip sync**
- High-quality **lip synchronization and facial realism**
- Supports subtle expression control via prompt
- Generates natural head movement and speaking dynamics

> **Note:** This model prioritizes quality and realism, which may result in **longer generation time** compared to video-based lip sync methods.

---

## Parameters

This block focuses on **content-driven control**, with minimal explicit parameters.

---

## Lip sync & animation logic

The block performs:

- **Facial reconstruction**
  Builds a dynamic facial representation from the static image

- **Phoneme alignment**
  Maps speech audio to mouth shapes and timing

- **Expression synthesis**
  Generates facial expressions based on audio and optional prompt

- **Micro-movements**
  Adds subtle head, eye, and facial motion for realism

---

## Usage tips and best practices

1. **Use clear face images**
   High-resolution, front-facing portraits produce the best results

2. **Avoid occlusions**
   Hair, hands, or objects covering the mouth reduce accuracy

3. **Use prompts for acting control**
   Example:
   - “confident and energetic tone”
   - “soft and emotional delivery”
   - “professional and calm expression”

4. **Keep audio concise**
   ≤ 30 seconds recommended for faster generation and stability

5. **Match expression with audio**
   The more aligned the tone, the more natural the result

6. **Expect slower generation**
   Higher realism comes with longer processing time

---

## Common use cases

- **AI avatar videos**
  Turn a single image into a speaking character

- **UGC ad production**
  Generate talking-head style marketing videos without filming

- **Content localization**
  Reuse the same visual with different languages

- **Talking portraits**
  Animate characters, influencers, or fictional personas

- **Script iteration**
  Rapidly test different voiceovers with the same visual

---

## Comparison with Video to Lip Sync

| Feature | Image to Lip Sync | Video to Lip Sync |
|---|---|---|
| Input | Image + audio | Video + audio |
| Realism | Higher facial generation flexibility | Higher structural consistency |
| Speed | Slower | Faster |
| Control | Expression via prompt | Expression inherited from video |
| Use case | Avatar generation | Editing existing footage |

---

## Pending technical details

* Generation time increases with audio length  
* Facial realism depends on input image quality  
* Extreme expressions may reduce stability  
* Future versions may support emotion presets or batch avatar generation  