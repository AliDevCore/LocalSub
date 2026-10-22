# LocalSub - User Guide and Instructions

## 1. Getting Started

### Running the Standalone Version
1. Locate `LocalSub-v1.0.0-windows-x64.zip` in the `dist/` directory.
2. Extract the ZIP archive to any folder on your computer (e.g. `C:\Ali\Utility\LocalSub` or Desktop).
3. Double-click `LocalSub.exe` to launch the application.
4. No Python installation, drivers, or command-line setup is needed.

---

## 2. Choosing Subtitle Language

In the top section of the window, locate **Subtitle Language**:

- **Persian (فارسی - Local AI Translated) [Default]**:
  - The software extracts audio, transcribes English speech, and uses local AI to translate dialogue into natural Persian.
  - The resulting file is named `<video_name>.fa.srt` and contains the Persian subtitles with original timing.
- **English (Original Speech Transcript)**:
  - Speech is transcribed directly into English.
  - Translation models are completely bypassed and not loaded.
  - The resulting file is named `<video_name>.en.srt`.

---

## 3. Selecting Models

- **Speech Recognition (faster-whisper)**:
  - `Base`: Fastest, uses least RAM (~500MB). Good for clean dialogue.
  - `Small` *(Recommended)*: High accuracy and balanced speed (~1.1GB RAM).
  - `Medium`: Maximum accuracy for complex movies or thick accents (~2.8GB RAM).
- **Translation Model (Persian)**:
  - `Meta NLLB-200 Distilled 600M` *(Recommended)*: High-quality Persian subtitles.
  - `Helsinki Opus-MT`: Lightweight alternative under Apache 2.0.

> **First Use Note:** If a model is not yet downloaded, LocalSub will ask to download it on your first run or when clicking the "Download" button. Once downloaded, all models work 100% offline.

---

## 4. Processing Video Files

1. Click **Add Video Files...** or drag and drop video files directly into the window.
2. (Optional) Choose a custom output folder in **Output & Queue Settings**. By default, subtitles are saved in the same folder as the video.
3. Click **Start Subtitling**.
4. You can monitor progress per video in the queue table.
5. If needed, click **Cancel** to cleanly stop processing. Completed files will be preserved.

---

## 5. Playing Subtitles with Video

The generated `.srt` files can be played automatically in any modern media player:
- **VLC Media Player**: Automatically loads subtitles if named `<movie>.fa.srt` in the same directory.
- **PotPlayer / MPC-HC**: Fully supported with correct Right-To-Left (RTL) Persian rendering.
