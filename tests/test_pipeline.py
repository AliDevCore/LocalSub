"""
Tests for SubtitlePipeline and batch queue execution.
"""

from __future__ import annotations

import uuid
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from app.core.config import AppSettings
from app.core.types import FileQueueItem, ProcessingStatus, SubtitleSegment, TargetLanguage
from app.services.ffmpeg_service import FFmpegService
from app.services.pipeline import SubtitlePipeline
from app.services.transcription_service import TranscriptionService
from app.services.translation_service import MockTranslationBackend, TranslationService
from app.workers.pipeline_worker import PipelineWorker


@pytest.fixture
def mock_pipeline(temp_dir: Path, sample_segments):
    """Pipeline with mocked audio and speech services, and mock offline translation."""
    mock_ffmpeg = MagicMock(spec=FFmpegService)
    mock_ffmpeg.probe_media.return_value = (True, True, 10.0)

    # Return a dummy wav path that exists
    dummy_wav = temp_dir / "extracted.wav"
    dummy_wav.write_bytes(b"RIFF dummy wav data")
    mock_ffmpeg.extract_audio.return_value = dummy_wav

    mock_stt = MagicMock(spec=TranscriptionService)
    mock_stt.transcribe_audio.return_value = sample_segments

    mock_trans_backend = MockTranslationBackend(prefix="[FA] ")
    trans_service = TranslationService(custom_backend=mock_trans_backend)

    return SubtitlePipeline(
        ffmpeg_service=mock_ffmpeg,
        transcription_service=mock_stt,
        translation_service=trans_service,
    )


def test_pipeline_english_mode(temp_dir: Path, mock_pipeline: SubtitlePipeline, sample_settings: AppSettings):
    """In English mode, transcription runs and translation is skipped."""
    sample_settings.target_language = TargetLanguage.ENGLISH.value

    video_file = temp_dir / "sample_movie.mp4"
    video_file.write_bytes(b"dummy_video_bytes")
    srt_out = temp_dir / "sample_movie.en.srt"

    item = FileQueueItem(
        id=str(uuid.uuid4()),
        file_path=video_file,
        output_srt_path=srt_out,
    )

    out_path = mock_pipeline.process_item(item, sample_settings)

    assert out_path.is_file()
    assert item.status == ProcessingStatus.COMPLETED
    assert item.progress == 100.0

    content = out_path.read_text(encoding="utf-8")
    assert "Hello world" in content
    # English mode should not have Persian prefixes
    assert "[FA]" not in content


def test_pipeline_persian_mode(temp_dir: Path, mock_pipeline: SubtitlePipeline, sample_settings: AppSettings):
    """In Persian mode, transcription runs and output SRT contains translated Persian text."""
    sample_settings.target_language = TargetLanguage.PERSIAN.value

    video_file = temp_dir / "sample_movie.mp4"
    video_file.write_bytes(b"dummy_video_bytes")
    srt_out = temp_dir / "sample_movie.fa.srt"

    item = FileQueueItem(
        id=str(uuid.uuid4()),
        file_path=video_file,
        output_srt_path=srt_out,
    )

    out_path = mock_pipeline.process_item(item, sample_settings)

    assert out_path.is_file()
    assert item.status == ProcessingStatus.COMPLETED

    content = out_path.read_text(encoding="utf-8")
    # Persian translation output verified
    assert "سلام دنیا" in content or "[FA]" in content

    # Companion English SRT output verified
    en_path = temp_dir / "sample_movie.en.srt"
    assert en_path.is_file()
    assert "Hello world" in en_path.read_text(encoding="utf-8")


def test_pipeline_overwrite_protection(temp_dir: Path, mock_pipeline: SubtitlePipeline, sample_settings: AppSettings):
    """If destination SRT exists and overwrite is disabled, FileExistsError is raised."""
    sample_settings.overwrite_existing = False

    video_file = temp_dir / "sample.mp4"
    video_file.write_bytes(b"dummy")
    srt_out = temp_dir / "sample.en.srt"
    srt_out.write_text("existing content", encoding="utf-8")

    item = FileQueueItem(id="1", file_path=video_file, output_srt_path=srt_out)

    with pytest.raises(FileExistsError):
        mock_pipeline.process_item(item, sample_settings)

    assert item.status == ProcessingStatus.FAILED


def test_pipeline_cancellation(temp_dir: Path, mock_pipeline: SubtitlePipeline, sample_settings: AppSettings):
    """Cooperative cancellation flag interrupts processing gracefully."""
    video_file = temp_dir / "sample.mp4"
    video_file.write_bytes(b"dummy")
    srt_out = temp_dir / "sample.en.srt"

    item = FileQueueItem(id="cancel_test", file_path=video_file, output_srt_path=srt_out)

    with pytest.raises(InterruptedError):
        mock_pipeline.process_item(item, sample_settings, is_cancelled=lambda: True)

    assert item.status == ProcessingStatus.CANCELLED


def test_batch_worker_fault_tolerance(temp_dir: Path, mock_pipeline: SubtitlePipeline, sample_settings: AppSettings):
    """Failure of one video does not abort subsequent items in the queue."""
    # Video 1: Will fail (invalid file)
    v1 = temp_dir / "broken.mp4"
    v1.write_bytes(b"broken")
    # Video 2: Will succeed
    v2 = temp_dir / "good.mp4"
    v2.write_bytes(b"good")

    item1 = FileQueueItem(id="1", file_path=v1, output_srt_path=temp_dir / "broken.en.srt")
    item2 = FileQueueItem(id="2", file_path=v2, output_srt_path=temp_dir / "good.en.srt")

    # Make pipeline fail on item1, succeed on item2
    original_process = mock_pipeline.process_item

    def custom_process(item, settings, progress_callback=None, is_cancelled=None):
        if item.id == "1":
            item.status = ProcessingStatus.FAILED
            raise RuntimeError("Corrupted video container")
        return original_process(item, settings, progress_callback, is_cancelled)

    mock_pipeline.process_item = custom_process

    worker = PipelineWorker(
        queue_items=[item1, item2],
        settings=sample_settings,
        pipeline=mock_pipeline,
    )

    # Run worker synchronously for test
    worker.run()

    assert item1.status == ProcessingStatus.FAILED
    assert item2.status == ProcessingStatus.COMPLETED
