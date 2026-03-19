# Text to Speech – Block Knowledge

## Overview

The Text to Speech block converts written text into speech audio.

It is used to generate voiceovers, narration, dialogue audio, and speaking tracks for downstream workflows such as lip sync, video narration, ads, and localized content.

This block supports multiple voice providers with different strengths:

- **Fish Audio** → celebrity / parody / creator-style voices
- **ElevenLabs v2** → professional, brand-safe, narration-style voices
- **Minimax Speech 2.8 HD** → Chinese-focused voices and stronger Chinese delivery

---

## Input modalities

| Modality | Description | Limits |
|---|---|---|
| **Text (required)** | The script to be converted into speech. | Best practice: keep each text chunk short enough to produce audio of **30 seconds or less**. |

> **Note:** If the source script is long, it is recommended to split it into smaller chunks first, then generate audio in parallel.

---

## Output modality

| Modality | Description | Use cases |
|---|---|---|
| **Audio** | Generated speech audio using the selected voice model and voice effect. | Voiceover, narration, lip-sync input, ads, dialogue |

---

## Model selection

### 1. Fish Audio

Best for:
- celebrity / parody style voices
- meme content
- creator-style or internet-native delivery
- entertaining, exaggerated, or stylized voice outputs

#### Example voice options seen in product

- Elon Musk
- Donald Trump
- Taylor Swift
- Alle
- Paula
- Energetic Male
- Mr Beast
- ElevenLabs Adam
- Marcus Narrator
- E-Girl Soft
- Horror Narrator

> **Note:** Fish Audio voice options are broad and may include celebrity-inspired, creator-inspired, and stylized internet-native voices.

---

### 2. ElevenLabs v2

Best for:
- brand narration
- polished ads
- explainer videos
- professional and neutral voiceover generation

#### Example voice options seen in product

- Rachel
- Aria
- Charlotte
- River
- Charlie
- Callum
- Brian
- Bill
- Lily
- Sarah
- Roger
- Laura

> **Note:** ElevenLabs voices are generally more stable, neutral, and production-friendly than stylized or parody-oriented voices.

---

### 3. fal-ai/minimax/speech-2.8-hd

Best for:
- Chinese voice generation
- localized Chinese content
- bilingual workflows
- Chinese narration with better fluency and pronunciation

#### Example voice options seen in product

- Lively Girl
- Patient Man
- Young Knight
- Determined Man
- Lovely Girl
- Decent Boy

#### Additional controls

| Parameter | Description |
|---|---|
| `language_boost` | Improves language performance, such as Chinese |
| `voice_speed` | Controls speaking speed |
| `voice_volume` | Controls output loudness |

---

## Parameters

### Common parameters

| Parameter | Description |
|---|---|
| `model` | Selects the speech generation provider |
| `voice_effect` | Selects the voice identity / style within that provider |

### Minimax-specific parameters

| Parameter | Description |
|---|---|
| `language_boost` | Boosts performance for the selected language |
| `voice_speed` | Adjusts speaking speed |
| `voice_volume` | Adjusts output volume |

---

## Best practices

### 1. Keep each chunk short

Best practice:
- each text chunk should generate **30 seconds or less** of audio

Why:
- faster generation
- better stability
- easier parallel production
- easier downstream alignment for lip sync and editing

---

### 2. Split long scripts first

Recommended workflow:

`Long script → Text Splitter → short text chunks → parallel TTS generation`

This is especially useful for:
- long voiceovers
- ad scripts with multiple scenes
- narration pipelines
- multi-segment talking videos

---

### 3. Match the voice model to the content type

| Scenario | Recommended model |
|---|---|
| Celebrity / parody / meme / creator-style content | Fish Audio |
| Professional brand narration / ads / explainers | ElevenLabs v2 |
| Chinese voiceover / localized Chinese content | Minimax Speech 2.8 HD |

---

### 4. Write text for speaking, not reading

For better output:
- use shorter sentences
- add natural pauses
- avoid overly dense paragraphs
- write in a spoken, conversational rhythm

---

## Common use cases

- **UGC ad voiceover**
- **Narration for short-form videos**
- **Creator-style AI voice generation**
- **Brand explainer voiceover**
- **Chinese localization**
- **Lip-sync audio generation**
- **Batch voice generation for multi-scene workflows**

---

## Limitations

- Long text blocks may reduce stability and increase generation time
- Voice consistency across many separate chunks may vary slightly
- Stylized voices may exaggerate tone or delivery
- Final timing may still require downstream editing for perfect sync

---

## Position in workflow

Text to Speech is a core **audio generation block** and is commonly used with:

- **Text Splitter** → **Text to Speech** → split long scripts into short chunks
- **Text to Speech** → **Video to Lip Sync** → drive speaking videos from audio
- **Text to Speech** → **Image to Lip Sync** → turn portraits into speaking characters