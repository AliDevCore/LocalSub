"""
LocalSub - Application Configuration and State Management.
Handles user directories, persistent preferences, and platform constants.
"""

from __future__ import annotations

import json
import os
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Tuple

from app.core.types import TargetLanguage, TranslationModelType, WhisperModelSize

def _resolve_version() -> str:
    """Resolve version from package metadata or pyproject.toml."""
    try:
        from importlib.metadata import version
        return version("LocalSub")
    except Exception:
        pass
    try:
        pyproject = Path(__file__).resolve().parent.parent.parent / "pyproject.toml"
        if pyproject.is_file():
            for line in pyproject.read_text(encoding="utf-8").splitlines():
                stripped = line.strip()
                if stripped.startswith("version"):
                    parts = stripped.split("=", 1)
                    if len(parts) == 2:
                        return parts[1].strip().strip('"').strip("'")
    except Exception:
        pass
    return "1.0.0"

APP_NAME = "LocalSub"
APP_TITLE = "LocalSub - AI Subtitle & Persian Translation Studio"
APP_VERSION = _resolve_version()
APP_AUTHOR = "LocalSub Team"

# Supported video extensions (Note: .ts excluded to avoid collisions with TypeScript source files)
SUPPORTED_VIDEO_EXTENSIONS = {
    ".mp4",
    ".mkv",
    ".avi",
    ".mov",
    ".wmv",
    ".m4v",
    ".webm",
    ".flv",
    ".m2ts",
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


def get_asset_path(filename: str) -> Path:
    """Return the absolute path to an asset file in development or PyInstaller frozen mode."""
    if getattr(sys, "frozen", False):
        if hasattr(sys, "_MEIPASS"):
            p = Path(sys._MEIPASS) / "assets" / filename
            if p.is_file():
                return p
        exe_dir = Path(sys.executable).resolve().parent
        for candidate in [
            exe_dir / "_internal" / "assets" / filename,
            exe_dir / "assets" / filename,
        ]:
            if candidate.is_file():
                return candidate

    return Path(__file__).resolve().parent.parent.parent / "assets" / filename


def get_default_cpu_threads() -> int:
    """Return default CPU threads (uses full system cores by default for maximum performance)."""
    return os.cpu_count() or 4


def get_available_cpu_thread_options() -> List[Tuple[int, str]]:
    """
    Dynamically discover system CPU cores and return user-selectable options.
    Works dynamically for any core count (2, 4, 8, 16, 32, 64+ cores).
    """
    total = os.cpu_count() or 4
    if total <= 8:
        counts = list(range(total, 0, -1))
    elif total <= 16:
        counts = sorted(list(set([total, 14, 12, 10, 8, 6, 4, 2, 1])), reverse=True)
        counts = [c for c in counts if c <= total]
    else:
        counts = sorted(
            list(set([total, int(total * 0.75), total // 2, max(4, total // 4), 8, 4, 2, 1])),
            reverse=True,
        )
        counts = [c for c in counts if c <= total]

    options: List[Tuple[int, str]] = []
    for count in counts:
        pct = int(round((count / total) * 100))
        if count == total:
            label = f"{count} هسته (حداکثر توان / ۱۰۰٪)"
        elif pct >= 75:
            label = f"{count} هسته (توان بالا / {pct}٪)"
        elif pct >= 50:
            label = f"{count} هسته (متعادل / {pct}٪)"
        else:
            label = f"{count} هسته (حالت سبک / {pct}٪)"
        options.append((count, label))

    return options


@dataclass
class AppSettings:
    """User preferences saved across application restarts."""
    target_language: str = TargetLanguage.PERSIAN.value
    whisper_model: str = WhisperModelSize.SMALL_EN.value
    translation_model: str = TranslationModelType.TRANSLATEGEMMA_4B.value
    last_output_dir: str = ""
    last_input_dir: str = ""
    cpu_threads: int = field(default_factory=get_default_cpu_threads)
    compute_type: str = "int8"
    batch_size: int = 16
    overwrite_existing: bool = False
    save_original_english: bool = True
    custom_ffmpeg_path: str = ""
    filter_filler_words: bool = True

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
            try:
                from app.services.logging_service import get_logger
                get_logger().error(f"Failed to persist settings to '{path}': {e}")
            except Exception:
                pass
