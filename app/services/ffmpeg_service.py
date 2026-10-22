"""
LocalSub - FFmpeg Audio Extraction and Validation Service.
Provides robust discovery of FFmpeg binaries, media container verification,
audio track probing, and cancellation-aware extraction to 16kHz mono WAV.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Callable, Optional, Tuple

from app.core.config import SUPPORTED_VIDEO_EXTENSIONS, get_temp_dir
from app.services.logging_service import get_logger


class FFmpegNotFoundError(RuntimeError):
    """Raised when FFmpeg executable cannot be located on system or bundle."""
    pass


class NoAudioStreamError(RuntimeError):
    """Raised when media file contains no detectable audio tracks."""
    pass


class FFmpegService:
    """Service wrapping FFmpeg operations."""

    def __init__(self, custom_path: Optional[str] = None):
        self._custom_path = custom_path
        self._ffmpeg_path: Optional[Path] = None

    def find_ffmpeg(self) -> Path:
        """
        Locate FFmpeg executable in priority order:
        1. Custom path specified in settings
        2. PyInstaller bundled path (_MEIPASS / executable directory)
        3. System PATH environment variable
        """
        if self._ffmpeg_path and self._ffmpeg_path.is_file():
            return self._ffmpeg_path

        candidates = []

        # 1. Custom path
        if self._custom_path:
            candidates.append(Path(self._custom_path))

        # 2. PyInstaller bundle or script directory
        if getattr(sys, "frozen", False):
            # Running as bundled executable
            base_dir = Path(getattr(sys, "_MEIPASS", sys.executable)).parent
            candidates.append(base_dir / "ffmpeg.exe")
            candidates.append(base_dir / "bin" / "ffmpeg.exe")
            if hasattr(sys, "_MEIPASS"):
                meipass = Path(sys._MEIPASS)
                candidates.append(meipass / "ffmpeg.exe")
                candidates.append(meipass / "bin" / "ffmpeg.exe")
        else:
            # Script directory
            current_dir = Path(__file__).resolve().parent.parent.parent
            candidates.append(current_dir / "bin" / "ffmpeg.exe")
            candidates.append(current_dir / "ffmpeg.exe")

        # 3. System PATH
        system_ffmpeg = shutil.which("ffmpeg")
        if system_ffmpeg:
            candidates.append(Path(system_ffmpeg))

        for candidate in candidates:
            if candidate and candidate.is_file():
                self._ffmpeg_path = candidate.resolve()
                get_logger().info(f"FFmpeg discovered at: {self._ffmpeg_path}")
                return self._ffmpeg_path

        error_msg = (
            "FFmpeg executable not found! Please ensure FFmpeg is installed and added to "
            "system PATH, or place ffmpeg.exe in the application directory."
        )
        get_logger().error(error_msg)
        raise FFmpegNotFoundError(error_msg)

    def probe_media(self, media_path: Path) -> Tuple[bool, bool, float]:
        """
        Probe a media file using FFmpeg to verify:
        - Returns (is_valid, has_audio, duration_seconds)
        """
        ffmpeg_bin = self.find_ffmpeg()
        media_path = Path(media_path).resolve()

        if not media_path.is_file():
            get_logger().error(f"Media file does not exist: {media_path}")
            return False, False, 0.0

        if media_path.stat().st_size == 0:
            get_logger().error(f"Media file is 0 bytes: {media_path}")
            return False, False, 0.0

        cmd = [
            str(ffmpeg_bin),
            "-hide_banner",
            "-i",
            str(media_path),
        ]

        try:
            # FFmpeg outputs file probe details to stderr
            result = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace",
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
            )
            stderr = result.stderr

            has_audio = "Audio:" in stderr
            duration = 0.0

            # Parse Duration: HH:MM:SS.xx
            dur_match = re.search(r"Duration:\s*(\d{2}):(\d{2}):(\d{2}\.\d+)", stderr)
            if dur_match:
                h = int(dur_match.group(1))
                m = int(dur_match.group(2))
                s = float(dur_match.group(3))
                duration = h * 3600 + m * 60 + s

            is_valid = ("Duration:" in stderr or "Input #" in stderr)
            return is_valid, has_audio, duration

        except Exception as e:
            get_logger().error(f"Error probing media file '{media_path}': {e}")
            return False, False, 0.0

    def extract_audio(
        self,
        video_path: Path,
        output_wav_path: Optional[Path] = None,
        duration_seconds: Optional[float] = None,
        is_cancelled: Optional[Callable[[], bool]] = None,
        progress_callback: Optional[Callable[[str], None]] = None,
    ) -> Path:
        """
        Extract audio track from video file into 16kHz 16-bit mono PCM WAV.
        Supports cooperative cancellation. Skips duplicate probe if duration_seconds is provided.
        """
        ffmpeg_bin = self.find_ffmpeg()
        video_path = Path(video_path).resolve()

        if duration_seconds is not None and duration_seconds > 0:
            duration = duration_seconds
        else:
            is_valid, has_audio, duration = self.probe_media(video_path)
            if not is_valid:
                raise ValueError(f"Input file is not a recognized media container: {video_path}")
            if not has_audio:
                raise NoAudioStreamError(f"Media file contains no audio track: {video_path.name}")

        if output_wav_path is None:
            # Create a unique temporary wav file in user temp dir
            temp_dir = get_temp_dir()
            clean_stem = re.sub(r"[^\w\-_]", "_", video_path.stem)
            output_wav_path = temp_dir / f"{clean_stem}_{os.getpid()}_{id(video_path)}.wav"

        output_wav_path = Path(output_wav_path).resolve()
        output_wav_path.parent.mkdir(parents=True, exist_ok=True)

        if output_wav_path.is_file():
            try:
                output_wav_path.unlink()
            except OSError:
                pass

        if progress_callback:
            progress_callback("Extracting audio with FFmpeg...")

        cmd = [
            str(ffmpeg_bin),
            "-y",
            "-nostdin",
            "-threads",
            "0",
            "-i",
            str(video_path),
            "-vn",
            "-sn",
            "-dn",
            "-acodec",
            "pcm_s16le",
            "-ar",
            "16000",
            "-ac",
            "1",
            str(output_wav_path),
        ]

        get_logger().info(f"Extracting audio from '{video_path.name}' -> '{output_wav_path.name}'")

        process = subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
        )

        import threading

        stderr_lines = []

        def _drain_stderr():
            try:
                for line in iter(process.stderr.readline, ""):
                    if not line:
                        break
                    stderr_lines.append(line)
                    if progress_callback:
                        m = re.search(r"time=(\d{2}):(\d{2}):(\d{2})", line)
                        if m:
                            cur_s = int(m.group(1)) * 3600 + int(m.group(2)) * 60 + int(m.group(3))
                            if duration > 0:
                                pct = min(99.0, (cur_s / duration) * 100.0)
                                progress_callback(f"Extracting audio: {pct:.0f}%...")
            except Exception:
                pass

        reader_thread = threading.Thread(target=_drain_stderr, daemon=True)
        reader_thread.start()

        try:
            while process.poll() is None:
                if is_cancelled and is_cancelled():
                    get_logger().info(f"Audio extraction cancelled for '{video_path.name}'. Terminating FFmpeg.")
                    process.terminate()
                    try:
                        process.wait(timeout=2)
                    except subprocess.TimeoutExpired:
                        process.kill()
                    self._safe_remove(output_wav_path)
                    raise InterruptedError("Audio extraction cancelled by user.")

                try:
                    process.wait(timeout=0.2)
                except subprocess.TimeoutExpired:
                    continue

            return_code = process.returncode
            reader_thread.join(timeout=1.0)

            if return_code != 0:
                self._safe_remove(output_wav_path)
                full_stderr = "".join(stderr_lines)
                raise RuntimeError(f"FFmpeg audio extraction failed (code {return_code}): {full_stderr.strip()}")

            if not output_wav_path.is_file() or output_wav_path.stat().st_size == 0:
                self._safe_remove(output_wav_path)
                raise RuntimeError(f"Extracted audio file is missing or empty: {output_wav_path}")

            get_logger().info(
                f"Audio extraction completed successfully: {output_wav_path.stat().st_size / (1024*1024):.2f} MB"
            )
            return output_wav_path

        except Exception:
            if process.poll() is None:
                process.kill()
            self._safe_remove(output_wav_path)
            raise

    @staticmethod
    def _safe_remove(path: Path) -> None:
        """Safely remove a file without raising exceptions."""
        try:
            if path and path.is_file():
                path.unlink()
        except OSError:
            pass
