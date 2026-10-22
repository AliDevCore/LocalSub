"""
LocalSub - Application Configuration and State Management.
Handles user directories, persistent preferences, and platform constants.
"""

from __future__ import annotations

import json
import os
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List

from app.core.types import TargetLanguage, TranslationModelType, WhisperModelSize

APP_NAME = "LocalSub"
APP_TITLE = "LocalSub - AI Subtitle & Persian Translation Studio"
APP_VERSION = "1.0.0"
APP_AUTHOR = "LocalSub Team"

# Supported video extensions
SUPPORTED_VIDEO_EXTENSIONS = {
    ".mp4",
    ".mkv",
    ".avi",
    ".mov",
    ".wmv",
    ".m4v",
    ".webm",
    ".flv",
    ".ts",
    ".mpeg",
    ".mpg",
}


def get_app_data_dir() -> Path:
    """Return user application data directory: %LOCALAPPDATA%\\LocalSub."""
    if sys.platform == "win32":
        base = os.environ.get("LOCALAPPDATA")
        if not base:
            base = os.path.expanduser("~")
        path = Path(base) / APP_NAME
    else:
        path = Path.home() / f".{APP_NAME.lower()}"
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_models_dir() -> Path:
    """Directory where Whisper and Translation models are stored."""
    path = get_app_data_dir() / "models"
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_logs_dir() -> Path:
    """Directory where runtime application logs are written."""
    path = get_app_data_dir() / "logs"
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_temp_dir() -> Path:
    """Directory for temporary audio extraction and intermediate files."""
    path = get_app_data_dir() / "temp"
    path.mkdir(parents=True, exist_ok=True)
    return path


@dataclass
class AppSettings:
    """User preferences saved across application restarts."""
    target_language: str = TargetLanguage.PERSIAN.value
    whisper_model: str = WhisperModelSize.SMALL.value
    translation_model: str = TranslationModelType.NLLB_DISTILLED_600M.value
    last_output_dir: str = ""
    last_input_dir: str = ""
    cpu_threads: int = 4
    compute_type: str = "int8"
    batch_size: int = 16
    overwrite_existing: bool = False
    save_original_english: bool = True
    custom_ffmpeg_path: str = ""

    @classmethod
    def get_settings_file(cls) -> Path:
        return get_app_data_dir() / "settings.json"

    @classmethod
    def load(cls) -> AppSettings:
        path = cls.get_settings_file()
        if not path.is_file():
            return cls()
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})
        except Exception:
            return cls()

    def save(self) -> None:
        path = self.get_settings_file()
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(asdict(self), f, indent=2, ensure_ascii=False)
        except Exception as e:
            # Avoid crashing if save fails
            pass
