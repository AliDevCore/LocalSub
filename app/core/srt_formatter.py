"""
LocalSub - Standard SubRip (SRT) Formatter and Validator.
Follows SubRip specification with strict timestamp formatting (HH:MM:SS,mmm),
sequential numbering, UTF-8 encoding, and atomic temporary-to-final writing.
"""

from __future__ import annotations

import math
import os
import re
from pathlib import Path
from typing import List, Optional, Tuple

from app.core.types import SubtitleSegment


def seconds_to_srt_time(seconds: float) -> str:
    """
    Convert floating-point seconds into standard SRT timestamp 'HH:MM:SS,mmm'.
    
    Example: 83.456 -> '00:01:23,456'
    """
    if seconds < 0:
        seconds = 0.0

    total_ms = int(math.floor(seconds * 1000 + 0.5))
    hours = total_ms // 3_600_000
    remainder = total_ms % 3_600_000
    minutes = remainder // 60_000
    remainder %= 60_000
    secs = remainder // 1000
    millis = remainder % 1000

    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


def srt_time_to_seconds(time_str: str) -> float:
    """
    Convert 'HH:MM:SS,mmm' (or with dot 'HH:MM:SS.mmm') into seconds.
    """
    time_str = time_str.strip().replace(".", ",")
    pattern = r"^(\d{1,2}):(\d{2}):(\d{2}),(\d{1,3})$"
    match = re.match(pattern, time_str)
    if not match:
        raise ValueError(f"Invalid SRT timestamp format: '{time_str}'")

    hours = int(match.group(1))
    minutes = int(match.group(2))
    secs = int(match.group(3))
    millis = int(match.group(4).ljust(3, "0")[:3])

    return hours * 3600 + minutes * 60 + secs + millis / 1000.0


def sanitize_subtitle_text(text: str) -> str:
    """
    Clean dialogue text for subtitles: strip excess whitespace,
    normalize line endings, remove dangling formatting.
    """
    if not text:
        return ""
    lines = [line.strip() for line in text.replace("\r\n", "\n").replace("\r", "\n").split("\n")]
    cleaned_lines = [l for l in lines if l]
    return "\n".join(cleaned_lines).strip()


def format_segments_to_srt(segments: List[SubtitleSegment]) -> str:
    """
    Format a list of SubtitleSegment instances into a standard SubRip string.
    Ensures sequential numbering, valid timestamps, and skips empty segments.
    """
    output_blocks: List[str] = []
    current_index = 1

    for seg in sorted(segments, key=lambda s: s.start):
        cleaned_text = sanitize_subtitle_text(seg.text)
        if not cleaned_text:
            continue

        start_sec = max(0.0, float(seg.start))
        end_sec = max(start_sec + 0.1, float(seg.end))

        start_str = seconds_to_srt_time(start_sec)
        end_str = seconds_to_srt_time(end_sec)

        block = f"{current_index}\n{start_str} --> {end_str}\n{cleaned_text}\n"
        output_blocks.append(block)
        current_index += 1

    return "\n".join(output_blocks)


def parse_srt_content(content: str) -> List[SubtitleSegment]:
    """
    Parse SRT text into a list of SubtitleSegment instances.
    """
    # Normalize line breaks
    normalized = content.replace("\r\n", "\n").replace("\r", "\n").strip()
    if not normalized:
        return []

    # SRT blocks are separated by double newlines
    raw_blocks = re.split(r"\n\s*\n", normalized)
    segments: List[SubtitleSegment] = []

    for block in raw_blocks:
        lines = [line.strip() for line in block.strip().split("\n") if line.strip()]
        if len(lines) < 2:
            continue

        # Line 0 is usually index, but sometimes omitted; check if line contains '-->'
        time_line_idx = -1
        for i, line in enumerate(lines[:3]):
            if "-->" in line:
                time_line_idx = i
                break

        if time_line_idx == -1:
            continue

        time_line = lines[time_line_idx]
        parts = time_line.split("-->")
        if len(parts) != 2:
            continue

        try:
            start = srt_time_to_seconds(parts[0].strip())
            end = srt_time_to_seconds(parts[1].strip())
        except ValueError:
            continue

        text_lines = lines[time_line_idx + 1 :]
        text = sanitize_subtitle_text("\n".join(text_lines))
        if not text:
            continue

        idx = len(segments) + 1
        segments.append(SubtitleSegment(index=idx, start=start, end=end, text=text))

    return segments


def validate_srt_file(file_path: Path) -> Tuple[bool, Optional[str]]:
    """
    Validate that an SRT file exists, is non-empty, contains valid UTF-8,
    and has correct SubRip structure and timestamps.
    """
    if not file_path.is_file():
        return False, f"File does not exist: {file_path}"

    try:
        content = file_path.read_text(encoding="utf-8")
    except UnicodeDecodeError as e:
        return False, f"SRT file is not valid UTF-8: {e}"

    if not content.strip():
        return False, "SRT file is empty"

    segments = parse_srt_content(content)
    if not segments:
        return False, "SRT file contains no valid subtitle blocks"

    for i, seg in enumerate(segments):
        if seg.start < 0:
            return False, f"Segment {seg.index} has negative start time: {seg.start}"
        if seg.end <= seg.start:
            return False, f"Segment {seg.index} has end time ({seg.end}) <= start time ({seg.start})"
        if not seg.text.strip():
            return False, f"Segment {seg.index} has empty text"
        if i > 0 and seg.start < segments[i - 1].start:
            return False, f"Segments are not in chronological order: segment {seg.index}"

    return True, None


def write_srt_atomic(
    segments: List[SubtitleSegment],
    destination_path: Path,
    overwrite: bool = True,
) -> Path:
    """
    Atomically write subtitle segments to destination path.
    1. Write to temporary file with .tmp extension.
    2. Validate file integrity.
    3. Atomically rename/replace to destination path.
    """
    destination_path = Path(destination_path)
    if destination_path.exists() and not overwrite:
        raise FileExistsError(f"Destination SRT already exists and overwrite is False: {destination_path}")

    destination_path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = destination_path.with_name(f"{destination_path.name}.tmp")

    try:
        srt_content = format_segments_to_srt(segments)
        # Write with UTF-8
        temp_path.write_text(srt_content, encoding="utf-8")

        # Validate temp file before replacing destination
        is_valid, error = validate_srt_file(temp_path)
        if not is_valid:
            raise ValueError(f"Generated SRT failed validation: {error}")

        # Atomic replace
        if destination_path.exists():
            destination_path.unlink()
        temp_path.replace(destination_path)
        return destination_path
    finally:
        if temp_path.exists():
            try:
                temp_path.unlink()
            except OSError:
                pass
