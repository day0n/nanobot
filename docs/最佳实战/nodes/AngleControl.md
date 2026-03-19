# Angle Control – Block Knowledge

## Overview

The Angle Control block is an Image-to-Image component designed to control the **camera viewpoint relative to a subject**.

It allows users to reposition the virtual camera in 3D space—changing how the subject is seen—while preserving identity, structure, and overall scene consistency.

Unlike general editing, Angle Control focuses specifically on **viewpoint transformation**, making it ideal for creating multiple perspectives of the same subject.

---

## Input modalities

| Modality | Description | Limits |
|---|---|---|
| **Image (required)** | The source image containing the subject to be viewed from different angles. | JPEG/PNG recommended, ≤ 10 MB. Clear subject structure improves consistency. |

> **Note:** This block changes the viewing angle, not the core identity of the subject. Extreme angle shifts may introduce variation.

---

## Output modality

| Modality | Description | Use cases |
|---|---|---|
| **Image** | A new version of the image rendered from a different camera perspective. | Multi-angle generation, product visualization, perspective exploration |

---

## Parameters

### Core camera controls

| Parameter | Range | Description |
|---|---|---|
| `horizontal_angle` | 0° – 360° | Rotates the camera around the subject horizontally. Controls left/right viewpoint (orbit). |
| `vertical_angle` | 0° – 180° | Controls camera elevation. Lower values = front/eye-level; higher values = top-down view. |
| `zoom` | continuous (e.g., 1.0 – 10.0) | Controls camera distance. Higher values zoom in; lower values zoom out. |

---

## Camera control logic

Angle Control simulates a **virtual orbit camera system**:

- **Horizontal angle** → rotates around the subject (front → side → back)
- **Vertical angle** → moves camera up/down (eye-level → top-down)
- **Zoom** → adjusts distance and framing

Together, these parameters define the **camera position in 3D space**, enabling consistent viewpoint changes.

---

## Usage tips and best practices

1. **Start from a clear front view**
   The more centered and clean the original image, the better the transformation.

2. **Use horizontal rotation for variation**
   Small angle changes (15°–45°) work well for realistic multi-angle outputs.

3. **Control vertical angle carefully**
   - Low angle → more natural perspective  
   - High angle → top-down / product showcase  

4. **Use zoom to refine framing**
   Adjust zoom after setting angle to maintain composition quality.

5. **Avoid extreme combinations**
   Large angle + high zoom may distort results.

---

## Common use cases

- **Product multi-angle generation**  
  Create front, side, and perspective views from a single product image

- **E-commerce visualization**  
  Generate consistent angles for product listings

- **Creative direction testing**  
  Explore different viewpoints for the same subject

- **Character perspective variation**  
  Maintain identity while changing viewpoint

- **Ad creative iteration**  
  Test framing and angles for better performance

---

## Pending technical details

* Large viewpoint shifts may reduce structural consistency  
* Output quality depends on clarity of subject geometry in the input image  
* Future versions may support multi-view batch generation or camera presets  