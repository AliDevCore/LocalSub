# Changelog

All notable changes to the **LocalSub** project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [1.0.0] - 2026-10-22

### Added
- **Local Speech Recognition**: Integrated `faster-whisper` on CPU using INT8 quantization (`base`, `small`, `medium` model sizes).
- **Local Neural Machine Translation**: Integrated `Meta NLLB-200 Distilled 600M` and `Helsinki Opus-MT` for English to Persian translation.
- **Independent Language Modes**:
  - English Mode: Generates original speech transcript in standard SRT; completely avoids loading or downloading translation models.
  - Persian Mode: Performs English speech recognition and translates dialogue into natural Persian (`.fa.srt`).
- **Standard SubRip (.srt) Generator**:
  - Strict timestamp formatting (`HH:MM:SS,mmm`).
  - Sequential index numbering and chronological order.
  - Automatic filtering of empty speech segments.
  - Atomic writing to temporary files before moving to final destination.
  - UTF-8 encoding with Persian character and punctuation normalization (`؟`, `،`, `؛`).
- **Batch Video Queue**:
  - Drag-and-drop video import and folder scanning.
  - Non-blocking execution via PySide6 `QThread` workers.
  - True cooperative cancellation with real-time FFmpeg process termination and temporary file cleanup.
  - Fault tolerance: Single corrupted video does not abort remaining queue items.
  - Overwrite safety switch.
- **Model Manager**:
  - On-demand downloading with progress reporting.
  - Persistent caching in `%LOCALAPPDATA%\LocalSub\models`.
  - Integrity validation and offline readiness verification.
- **Windows GUI**:
  - Windows 11 Fluent dark theme using PySide6.
  - Live model readiness badges and queue progress indicators.
  - Built-in Log Viewer dialog and Explorer shortcuts.
- **CI / CD and Packaging**:
  - Automated Windows build script using PyInstaller (`onedir` mode packaged in ZIP).
  - Automated SHA-256 checksum generation.
- **Automated Test Suite**:
  - 28 unit and integration tests passing with pytest.
