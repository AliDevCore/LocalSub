"""
Tests for SubRip (SRT) formatting, timestamp parsing, validation, and atomic writing.
"""

from __future__ import annotations

from pathlib import Path
from typing import List

import pytest

from app.core.srt_formatter import (
    format_segments_to_srt,
    parse_srt_content,
    seconds_to_srt_time,
    srt_time_to_seconds,
    validate_srt_file,
    write_srt_atomic,
)
from app.core.types import SubtitleSegment


def test_seconds_to_srt_time():
    """Verify timestamp conversion adheres to standard HH:MM:SS,mmm format."""
    assert seconds_to_srt_time(0.0) == "00:00:00,000"
    assert seconds_to_srt_time(1.234) == "00:00:01,234"
    assert seconds_to_srt_time(65.5) == "00:01:05,500"
    assert seconds_to_srt_time(3661.125) == "01:01:01,125"
    # Negative values clamp to 0
    assert seconds_to_srt_time(-5.0) == "00:00:00,000"


def test_srt_time_to_seconds_roundtrip():
    """Verify parsing and round-tripping of SRT timestamps."""
    original_sec = 125.750
    time_str = seconds_to_srt_time(original_sec)
    assert time_str == "00:02:05,750"
    parsed_sec = srt_time_to_seconds(time_str)
    assert abs(parsed_sec - original_sec) < 0.001

    # Also accepts dot separator
    assert abs(srt_time_to_seconds("00:00:02.500") - 2.5) < 0.001


def test_format_segments_sequential_and_chronological(sample_segments):
    """Ensure numbering is strictly sequential (1, 2, 3...) and in order."""
    # Pass unordered list
    unordered = [sample_segments[2], sample_segments[0], sample_segments[1]]
    srt_str = format_segments_to_srt(unordered)

    parsed = parse_srt_content(srt_str)
    assert len(parsed) == 3
    assert [p.index for p in parsed] == [1, 2, 3]
    assert parsed[0].text == "Hello world"
    assert parsed[1].text == "This is a test of LocalSub."
    assert parsed[2].text == "Thank you very much."


def test_format_skips_empty_segments():
    """Empty or whitespace-only subtitle segments must be skipped."""
    segments = [
        SubtitleSegment(index=1, start=1.0, end=2.0, text="   "),
        SubtitleSegment(index=2, start=2.5, end=4.0, text="Valid dialogue"),
        SubtitleSegment(index=3, start=4.5, end=5.0, text=""),
    ]
    srt_str = format_segments_to_srt(segments)
    parsed = parse_srt_content(srt_str)

    assert len(parsed) == 1
    assert parsed[0].index == 1
    assert parsed[0].text == "Valid dialogue"


def test_validate_srt_file_success(temp_dir: Path, sample_segments: List[SubtitleSegment]):
    """Ensure valid SRT file passes integrity check."""
    srt_path = temp_dir / "valid.srt"
    write_srt_atomic(sample_segments, srt_path)

    is_valid, error = validate_srt_file(srt_path)
    assert is_valid is True
    assert error is None


def test_validate_srt_file_catches_errors(temp_dir: Path):
    """Ensure validator detects empty, malformed, or inverted timestamps."""
    # 1. Non-existent file
    is_valid, _ = validate_srt_file(temp_dir / "missing.srt")
    assert is_valid is False

    # 2. Empty file
    empty_path = temp_dir / "empty.srt"
    empty_path.write_text("", encoding="utf-8")
    is_valid, err = validate_srt_file(empty_path)
    assert is_valid is False
    assert "empty" in err.lower()

    # 3. Inverted timestamps (end <= start)
    corrupted_path = temp_dir / "corrupted.srt"
    corrupted_path.write_text(
        "1\n00:00:05,000 --> 00:00:02,000\nInverted time\n\n", encoding="utf-8"
    )
    is_valid, err = validate_srt_file(corrupted_path)
    assert is_valid is False
    assert "<= start" in err.lower()


def test_write_srt_atomic_overwrite_prevention(temp_dir: Path, sample_segments):
    """FileExistsError raised if destination exists and overwrite=False."""
    srt_path = temp_dir / "existing.srt"
    write_srt_atomic(sample_segments, srt_path)
    assert srt_path.is_file()

    with pytest.raises(FileExistsError):
        write_srt_atomic(sample_segments, srt_path, overwrite=False)


def test_persian_utf8_encoding_and_unicode_path(temp_dir: Path):
    """Verify Persian subtitles and directories with Persian and spaces work properly."""
    persian_dir = temp_dir / "پوشه آزمایشی زیرنویس"
    persian_dir.mkdir(parents=True, exist_ok=True)
    srt_path = persian_dir / "فیلم تست اول.fa.srt"

    persian_segments = [
        SubtitleSegment(index=1, start=1.0, end=3.5, text="سلام! به نرم‌افزار LocalSub خوش آمدید."),
        SubtitleSegment(index=2, start=4.0, end=7.2, text="این زیرنویس به زبان فارسی تولید شده است."),
    ]

    written_path = write_srt_atomic(persian_segments, srt_path)
    assert written_path.is_file()

    # Read back as raw bytes to confirm UTF-8
    raw_bytes = written_path.read_bytes()
    decoded_text = raw_bytes.decode("utf-8")

    assert "خوش آمدید" in decoded_text
    assert "فارسی" in decoded_text

    # Validate file
    is_valid, err = validate_srt_file(written_path)
    assert is_valid is True
    assert err is None
