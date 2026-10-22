# Third-Party Notices and Model Licensing

LocalSub is licensed under the MIT License. However, it incorporates and interacts with various third-party libraries, AI models, and tools. Below is an overview of third-party licenses and constraints.

---

## 1. Third-Party Libraries

| Library | License | Usage |
| :--- | :--- | :--- |
| **PySide6 / Qt 6** | LGPLv3 / Commercial | Graphical User Interface runtime |
| **faster-whisper** | MIT License | CTranslate2-based Whisper speech recognition |
| **CTranslate2** | MIT License | Fast INT8 CPU inference engine |
| **Transformers** | Apache 2.0 | Tokenization and translation pipelines |
| **SentencePiece** | Apache 2.0 | Subword tokenization |
| **Hugging Face Hub**| Apache 2.0 | Model downloading and caching |
| **FFmpeg** | LGPL / GPL v3 | Audio extraction from video containers |
| **PyInstaller** | GPLv2 with Exception | Executable packaging |
| **Pytest** | MIT License | Automated testing suite |

---

## 2. Artificial Intelligence Models

LocalSub downloads AI models dynamically on user demand. The software itself does not bundle model weights.

### Speech Recognition Models (Whisper)
- **Engine**: OpenAI Whisper ported to CTranslate2 by Systran (`Systran/faster-whisper-*`).
- **License**: **MIT License**.
- **Commercial Use**: Permitted under OpenAI/Systran MIT terms.

### Translation Models
1. **Meta NLLB-200 (No Language Left Behind)**
   - **Repository**: `facebook/nllb-200-distilled-600M` / `JustFrederik/nllb-200-distilled-600M-ct2-int8`
   - **License**: **Creative Commons Attribution-NonCommercial 4.0 International (CC-BY-NC 4.0)**
   - **Constraints**: Free for research, personal, educational, and non-commercial open-source distribution. If using LocalSub in commercial enterprise settings, users must switch to an Apache-licensed translation model or obtain appropriate licensing from Meta.
   - **Language Pair**: English (`eng_Latn`) to Persian (`pes_Arab`).

2. **Helsinki-NLP Opus-MT (en-fa)**
   - **Repository**: `Helsinki-NLP/opus-mt-en-fa`
   - **License**: **Apache 2.0**
   - **Constraints**: Fully open source and permissive for all uses including commercial.

---

## 3. FFmpeg Notice

FFmpeg is licensed under the GNU Lesser General Public License (LGPL) version 2.1 or later, or GNU General Public License (GPL) version 2 or later depending on build configurations. LocalSub executes FFmpeg as an independent external process (`ffmpeg.exe`) via standard subprocess interfaces and does not statically link against FFmpeg source code.

Source code for FFmpeg can be downloaded from: https://ffmpeg.org
