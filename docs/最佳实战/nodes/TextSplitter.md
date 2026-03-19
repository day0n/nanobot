# Text Splitter – Block Knowledge

## Overview

The **Text Splitter** block is a functional component used to divide an input document into smaller, logically meaningful segments. Unlike generative blocks, it does not invoke a language model. Instead, the user provides a *splitting rule* in the prompt (e.g., “split by numbered scenes,” “split by bullets,” or “split at every blank line”), and the block returns a list of text chunks accordingly. Splitting a long script or storyboard into individual shots allows downstream generation blocks to process each scene separately, ensuring that each description yields its own image or video. Proper chunking improves performance and retrieval because it respects natural boundaries in the document.

### Input modalities

| Modality | Description | Limitations |
|---|---|---|
| **Text (required)** | The raw script, storyboard or other long form document to be split. Can include numbered scenes, bullet lists or paragraphs. | To ensure responsive processing, keep the input length within tens of thousands of characters (e.g., ≤ 30 k–50 k characters). Very long documents should be uploaded as PDF instead of plain text. |
| **PDF (optional)** | Upload a PDF file containing a long script or storyboard. The block will extract text and apply the splitting rule. | Recommended file size ≤ **10 MB**; PDF parsing may not preserve formatting perfectly—ensure scene markers are clear. |

> **Note:** If the text includes inline images or audio, these are ignored during splitting. Use the audio/image transcription blocks first to convert non‑text content to text.

### Output modality

| Modality | Description |
|---|---|
| **List of text segments** | A list of strings, where each element represents a chunk of the original document following the specified splitting rule. These segments can be passed individually to downstream generation blocks for parallel processing. |

## Splitting rules and parameters

Because the Text Splitter does not rely on a model, its behaviour is defined entirely by user‑provided rules. The block supports the following parameter:

| Parameter | Purpose | Examples & notes |
|---|---|---|
| `split_rule` | A natural language instruction describing how to partition the text. | Examples: “split by numbered headings (e.g., 1., 2., 3.)”, “split whenever you see ‘Scene X:’”, “split on every blank line”, or “split at each bullet point”. Provide clear patterns so that the block can identify boundaries. |

### Guidelines for effective splitting

1. **Respect document structure.** Simple fixed‑size chunking often breaks sentences and ignores natural boundaries. Instead, use separators that align with the document’s structure, such as double line breaks (`\n\n`), scene numbers, or bullet lists. Recursive splitting techniques using a hierarchy of separators preserve paragraph integrity and are widely used.
2. **Adapt rules to the document type.** Different documents require different splitting strategies. For a screenplay or storyboard, split by scene numbers or shot identifiers (e.g., “Scene 1:…”, “Shot 2:…”). For markdown or structured scripts, split on header levels (H1/H2). Avoid a one‑size‑fits‑all approach.
3. **Include context.** When splitting, ensure each segment contains all relevant information needed by downstream tasks. For example, a scene description should include both the setting and the associated dialogue. Avoid cutting off critical context mid‑sentence.
4. **Combine or trim small segments.** If splitting produces very short fragments (e.g., single sentences), consider merging them or adjusting the rule. Overly small chunks may lose context and increase overhead.
5. **Preview and verify.** After splitting, review the resulting list to ensure segments match your expectations. Adjust the `split_rule` and re‑run if necessary.

## Common use cases

- **Storyboard to image generation:** The input is a screenplay or storyboard where each shot is separated by a number (1., 2., 3.). Use a rule like “split by numbered scenes” to isolate each shot. Each text segment is then fed into an image generation block to produce a corresponding frame.
- **Chapter or section summarisation:** For long documents, split by chapter headings or section markers, then summarise each part separately using a summarisation block.
- **Dialogue extraction:** For transcripts or scripts, split by speaker names to isolate each speaker’s lines.

## Pending technical details

* The maximum supported length for text and PDF inputs is subject to the platform’s constraints; very large files may require pre‑processing outside this block.
* If future versions support semantic splitting (e.g., clustering sentences by meaning), additional parameters will be introduced. Current functionality is rule‑based.
* PDF extraction quality can vary depending on the underlying parser; complex layouts (tables, columns) may not be handled gracefully. Verify results or convert PDF to plain text before splitting.