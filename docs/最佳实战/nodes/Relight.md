# Relight – Block Knowledge

## Overview

The Relight block is a specialized Image-to-Image component focused on **lighting transformation and control**.

It allows users to adjust the **direction, intensity, and color of light** on an existing image, while preserving the original subject and composition.

Unlike general Image-to-Image editing, Relight is designed for **physically coherent lighting adjustments**, making it ideal for product visuals, portraits, and commercial imagery.

---

## Input modalities

| Modality | Description | Limits |
|---|---|---|
| **Image (required)** | The source image to be relit. | JPEG/PNG recommended, ≤ 10 MB. Clear subject separation improves results. |

> **Note:** This block focuses on lighting transformation. It does not significantly alter object structure or composition.

---

## Output modality

| Modality | Description | Use cases |
|---|---|---|
| **Image** | The same image with modified lighting conditions. | Product relighting, portrait enhancement, mood adjustment |

---

## Model and parameters

This block is powered by **Banana Pro**, optimized for realistic rendering and physically accurate lighting.

---

### Core parameters

| Parameter | Type | Description |
|---|---|---|
| `horizontal` | 0° – 360° | Controls the horizontal direction of the light source. Determines where light comes from (left/right/front/back). |
| `vertical` | 0° – 180° | Controls the vertical angle of the light source. Higher values simulate top lighting; lower values simulate front or bottom lighting. |
| `brightness` | 0% – 100%+ | Controls light intensity. Higher values produce stronger highlights and contrast. |
| `color` | HEX (e.g., `#FFB6E6`) | Defines the color temperature or tint of the light source. |

---

### Output settings (Banana Pro)

| Parameter | Options | Notes |
|---|---|---|
| `aspect_ratio` | `1:1`, `2:3`, `3:2`, `3:4`, `4:3`, `4:5`, `5:4`, `9:16`, `16:9`, `21:9` | Controls framing of the final image. |
| `resolution` | `1K`, `2K`, `4K` | Controls output detail level. Higher resolution yields sharper lighting effects. |

---

## Lighting control logic

Relight simulates a **virtual light source in 3D space**:

- **Horizontal angle** → rotates light around the subject (left ↔ right)
- **Vertical angle** → changes elevation (top light ↔ front light ↔ bottom light)
- **Brightness** → adjusts intensity and shadow contrast
- **Color** → controls mood and temperature (warm, cool, stylized)

These parameters work together to create consistent and realistic lighting changes.

---

## Usage tips and best practices

1. **Start with neutral lighting**
   Begin with moderate brightness and neutral color before exploring extremes.

2. **Use horizontal + vertical together**
   Lighting direction feels natural only when both axes are balanced.

3. **Match lighting to context**
   - Top lighting → premium/product look  
   - Side lighting → dramatic/contrast  
   - Front lighting → clean/commercial  

4. **Use color for mood**
   - Warm tones → lifestyle / cozy  
   - Cool tones → tech / futuristic  
   - Colored lights → creative / editorial  

5. **Avoid overexposure**
   Extremely high brightness can wash out details.

---

## Common use cases

- **Product photography relighting**  
  Simulate studio lighting without reshooting

- **Portrait enhancement**  
  Adjust facial lighting for better depth and clarity

- **Ad creative optimization**  
  Test different lighting moods for performance

- **E-commerce image refinement**  
  Improve consistency across product listings

- **Mood transformation**  
  Shift lighting tone for different brand aesthetics

---

## Pending technical details

* Extreme lighting changes may introduce artifacts depending on the input image  
* Results depend on the clarity of subject-background separation  
* Future versions may support multiple light sources or advanced lighting presets  