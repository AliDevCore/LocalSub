# LocalSub - AI Models Evaluation and Documentation

LocalSub relies on two independent artificial intelligence layers:
1. **Speech Recognition (Audio -> English Text)**
2. **Neural Machine Translation (English Text -> Persian Text)**

---

## 1. Speech Recognition Models (`faster-whisper`)

LocalSub utilizes `faster-whisper`, a reimplementation of OpenAI's Whisper model powered by `CTranslate2`. It runs efficiently on Windows CPUs utilizing INT8 quantization without requiring a dedicated GPU.

### Model Options & Resource Profile

| Model | Size on Disk | RAM Usage | Speed Factor | Word Error Rate (en) | Target System |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **base** | ~145 MB | ~500 MB | ~4x real-time | Good for clear audio | Laptops / Low-spec CPUs |
| **small** *(Default)* | ~488 MB | ~1.1 GB | ~2.5x real-time | High accuracy for movies | Standard 8GB-16GB RAM PC |
| **medium** | ~1.53 GB | ~2.8 GB | ~1.2x real-time | Highest accuracy | Fast multi-core CPUs, 16GB+ RAM |

### Configuration Details
- **Quantization**: `int8` (8-bit integer weights with FP32/FP16 scale factors).
- **Execution Target**: CPU (`device="cpu"`).
- **Language Lock**: `language="en"` (enforces English speech recognition, preventing hallucinations or language drifting).
- **Voice Activity Detection**: Enabled (`vad_filter=True`) to prevent silence hallucinations.
- **Word Timestamps**: Enabled (`word_timestamps=True`) for high-precision subtitle boundaries.
- **License**: MIT License.

---

## 2. Neural Machine Translation Models (EN -> FA)

### Evaluated Alternatives

During the design phase of LocalSub, three primary candidate model families were evaluated for English-to-Persian translation:

1. **Meta NLLB-200 (No Language Left Behind)**
   - *Model Variant*: `facebook/nllb-200-distilled-600M` / CTranslate2 quantized `JustFrederik/nllb-200-distilled-600M-ct2-int8`.
   - *Parameters*: 600 Million (distilled from 54B parameters).
   - *Size on Disk*: ~620 MB in INT8.
   - *RAM Usage*: ~850 MB.
   - *Persian Language Code*: `pes_Arab` (Western Persian / Farsi in Arabic script).
   - *License*: **CC-BY-NC 4.0** (Creative Commons NonCommercial).
   - *Quality Assessment*: **Superior**. Preserves sentence semantics, movie slang, and natural conversational cadence better than smaller models.
   - *Decision*: **Selected as Primary / Default Translation Model**.

2. **Helsinki-NLP Opus-MT (`Helsinki-NLP/opus-mt-en-fa`)**
   - *Parameters*: ~74 Million.
   - *Size on Disk*: ~310 MB.
   - *RAM Usage*: ~550 MB.
   - *License*: **Apache 2.0** (Permissive open source).
   - *Quality Assessment*: Functional for formal prose, but often struggles with modern colloquial English dialogue and slang in subtitles.
   - *Decision*: **Retained as Permissive / Lightweight Alternative**.

3. **Meta M2M-100 (`facebook/m2m100_418M`)**
   - *Parameters*: 418 Million.
   - *Size on Disk*: ~1.9 GB (unquantized) / ~500 MB (CT2).
   - *License*: MIT License.
   - *Quality Assessment*: Good, but superseded in BLEU and chrF scores by NLLB-200 for low-to-medium resource language pairs like English-to-Persian.

---

## 3. Subtitle Alignment and Batching Strategy

Translating subtitles requires maintaining the exact 1-to-1 relationship between spoken segments and their time boundaries:
1. **No Segment Collapsing**: The translation engine receives batches of 16 segments at a time. It translates each segment independently or with sentence context, returning the exact same segment count.
2. **Timestamp Preservation**: Time offsets (`start` and `end` in milliseconds) are assigned to the Persian subtitle blocks without any alteration.
3. **Persian Typography Normalization**:
   - Arabic characters are converted to Persian equivalents: `ي` -> `ی`, `ك` -> `ک`.
   - Western punctuation is adapted: `,` -> `،`, `?` -> `؟`, `;` -> `؛`.
