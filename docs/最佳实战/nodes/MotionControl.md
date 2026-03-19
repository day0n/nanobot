# Motion Control – Block Knowledge

## Overview

The Motion Control block transfers motion from a reference video onto a target subject, generating a new video where the subject performs the same movement.

It is designed for **motion capture and motion transfer**, enabling users to replicate actions such as dancing, sports movements, or gestures onto a different character or object.

This block is commonly used for **UGC content, entertainment, character animation, and creative motion replication**.

---

## Input modalities

| Modality | Description | Limits |
|---|---|---|
| **Image (required)** | The target subject (e.g., person, character, animal) that will perform the motion. | Full-body images recommended for best results. Clear pose and structure improve motion transfer. |
| **Video (required)** | The motion reference video that defines the movement. | Recommended ≤ **30 seconds**. Clear, continuous motion improves quality. |
| **Text (optional)** | Additional instruction for style, character details, or scene refinement. | Optional. Can be used to adjust style or enhance output. |

> **Note:** The image defines *who*, and the video defines *how they move*.

---

## Output modality

| Modality | Description | Use cases |
|---|---|---|
| **Video** | A generated video where the target subject performs the motion from the reference video. | Dance replication, motion transfer, character animation |

---

## Modes

### 1. Motion-first (video)

The output strictly follows the motion from the reference video.

#### Behavior

- Transfers **full-body movement and pose dynamics**
- Preserves timing and rhythm of the original motion
- Adapts motion onto the new subject

#### Best for:

- Dance videos  
- Sports actions  
- Large or complex movements  
- High-energy motion replication  

#### Notes:

- Max duration typically around **30 seconds**
- Motion fidelity is prioritized over composition

---

### 2. Composition-first (image)

The output prioritizes the composition and framing of the input image, while applying motion more subtly.

#### Behavior

- Preserves **original framing and pose**
- Applies **partial or simplified motion**
- Focuses on camera motion and light movement rather than full-body dynamics

#### Best for:

- Close-up shots  
- Subtle animation  
- Product visuals  
- Light motion effects (e.g., breathing, slight movement)

#### Notes:

- Max duration typically shorter (e.g., ~10 seconds)
- Composition consistency is prioritized over motion accuracy

---

## Parameters

### Core parameters

| Parameter | Options | Description |
|---|---|---|
| `mode` | `motion-first`, `composition-first` | Controls whether motion or composition is prioritized |
| `keep_audio` | `on`, `off` | Determines whether to preserve the original audio from the reference video |

---

## Motion transfer logic

The block performs:

- **Motion extraction**  
  Captures pose, timing, and movement from the reference video

- **Subject mapping**  
  Applies motion to the target subject while preserving identity

- **Temporal alignment**  
  Maintains rhythm and sequencing of the original motion

- **Visual synthesis**  
  Generates new frames consistent with the subject and motion

---

## Usage tips and best practices

1. **Use full-body images for best results**
   Partial or cropped subjects reduce motion accuracy

2. **Choose clean motion videos**
   Clear, well-lit, single-subject videos work best

3. **Match proportions when possible**
   Similar body structure improves realism

4. **Use Motion-first for fidelity**
   When exact motion replication matters

5. **Use Composition-first for control**
   When visual consistency matters more than motion

6. **Keep background simple**
   Complex scenes may introduce artifacts

7. **Use text for refinement**
   Add style cues like:
   - “cartoon style”
   - “cinematic lighting”
   - “realistic fur texture”

---

## Common use cases

- **Dance replication**
  Transfer choreography onto a different character (e.g., pets, avatars)

- **UGC content creation**
  Generate viral-style motion content

- **Character animation**
  Bring static characters to life with real-world motion

- **Entertainment / meme generation**
  Recreate popular motion formats with new subjects

- **Sports motion transfer**
  Apply athletic movement to stylized or fictional characters

---

## Pending technical details

* Motion quality depends heavily on input video clarity and continuity  
* Complex occlusion or multiple subjects may reduce accuracy  
* Large differences in body structure may introduce distortion  
* Future versions may support multi-subject motion transfer or motion blending  