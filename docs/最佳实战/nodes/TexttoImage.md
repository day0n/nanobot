# Text-to-Image – Block Knowledge

## Overview

The Text-to-Image block converts natural language descriptions into digital images.

It generates visuals based on a prompt describing the subject, environment, and style.  
Multiple models are available, each with different strengths and parameter controls.

---

## Input modality

| Modality | Description | Limitations |
|---|---|---|
| **Text (required)** | A natural language description of the image you want to generate | Keep prompts concise for better coherence |

---

## Output modality

| Modality | Description |
|---|---|
| **Image** | Generated image(s) in PNG, JPEG, or WEBP format |

---

## Available models and parameters

### Banana Pro 

**Strengths:**  
- Photorealistic imagery  
- High-resolution output  
- Accurate lighting and shadows  

#### Parameters

| Parameter | Options | Description |
|---|---|---|
| `aspect_ratio` | `1:1`, `2:3`, `3:2`, `3:4`, `4:3`, `4:5`, `5:4`, `9:16`, `16:9`, `21:9` | Controls image shape |
| `resolution` | `1K`, `2K`, `4K` | Controls output resolution |

#### Notes

- Resolution defines the **short side** of the image  
- Higher resolution → higher quality + longer generation time  

---

### Seedream 5.0 Lite

**Strengths:**  
- Stylized and fashion-forward visuals  
- Strong structure and layout reasoning  
- Good at rendering structured compositions  

#### Parameters

| Parameter | Options | Description |
|---|---|---|
| `image_size` | `square_hd`, `square`, `portrait_4_3`, `portrait_16_9`, `landscape_4_3`, `landscape_16_9`, `auto_2K`, `auto_3K` | Predefined layout and resolution |
| `enable_safety_checker` | true / false | Content safety filtering |

#### Notes

- Generation time: ~20–40s per image  

---

### GPT Image 1.5

**Strengths:**  
- Clean, prompt-faithful output  
- Strong for UI, graphics, and text-based visuals  
- Simple parameter system  

#### Parameters

| Parameter | Options | Description |
|---|---|---|
| `size` | `1024×1024`, `1536×1024`, `1024×1536`, `auto` | Output canvas size |
| `quality` | `low`, `medium`, `high`, `auto` | Controls fidelity and cost |
| `format` | `png`, `jpeg`, `webp` | Output file format |
| `background` | `transparent`, `opaque`, `auto` | Background type |

#### Notes

- Max resolution is limited compared to Banana Pro  
- Supports transparent backgrounds  

---

## Common use cases

- Product visuals  
- Social media images  
- Marketing creatives  
- Concept art  
- UI / graphic assets  

---

## Limitations

- Output quality varies by model  
- High resolution increases latency and cost  
- Some models have limited parameter flexibility  
- Safety filters may restrict certain outputs  

---

## Position in workflow

Text-to-Image is a core **visual generation block**, often used with:

- Image editing blocks (background edit, relight, etc.)  
- Image-to-video workflows  
- Content production pipelines  