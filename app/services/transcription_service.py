"""
LocalSub - Speech-to-Text Transcription Service.
Wraps faster-whisper on CPU with INT8 quantization, yielding timestamped
dialogue segments with progress reporting and cancellation support.
"""

from __future__ import annotations

import gc
from pathlib import Path
from typing import Callable, Iterator, List, Optional

from faster_whisper import WhisperModel

from app.core.types import SubtitleSegment, WhisperModelSize, WordTiming
from app.services.logging_service import get_logger
from app.services.model_manager import ModelManager


class TranscriptionService:
    """Performs local speech recognition using faster-whisper on CPU."""

    def __init__(self, model_manager: Optional[ModelManager] = None):
        self.model_manager = model_manager or ModelManager()
        self._loaded_model: Optional[WhisperModel] = None
        self._current_model_size: Optional[str] = None
        self._current_cpu_threads: Optional[int] = None

    def load_model(
        self,
        model_size: str = WhisperModelSize.SMALL_EN.value,
        cpu_threads: Optional[int] = None,
        compute_type: str = "int8",
        progress_callback: Optional[Callable[[str, float], None]] = None,
        is_cancelled: Optional[Callable[[], bool]] = None,
    ) -> WhisperModel:
        """
        Load WhisperModel on CPU. Automatically downloads model if not present.
        Caches loaded model instance if size and thread count match.
        """
        effective_threads = int(cpu_threads) if cpu_threads is not None else (os.cpu_count() or 4)

        if (
            self._loaded_model is not None
            and self._current_model_size == model_size
            and self._current_cpu_threads == effective_threads
        ):
            return self._loaded_model

        # Ensure model is ready locally
        if not self.model_manager.is_whisper_model_ready(model_size):
            if progress_callback:
                progress_callback(f"Downloading Whisper {model_size} model...", 0.0)
            self.model_manager.download_whisper_model(
                model_size=model_size,
                progress_callback=progress_callback,
                is_cancelled=is_cancelled,
            )

        model_path = self.model_manager.get_whisper_model_path(model_size)
        get_logger().info(
            f"Loading Whisper model '{model_size}' from '{model_path}' on CPU (threads={effective_threads}, compute_type={compute_type})..."
        )

        # Release existing model if switching sizes or threads
        self.unload_model()

        if is_cancelled and is_cancelled():
            raise InterruptedError("Cancelled before model initialization.")

        # Ensure no invalid non-JSON vocabulary.json causes CTranslate2 parse error
        ModelManager._normalize_model_files(model_path)

        try:
            self._loaded_model = WhisperModel(
                model_size_or_path=str(model_path),
                device="cpu",
                compute_type=compute_type,
                cpu_threads=effective_threads,
            )
            self._current_model_size = model_size
            self._current_cpu_threads = effective_threads
            get_logger().info(f"Whisper model '{model_size}' loaded successfully (threads={effective_threads}).")
            return self._loaded_model
        except Exception as e:
            get_logger().error(f"Failed to load Whisper model from '{model_path}': {e}")
            raise RuntimeError(f"Unable to load speech recognition model: {e}")

    def unload_model(self) -> None:
        """Release loaded model from memory to free CPU RAM."""
        if self._loaded_model is not None:
            get_logger().info(f"Unloading Whisper model '{self._current_model_size}' from memory.")
            del self._loaded_model
            self._loaded_model = None
            self._current_model_size = None
            self._current_cpu_threads = None
            gc.collect()

    def transcribe_audio(
        self,
        audio_path: Path,
        duration_seconds: Optional[float] = None,
        model_size: str = WhisperModelSize.SMALL_EN.value,
        cpu_threads: Optional[int] = None,
        compute_type: str = "int8",
        progress_callback: Optional[Callable[[str, float], None]] = None,
        is_cancelled: Optional[Callable[[], bool]] = None,
    ) -> List[SubtitleSegment]:
        """
        Transcribe audio file into a list of SubtitleSegment instances.
        Enforces English language recognition ('en').
        """
        audio_path = Path(audio_path).resolve()
        if not audio_path.is_file():
            raise FileNotFoundError(f"Audio file not found: {audio_path}")

        effective_threads = int(cpu_threads) if cpu_threads is not None else (os.cpu_count() or 4)

        model = self.load_model(
            model_size=model_size,
            cpu_threads=effective_threads,
            compute_type=compute_type,
            progress_callback=progress_callback,
            is_cancelled=is_cancelled,
        )

        get_logger().info(f"Starting speech transcription for '{audio_path.name}' (language='en', threads={effective_threads}).")
        if progress_callback:
            progress_callback("Transcribing speech with faster-whisper...", 5.0)

        # Fast and accurate speech transcription:
        # - beam_size=2: Fast search space evaluation with high English accuracy
        # - word_timestamps=False: High inference speed without token-level DTW alignment overhead
        # - condition_on_previous_text=True: Ensures rapid context-aware decoding across 30s windows
        # - vad_filter=True: Skips non-speech audio segments using Silero VAD
        segments_generator, info = model.transcribe(
            str(audio_path),
            language="en",
            task="transcribe",
            beam_size=2,
            word_timestamps=False,
            vad_filter=True,
            vad_parameters=dict(min_silence_duration_ms=500),
            condition_on_previous_text=True,
        )

        # Check detected language confidence
        detected_lang = getattr(info, "language", "en")
        lang_prob = getattr(info, "language_probability", 1.0)
        if detected_lang != "en" and lang_prob > 0.6:
            get_logger().warning(
                f"Audio in '{audio_path.name}' may not be English! Detected: '{detected_lang}' (confidence: {lang_prob:.1%})."
            )

        audio_duration = duration_seconds or getattr(info, "duration", 0.0) or 1.0

        subtitle_segments: List[SubtitleSegment] = []
        seg_index = 1

        for seg in segments_generator:
            if is_cancelled and is_cancelled():
                get_logger().info("Transcription cancelled by user.")
                raise InterruptedError("Speech transcription cancelled by user.")

            raw_text = seg.text.strip()
            if not raw_text:
                continue

            words_data: List[WordTiming] = []
            if getattr(seg, "words", None):
                for w in seg.words:
                    words_data.append(
                        WordTiming(
                            word=w.word,
                            start=float(w.start),
                            end=float(w.end),
                            probability=float(getattr(w, "probability", 1.0)),
                        )
                    )

            subtitle_segment = SubtitleSegment(
                index=seg_index,
                start=float(seg.start),
                end=float(seg.end),
                text=raw_text,
                words=words_data,
            )
            subtitle_segments.append(subtitle_segment)
            seg_index += 1

            if progress_callback and audio_duration > 0:
                current_time = float(seg.end)
                pct = min(98.0, 5.0 + (current_time / audio_duration) * 90.0)
                progress_callback(f"Transcribed {len(subtitle_segments)} segments...", pct)

        get_logger().info(
            f"Speech transcription complete: {len(subtitle_segments)} segments extracted."
        )
        if progress_callback:
            progress_callback(f"Transcription finished: {len(subtitle_segments)} segments.", 100.0)

        return subtitle_segments
