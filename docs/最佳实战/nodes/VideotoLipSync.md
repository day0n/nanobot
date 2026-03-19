# Video to Lip Sync – Block Knowledge

## Overview

The Video to Lip Sync block generates a new video where a character’s mouth movements are synchronized to a given audio track.

It takes a **source video (with a visible face)** and a **speech audio input**, then produces a video where the character appears to speak the provided audio naturally.

This block is commonly used for **UGC ads, avatar speaking videos, dubbing, localization, and content personalization**.

---

## Input modalities

| Modality | Description | Limits |
|---|---|---|
| **Video (required)** | A video containing a clearly visible face and mouth region. | Clear frontal or semi-frontal face recommended. Stable head movement improves sync quality. |
| **Audio (required)** | The speech audio to drive lip movement. | Recommended ≤ **30 seconds** for faster and more stable generation. |

> **Note:** The video defines *who speaks*, and the audio defines *what is being said*.

---

## Output modality

| Modality | Description | Use cases |
|---|---|---|
| **Video** | A lip-synced video where the subject speaks the input audio. | UGC ads, dubbing, avatar videos |

---

## Model

### Pixverse Lipsync

- Specialized for **lip synchronization and facial animation**
- Aligns mouth movement with speech timing and phonemes
- Preserves facial identity and overall video structure
- Suitable for both realistic and stylized characters

---

## Parameters

### Core parameters

| Parameter | Options | Description |
|---|---|---|
| `video_fill_mode` | `Ping Pong` | Extends or loops the source video to match the audio duration |

---

## Aspect ratio behavior

- The output video **inherits the aspect ratio of the input video**
- Aspect ratio **cannot be modified** in this block
- To change aspect ratio, preprocess the video using other blocks before lip sync

---

## Video Fill Mode

### Ping Pong

- Loops the source video forward and backward
- Ensures final video duration matches the input audio length
- Maintains smooth temporal continuity without abrupt cuts

#### When to use:
- Audio is longer than the input video  
- Want seamless looping behavior  
- Need consistent output duration  

---

## Lip sync logic

The block performs:

- **Facial region detection**  
  Identifies mouth and key facial landmarks

- **Phoneme alignment**  
  Maps audio speech patterns to mouth shapes

- **Temporal synchronization**  
  Aligns lip motion frame-by-frame with audio timing

- **Video extension (if needed)**  
  Uses Ping Pong mode to match audio duration

---

## Usage tips and best practices

1. **Use clear face videos**
   Frontal or slightly angled faces work best

2. **Avoid occlusions**
   Hands, objects, or shadows covering the mouth reduce accuracy

3. **Keep audio clean**
   Clear speech improves lip sync precision

4. **Control audio length**
   ≤ 30 seconds recommended for better performance and speed

5. **Match tone and expression**
   Neutral or expressive base videos work better than highly dynamic ones

6. **Use Ping Pong for duration matching**
   Especially when the source video is shorter than the audio

---

## Common use cases

- **UGC ad generation**
  Turn static talking-head videos into scripted ad content

- **Dubbing and localization**
  Replace original speech with different languages

- **AI avatar videos**
  Create speaking characters from base footage

- **Content personalization**
  Generate multiple variants of the same video with different scripts

- **Marketing videos**
  Quickly iterate on messaging without reshooting footage

---

## Pending technical details

* Lip sync accuracy depends on face visibility and audio clarity  
* Extreme head movement may reduce synchronization quality  
* Emotion mismatch between video and audio may affect realism  
* Future versions may support emotion-aware lip sync or full facial animation  