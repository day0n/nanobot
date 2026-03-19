# Image Upscaler – Block Knowledge

## Overview

The Image Upscaler block enhances an image by **increasing its resolution while preserving and reconstructing details**.

It is designed for **post-processing**, allowing low- or medium-resolution images to be converted into high-definition outputs suitable for commercial use.

Unlike general Image-to-Image transformation, this block focuses specifically on **clarity, sharpness, and detail recovery**, without altering composition or content.

---

## Input modalities

| Modality | Description | Limits |
|---|---|---|
| **Image (required)** | The source image to be upscaled. | JPEG/PNG recommended, ≤ 10 MB. Higher-quality inputs produce better results. |

> **Note:** The block enhances resolution but does not fundamentally change the content or structure of the image.

---

## Output modality

| Modality | Description | Use cases |
|---|---|---|
| **Image** | A higher-resolution version of the original image with improved detail and sharpness. | HD export, print-ready assets, quality enhancement |

---

## Model and parameters

This block is powered by a dedicated upscaling engine optimized for **detail reconstruction and super-resolution**.

---

### Core parameter

| Parameter | Options | Description |
|---|---|---|
| `upscale_factor` | `2x`, `4x`, `6x` | Multiplies the resolution of the input image. Higher values produce larger images with more reconstructed detail. |

---

## Upscaling behavior

The Image Upscaler performs:

- **Resolution increase**  
  Expands image dimensions proportionally (e.g., 2× → width & height doubled)

- **Detail reconstruction**  
  Uses learned priors to restore textures and edges

- **Sharpening & denoising**  
  Improves clarity while reducing artifacts

The output maintains the **original composition and layout**, with enhanced visual quality.

---

## Usage tips and best practices

1. **Start with the best possible input**  
   Cleaner images yield better upscaling results

2. **Choose factor based on use case**
   - `2x` → quick enhancement / social media  
   - `4x` → standard HD / marketing assets  
   - `6x` → print / large-format visuals  

3. **Avoid over-upscaling**
   Extremely high scaling on low-quality inputs may introduce artifacts

4. **Use as final step**
   Apply upscaling after all editing, styling, and composition steps

5. **Combine with other blocks**
   - Image-to-Image → refine → Upscale  
   - Relight / Angle → finalize → Upscale  

---

## Common use cases

- **E-commerce product images**  
  Upgrade visuals to high-resolution listing standards

- **Ad creatives**  
  Prepare assets for high-quality distribution

- **Print-ready images**  
  Convert digital assets into large-format outputs

- **UGC enhancement**  
  Improve user-generated content quality

- **Final export step in workflows**  
  Ensure consistent output quality across assets

---

## Pending technical details

* Extreme upscaling may introduce hallucinated details depending on input quality  
* Results vary based on noise level and compression artifacts in the source image  
* Future versions may support adaptive or region-based upscaling  