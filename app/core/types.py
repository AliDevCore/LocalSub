"""
LocalSub - Core Types and Data Models.
Defines domain models, enums, and data contracts used across LocalSub.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import List, Optional


class ProcessingStatus(str, Enum):
    """Lifecycle status for a video item in the processing queue."""
    QUEUED = "queued"
    EXTRACTING_AUDIO = "extracting_audio"
    TRANSCRIBING = "transcribing"
    TRANSLATING = "translating"
    GENERATING_SRT = "generating_srt"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

    @property
    def display_name(self) -> str:
        names = {
            ProcessingStatus.QUEUED: "Queued",
            ProcessingStatus.EXTRACTING_AUDIO: "Extracting Audio...",
            ProcessingStatus.TRANSCRIBING: "Transcribing Speech...",
            ProcessingStatus.TRANSLATING: "Translating to Persian...",
            ProcessingStatus.GENERATING_SRT: "Generating Subtitles...",
            ProcessingStatus.COMPLETED: "Completed",
            ProcessingStatus.FAILED: "Failed",
            ProcessingStatus.CANCELLED: "Cancelled",
        }
        return names.get(self, self.value)


class TargetLanguage(str, Enum):
    """Output subtitle language."""
    ENGLISH = "en"
    PERSIAN = "fa"

    @property
    def display_name(self) -> str:
        mapping = {
            TargetLanguage.ENGLISH: "English (Original Transcript)",
            TargetLanguage.PERSIAN: "Persian (فارسی - Local AI Translated)",
        }
        return mapping.get(self, self.value)

    @property
    def nllb_code(self) -> str:
        """NLLB-200 language code."""
        mapping = {
            TargetLanguage.ENGLISH: "eng_Latn",
            TargetLanguage.PERSIAN: "pes_Arab",
        }
        return mapping.get(self, "eng_Latn")


class WhisperModelSize(str, Enum):
    """faster-whisper model size on CPU."""
    BASE = "base"
    SMALL = "small"
    MEDIUM = "medium"

    @property
    def display_name(self) -> str:
        mapping = {
            WhisperModelSize.BASE: "Base (~145 MB, Fastest, Low RAM)",
            WhisperModelSize.SMALL: "Small (~488 MB, Recommended, Balanced)",
            WhisperModelSize.MEDIUM: "Medium (~1.5 GB, Highest Accuracy, Needs 4GB+ RAM)",
        }
        return mapping.get(self, self.value)

    @property
    def approx_size_mb(self) -> int:
        mapping = {
            WhisperModelSize.BASE: 145,
            WhisperModelSize.SMALL: 488,
            WhisperModelSize.MEDIUM: 1530,
        }
        return mapping.get(self, 488)


class TranslationModelType(str, Enum):
    """Supported local translation models."""
    TRANSLATEGEMMA_4B = "translategemma-4b"
    NLLB_DISTILLED_600M = "nllb-200-distilled-600M"
    OPUS_MT_EN_FA = "opus-mt-en-fa"

    @property
    def display_name(self) -> str:
        mapping = {
            TranslationModelType.TRANSLATEGEMMA_4B: "Google TranslateGemma 4B (Recommended, Fluent Persian)",
            TranslationModelType.NLLB_DISTILLED_600M: "Meta NLLB-200 Distilled 600M (Standard, Low RAM)",
            TranslationModelType.OPUS_MT_EN_FA: "Helsinki Opus-MT en-fa (Lightweight, Apache 2.0)",
        }
        return mapping.get(self, self.value)

    @property
    def license_name(self) -> str:
        mapping = {
            TranslationModelType.TRANSLATEGEMMA_4B: "Gemma Terms of Use (Open Weights)",
            TranslationModelType.NLLB_DISTILLED_600M: "CC-BY-NC-4.0 (Non-Commercial Research & Personal Use)",
            TranslationModelType.OPUS_MT_EN_FA: "Apache 2.0 (Permissive Open Source)",
        }
        return mapping.get(self, "Unknown")


@dataclass
class WordTiming:
    """Word-level timestamp for detailed alignment."""
    word: str
    start: float
    end: float
    probability: float = 1.0


@dataclass
class SubtitleSegment:
    """
    Individual subtitle block conforming to SubRip specifications.
    
    Timestamps are in floating-point seconds (e.g. 1.500 -> 00:00:01,500).
    """
    index: int
    start: float
    end: float
    text: str
    words: List[WordTiming] = field(default_factory=list)

    def validate(self) -> None:
        """Validate subtitle segment boundaries and contents."""
        if self.index < 1:
            raise ValueError(f"Subtitle index must be >= 1, got {self.index}")
        if self.start < 0:
            raise ValueError(f"Subtitle start time cannot be negative: {self.start}")
        if self.end <= self.start:
            raise ValueError(
                f"Subtitle end time ({self.end}) must be strictly greater than start time ({self.start})"
            )
        if not self.text.strip():
            raise ValueError("Subtitle text cannot be empty or pure whitespace")

    @property
    def duration(self) -> float:
        return max(0.0, self.end - self.start)


@dataclass
class FileQueueItem:
    """Queue representation for a video file scheduled for processing."""
    id: str
    file_path: Path
    output_srt_path: Path
    status: ProcessingStatus = ProcessingStatus.QUEUED
    progress: float = 0.0  # 0.0 to 100.0
    current_step: str = "In queue"
    error_message: Optional[str] = None
    duration_seconds: Optional[float] = None
    segments_count: int = 0
