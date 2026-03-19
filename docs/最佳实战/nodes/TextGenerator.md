# Text Generator (LLM) – Block Knowledge

## Overview

The Text Generator block is a core component of the OpenCreator workflow.  
It transforms natural language prompts into structured or creative text outputs such as scripts, scene descriptions, ad copy, and summaries.

The block supports **multimodal context inputs**:

- Text is required
- Images, video, audio, and PDF can be optionally provided

Outputs are always **text**, and this block typically serves as the **reasoning / planning layer** for downstream generation (e.g., image or video).

---

## Input Modalities


| Modality             | Description                                               | Limits                               |
| -------------------- | --------------------------------------------------------- | ------------------------------------ |
| **Text (required)**  | Natural language instructions describing the task or idea | Must fit within model context window |
| **Image (optional)** | Visual references (characters, scenes, products)          | JPEG/PNG, ≤10MB                      |
| **Video (optional)** | Short clips for motion or scene context                   | ≤90s, ≤50MB                          |
| **Audio (optional)** | Dialogue or sound references                              | ≤2min, MP3/WAV                       |
| **PDF (optional)**   | Long-form documents or references                         | Recommended ≤10MB                    |


> ⚠️ **Important: modality support differs by model**
>
> - **Gemini 3 Pro / Gemini 3 Flash**
>   - Support: text, image, audio, video (full multimodal)
> - **GPT-4o**
>   - Support: text + image input only
>   - ❌ Does NOT support audio or video input (API level)

---

## Output Modality


| Modality | Description                                                          |
| -------- | -------------------------------------------------------------------- |
| **Text** | Structured or free-form natural language output (Markdown supported) |


---

## Model Comparison

### Gemini 3 Pro

**Capabilities**

- Full multimodal input: text, image, audio, video
- Context window: up to **1M tokens (input)**
- Max output: **64K tokens**
- Strong reasoning and long-context understanding

**Best for**

- Long-form scripts and storytelling
- Complex multimodal workflows
- Deep reasoning and multi-step planning

---

### Gemini 3 Flash

**Capabilities**

- Same multimodal support as Pro
- Context window: **1M tokens**
- Max output: **64K tokens**
- Optimized for speed and cost efficiency

**Best for**

- High-volume generation
- Fast summarization and rewriting
- Cost-sensitive workflows

---

### GPT-4o

**Capabilities**

- Input: **text + image**
- Output: text
- Context window: **128K tokens**
- Max output: **16K tokens**
- Strong structure and instruction-following

**Limitations**

- ❌ No audio input
- ❌ No video input
- Multimodal capability is primarily vision (image understanding)

**Best for**

- Structured writing (scripts, outlines, copy)
- General-purpose text generation
- Image-informed text tasks

---

## When to Use Which Model


| Use Case                                                | Recommended Model |
| ------------------------------------------------------- | ----------------- |
| Complex multimodal workflows (video/audio/image + text) | Gemini 3 Pro      |
| High-throughput, cost-efficient generation              | Gemini 3 Flash    |
| Structured writing and stable outputs                   | GPT-4o            |


---

## Usage Patterns

- **Upstream planning layer**
  - Generate:
    - Scripts
    - Scene breakdowns
    - Prompts
- **Middle layer**
  - Structure outputs for image/video generation
- **Post-processing**
  - Rewrite, summarize, refine content

---

## Common Use Cases

- Script and scene generation  
- Storyboard planning  
- Ad copywriting  
- Summarization  
- Prompt generation for image/video models

---

## Key Limitations

1. **Model modality differences**
  - GPT-4o is not fully multimodal (no audio/video input)
  - Gemini models support full multimodal input
2. **Context window differences**
  - Gemini: up to 1M tokens
  - GPT-4o: 128K tokens
3. **Prompt structure matters**
  - Long or unstructured prompts reduce output quality
4. **PDF handling**
  - PDFs are processed as extracted text, not full document structure

---

## Role in Workflow

The Text Generator acts as the **"Brain Layer"** of the workflow.

Typical integrations:

- → Image Generator (visual creation)
- → Video Generator (scene scripting)
- → Audio (voiceover scripts)
- → Editing Blocks (refinement and optimization)

