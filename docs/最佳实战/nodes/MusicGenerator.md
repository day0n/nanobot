# Music Generator – Block Knowledge

## Overview

The Music Generator block converts text prompts into **music audio**, supporting both instrumental tracks and vocal songs.

It is designed for:
- background music (BGM)
- short-form video soundtracks
- ad music
- simple song generation

Users can choose between:
- **Instrumental mode** → music only  
- **Vocal mode** → music + singing voice  

---

## Input modalities

| Modality | Description | Limits |
|---|---|---|
| **Text (required)** | Description of the music style, mood, genre, or lyrics | Clear structure recommended |

---

## Output modality

| Modality | Description | Use cases |
|---|---|---|
| **Audio** | Generated music track (instrumental or vocal) | BGM, ads, short videos, songs |

---

## Modes

### 1. Instrumental = ON

- Outputs **music only (no vocals)**
- Best for:
  - background music (BGM)
  - ads and product videos
  - cinematic scoring
  - ambient or mood tracks

---

### 2. Instrumental = OFF

- Outputs **music + vocal (singing)**
- Can include:
  - lyrics (if provided in prompt)
  - melody + singing voice
- Best for:
  - short songs
  - lyrical content
  - creative/music experiments

---

## Prompting guide

A good prompt usually includes:

- **Genre** (e.g. hip hop, cinematic, pop, lo-fi)
- **Mood** (e.g. uplifting, dark, emotional, energetic)
- **Tempo** (optional, e.g. slow, 90 BPM, fast)
- **Instruments** (optional, e.g. piano, synth, drums)
- **Structure or lyrics** (for vocal mode)

---

### Example prompts

**Instrumental**
- "cinematic emotional piano, slow tempo, soft strings, film score"
- "lofi hip hop beat, chill vibe, vinyl texture, 80 BPM"

**Vocal**
- "upbeat pop song about chasing dreams, female vocal, catchy chorus"
- "dark rap track, aggressive tone, trap beat, male vocal"

---

## Best practices

### 1. Be specific about style

Instead of:
- "nice music"

Use:
- "uplifting cinematic orchestral music with piano and strings"

---

### 2. Separate use cases clearly

- For **video background** → use instrumental  
- For **storytelling / content** → use vocal  

---

### 3. Keep prompts structured

Recommended format:

`[genre] + [mood] + [tempo] + [instrumentation] + [optional lyrics]`

---

### 4. Control complexity

- Simpler prompts → more stable output  
- Overly complex prompts → less predictable results  

---

## Common use cases

- **Short video BGM**
- **Ad soundtrack generation**
- **UGC content music**
- **Quick song prototyping**
- **Mood music for scenes**
- **Creative experimentation**

---

## Limitations

- Limited fine-grained control over composition structure  
- Vocal clarity may vary depending on prompt  
- Not suited for full professional music production pipelines  
- Lyrics alignment and pronunciation may require iteration  

---

## Position in workflow

Music Generator is a core **audio creation block**, often used with:

- Video generation → add soundtrack  
- Editing workflows → background scoring  
- Lip sync (vocal mode, experimental)  