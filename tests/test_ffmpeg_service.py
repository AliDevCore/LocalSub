"""
Tests for FFmpegService: discovery, probing, error handling, and cancellation.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from app.services.ffmpeg_service import FFmpegNotFoundError, FFmpegService, NoAudioStreamError


def test_ffmpeg_discovery_system_path():
    """Verify that FFmpeg on system PATH is found."""
    service = FFmpegService()
    try:
        ffmpeg_bin = service.find_ffmpeg()
        assert ffmpeg_bin.is_file()
        assert "ffmpeg" in ffmpeg_bin.name.lower()
    except FFmpegNotFoundError:
        pytest.skip("FFmpeg not installed on host machine.")


def test_ffmpeg_custom_path_override(temp_dir: Path):
    """Verify custom FFmpeg path is prioritized."""
    custom_exe = temp_dir / "custom_ffmpeg.exe"
    custom_exe.write_text("fake", encoding="utf-8")

    service = FFmpegService(custom_path=str(custom_exe))
    found = service.find_ffmpeg()
    assert found == custom_exe.resolve()


def test_probe_missing_or_empty_file(temp_dir: Path):
    """Probing non-existent or 0-byte file returns (False, False, 0.0)."""
    service = FFmpegService()
    # Missing file
    valid, has_audio, dur = service.probe_media(temp_dir / "non_existent.mp4")
    assert valid is False
    assert has_audio is False

    # 0-byte file
    empty_file = temp_dir / "empty.mp4"
    empty_file.write_bytes(b"")
    valid, has_audio, dur = service.probe_media(empty_file)
    assert valid is False
    assert has_audio is False


def test_no_audio_stream_raises_error(temp_dir: Path):
    """Media without audio stream raises NoAudioStreamError during extraction."""
    service = FFmpegService()
    dummy_video = temp_dir / "silent_video.mp4"
    dummy_video.write_bytes(b"dummy_content")

    # Mock probe to return valid container but no audio
    with patch.object(service, "probe_media", return_value=(True, False, 10.0)):
        with pytest.raises(NoAudioStreamError):
            service.extract_audio(dummy_video)


def test_cancellation_cleans_temporary_wav(temp_dir: Path):
    """If extraction is cancelled, FFmpeg process is terminated and output file is deleted."""
    service = FFmpegService()
    dummy_video = temp_dir / "test_video.mp4"
    dummy_video.write_bytes(b"dummy_content")
    out_wav = temp_dir / "cancelled.wav"

    mock_process = MagicMock()
    mock_process.poll.return_value = None

    with patch.object(service, "find_ffmpeg", return_value=Path("ffmpeg.exe")):
        with patch.object(service, "probe_media", return_value=(True, True, 20.0)):
            with patch("subprocess.Popen", return_value=mock_process):
                with pytest.raises(InterruptedError):
                    service.extract_audio(
                        video_path=dummy_video,
                        output_wav_path=out_wav,
                        is_cancelled=lambda: True,  # Cancel immediately
                    )

    # Process terminate/kill was called
    assert mock_process.terminate.called or mock_process.kill.called
    assert not out_wav.exists()
