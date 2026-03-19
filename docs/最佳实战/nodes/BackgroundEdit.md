# Background Edit – Block Knowledge

## Overview

The Background Edit block is an Image-to-Image component designed to **modify or remove the background of an image while preserving the main subject**.

It supports two modes:

- **Change Background** → Replace the existing background with a new one based on a text instruction  
- **Remove Background** → Isolate the subject by removing the background entirely  

This block is commonly used in **e-commerce, advertising, and visual content production workflows**.

---

## Input modalities

| Modality | Description | Limits |
|---|---|---|
| **Image (required)** | The source image containing a clear foreground subject. | JPEG/PNG recommended, ≤ 10 MB. Clear subject-background separation improves results. |
| **Text (optional, Change BG only)** | A natural language instruction describing the desired background. | Keep concise and descriptive (e.g., “minimal white studio”, “sunset beach”, “modern living room”). |

---

## Output modality

| Modality | Description | Use cases |
|---|---|---|
| **Image** | The edited image with background replaced or removed. | Product images, marketing visuals, compositing |

---

## Modes

### 1. Change Background

Replaces the original background with a new one generated from a text description.

#### Behavior

- Detects and preserves the **main subject**
- Generates a new background based on the **creative instruction**
- Adjusts lighting, color, and perspective for better blending

#### Best practices

- Be specific with environment descriptions  
  → “clean white studio with soft shadows”  
  → “warm sunset beach with golden light”

- Match scene context  
  → Product → studio / lifestyle  
  → Character → environment / narrative  

- Avoid overly complex prompts  
  Keep background description focused

---

### 2. Remove Background

Removes the background and outputs the subject on a transparent or plain background.

#### Behavior

- Segments the subject from the background
- Removes surrounding environment
- Keeps edges as clean as possible

#### Best practices

- Use images with clear contrast between subject and background  
- Avoid heavy occlusion or cluttered scenes  
- Ideal for compositing into other workflows  

---

## Core logic

The block performs:

- **Foreground segmentation**  
  Identifies and isolates the main subject

- **Background processing**
  - Replace mode → generate new environment  
  - Remove mode → delete background

- **Edge refinement**  
  Ensures smooth boundaries between subject and background

- **Context-aware blending (Change BG)**  
  Adjusts lighting and tone to match the new background

---

## Usage tips and best practices

1. **Use high-quality input images**  
   Better subject clarity leads to cleaner results

2. **Ensure subject separation**  
   Simple backgrounds improve segmentation accuracy

3. **Use Change BG for storytelling**  
   Great for lifestyle scenes and ad creatives

4. **Use Remove BG for pipeline workflows**  
   Perfect as a preprocessing step before compositing

5. **Chain with other blocks**
   - Remove BG → place into new scene → Relight  
   - Change BG → refine → Upscale  

---

## Common use cases

- **E-commerce product images**  
  Replace backgrounds with studio or lifestyle scenes

- **Ad creative generation**  
  Quickly test different visual contexts

- **Catalog standardization**  
  Convert images to consistent clean backgrounds

- **Content repurposing**  
  Adapt one image to multiple environments

- **Preprocessing for compositing**  
  Remove background before further editing

---

## Pending technical details

* Complex backgrounds may reduce segmentation accuracy  
* Fine details (hair, transparent objects) may require refinement  
* Future versions may support batch background replacement or style presets  