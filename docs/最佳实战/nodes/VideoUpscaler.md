# Video Upscaler – Block Knowledge

## Overview

The Video Upscaler block enhances a video by **increasing its resolution and improving visual clarity**, while optionally adjusting frame rate for smoother playback.

It is designed as a **post-processing step**, allowing low- or medium-quality videos to be upgraded into high-definition outputs suitable for distribution, advertising, or presentation.

Unlike generative video blocks, this block focuses on **quality enhancement without altering content, motion, or structure**.

---

## Input modalities

| Modality | Description | Limits |
|---|---|---|
| **Video (required)** | The source video to be upscaled. | Clear input video recommended. Excessive compression or noise may reduce enhancement quality. |

---

## Output modality

| Modality | Description | Use cases |
|---|---|---|
| **Video** | A higher-resolution version of the original video with improved sharpness and detail. | HD export, ad delivery, content enhancement |

---

## Model

### Topaz (Video Upscaling Engine)

- Specialized for **video super-resolution and enhancement**
- Performs:
  - Detail reconstruction  
  - Noise reduction  
  - Edge sharpening  
  - Temporal consistency across frames  

- Maintains original motion and scene structure while improving clarity

---

## Parameters

### Core parameters

| Parameter | Options | Description |
|---|---|---|
| `upscale_factor` | `2x`, `3x`, `4x` | Multiplies video resolution. Higher values produce sharper, larger outputs. |
| `fps` | `16 – 60` (default `24`) | Controls output frame rate. Higher values result in smoother motion. |

---

## Resolution behavior

- Maximum supported output resolution: **4K (3840 × 2160)**
- Final resolution is determined by:
  - Input resolution  
  - Selected `upscale_factor`  
- If output exceeds 4K, it will be capped at the maximum limit

---

## Upscaling logic

The block performs:

- **Spatial upscaling**  
  Increases resolution frame-by-frame

- **Detail reconstruction**  
  Restores textures and edges using learned priors

- **Temporal smoothing**  
  Maintains consistency across frames to avoid flicker

- **Frame interpolation (via fps adjustment)**  
  Generates intermediate frames for smoother playback when increasing FPS

---

## Usage tips and best practices

1. **Use as final step**
   Apply after all video generation and editing is complete

2. **Choose factor based on use case**
   - `2x` → quick enhancement  
   - `3x` → standard HD upgrade  
   - `4x` → high-quality / near 4K output  

3. **Adjust FPS carefully**
   - `24 fps` → cinematic feel (default)  
   - `30 fps` → standard playback  
   - `60 fps` → ultra-smooth motion  

4. **Avoid over-upscaling low-quality input**
   Very noisy or compressed videos may produce artifacts

5. **Balance quality and performance**
   Higher resolution and FPS increase processing time

---

## Common use cases

- **Ad creative enhancement**
  Upgrade video quality before distribution

- **Social media content**
  Improve clarity for better engagement

- **UGC polishing**
  Enhance user-generated videos for professional use

- **Legacy video restoration**
  Improve older or low-resolution footage

- **Final export step in workflows**
  Ensure consistent output quality across all videos

---

## Pending technical details

* Output quality depends on input video clarity and compression level  
* High FPS interpolation may introduce motion artifacts in complex scenes  
* Processing time increases with resolution and duration  
* Future versions may support adaptive upscaling or region-specific enhancement  