"""
LocalSub - Pytest Configuration and Test Fixtures.
Provides isolated temporary directories, mock subtitle segments, and test helpers.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import Generator, List

import pytest

from app.core.config import AppSettings
from app.core.types import FileQueueItem, ProcessingStatus, SubtitleSegment, TargetLanguage, WordTiming
from app.services.translation_service import MockTranslationBackend, TranslationService


@pytest.fixture
def temp_dir() -> Generator[Path, None, None]:
    """Provide a clean temporary directory for tests."""
    with tempfile.TemporaryDirectory() as td:
        yield Path(td)


@pytest.fixture
def sample_segments() -> List[SubtitleSegment]:
    """Sample speech-recognition segments."""
    return [
        SubtitleSegment(
            index=1,
            start=1.200,
            end=3.400,
            text="Hello world",
            words=[
                WordTiming("Hello", 1.200, 2.100),
                WordTiming("world", 2.200, 3.400),
            ],
        ),
        SubtitleSegment(
            index=2,
            start=4.000,
            end=6.550,
            text="This is a test of LocalSub.",
        ),
        SubtitleSegment(
            index=3,
            start=7.100,
            end=9.825,
            text="Thank you very much.",
        ),
    ]


@pytest.fixture
def mock_translation_service() -> TranslationService:
    """Translation service with an offline mock backend."""
    backend = MockTranslationBackend(prefix="[فارسی] ")
    return TranslationService(custom_backend=backend)


@pytest.fixture
def sample_settings(temp_dir: Path) -> AppSettings:
    """Test app settings pointing to temp directory."""
    settings = AppSettings()
    settings.last_output_dir = str(temp_dir)
    settings.overwrite_existing = True
    return settings
