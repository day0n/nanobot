# Image to Image – Block Knowledge

## Overview

The Image to Image block transforms an existing image into a new visual output based on a creative instruction.

Unlike Text-to-Image, this block starts from a **reference image**, allowing users to preserve structure, composition, or subject identity while modifying style, details, or visual elements.

It is commonly used for **style transfer, variation generation, editing, and enhancement**, making it a key component in iterative creative workflows.

---

## Input modalities

| Modality | Description | Limits |
|---|---|---|
| **Image (required)** | The source image used as the base for transformation. | JPEG/PNG recommended, ≤ 10 MB. |
| **Text (required)** | Instruction describing how to transform the image. | — |

> **Note:** The output is guided by both the input image and the instruction. If the instruction conflicts heavily with the image, results may vary.

---

## Output modality

| Modality | Description | Use cases |
|---|---|---|
| **Image** | A transformed version of the input image. | Editing, variation generation, enhancement |

---

## Model selection and parameters

This block supports multiple image models. Each model exposes different parameters.

---

### Banana Pro

**Strengths:**  
Photorealistic transformation and high-fidelity editing.

#### Parameters

| Parameter | Options | Description |
|---|---|---|
| `aspect_ratio` | `1:1`, `2:3`, `3:2`, `3:4`, `4:3`, `4:5`, `5:4`, `9:16`, `16:9`, `21:9` | Controls output framing |
| `resolution` | `1K`, `2K`, `4K` | Controls output resolution |

---

### Seedream 5.0 Lite

**Strengths:**  
Stylized, fashion-forward, and design-oriented transformations.

#### Parameters

| Parameter | Options | Description |
|---|---|---|
| `image_size` | `square_hd`, `square`, `portrait_4_3`, `portrait_16_9`, `landscape_4_3`, `landscape_16_9`, `auto_2K`, `auto_3K` | Controls layout and resolution |

---

### GPT Image 1.5

**Strengths:**  
Controlled edits and structured visual outputs.

#### Parameters

| Parameter | Options | Description |
|---|---|---|
| `size` | `1024×1024`, `1536×1024`, `1024×1536`, `auto` | Output dimensions |
| `quality` | `low`, `medium`, `high` | Rendering quality |
| `background` | `transparent`, `opaque`, `auto` | Background type |

---

## Key transformation patterns

The Image to Image block supports the following transformation types:

- **Style transfer**  
- **Content modification**  
- **Enhancement**  
- **Variation generation**  
- **Recomposition**

---

## Common use cases

- Product image refinement  
- UGC quality enhancement  
- Visual variation generation  
- Character consistency workflows  
- Ad creative iteration  

---

## Limitations

- Output quality depends on input image quality  
- Different models vary in controllability  
- Complex transformations may produce inconsistent results  
- Model interpretation of instructions may vary  

---

## Position in workflow

Image to Image is a core **image transformation block**, commonly used with:

- Text-to-Image (as base generation → refinement)  
- Image editing pipelines  
- Video generation workflows  
- Content iteration loops  