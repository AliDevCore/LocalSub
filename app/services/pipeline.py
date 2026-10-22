"""
LocalSub - Complete Pipeline Execution Service.
Coordinates Audio Extraction -> Speech Recognition -> (Optional) Translation -> Atomic SRT Writing.
Enforces cancellation checks, resource cleanup, and validation at every boundary.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Callable, List, Optional

from app.core.config import AppSettings, get_temp_dir
from app.core.srt_formatter import write_srt_atomic
from app.core.types import FileQueueItem, ProcessingStatus, SubtitleSegment, TargetLanguage
from app.services.ffmpeg_service import FFmpegService
from app.services.logging_service import get_logger
from app.services.model_manager import ModelManager
from app.services.transcription_service import TranscriptionService
from app.services.translation_service import TranslationService


class SubtitlePipeline:
    """End-to-end execution pipeline for video subtitle extraction and translation."""

    def __init__(
        self,
        ffmpeg_service: Optional[FFmpegService] = None,
        model_manager: Optional[ModelManager] = None,
        transcription_service: Optional[TranscriptionService] = None,
        translation_service: Optional[TranslationService] = None,
    ):
        self.model_manager = model_manager or ModelManager()
        self.ffmpeg_service = ffmpeg_service or FFmpegService()
        self.transcription_service = (
            transcription_service or TranscriptionService(self.model_manager)
        )
        self.translation_service = (
            translation_service or TranslationService(self.model_manager)
        )

    def process_item(
        self,
        item: FileQueueItem,
        settings: AppSettings,
        progress_callback: Optional[Callable[[FileQueueItem, str, float], None]] = None,
        is_cancelled: Optional[Callable[[], bool]] = None,
    ) -> Path:
        """
        Process a single FileQueueItem through the end-to-end pipeline.
        
        Args:
            item: Video queue item with file path and target SRT path.
            settings: User configuration (models, language, cpu threads).
            progress_callback: Callback(item, step_description, percent).
            is_cancelled: Cancellation predicate function.
            
        Returns:
            Path to the generated, verified SRT file.
        """
        video_path = item.file_path.resolve()
        target_srt = item.output_srt_path.resolve()
        target_lang = settings.target_language
        is_persian = target_lang == TargetLanguage.PERSIAN.value

        get_logger().info(f"--- Starting pipeline for: '{video_path.name}' (Target: {target_lang}) ---")

        # 1. Pre-flight check: Destination file existence check
        if target_srt.exists() and not settings.overwrite_existing:
            err = f"Destination SRT already exists: '{target_srt.name}'. Overwrite disabled."
            get_logger().warning(err)
            item.status = ProcessingStatus.FAILED
            item.error_message = err
            raise FileExistsError(err)

        extracted_wav: Optional[Path] = None

        def report(step: str, pct: float) -> None:
            item.current_step = step
            item.progress = pct
            if progress_callback:
                progress_callback(item, step, pct)

        try:
            # Check cancellation
            if is_cancelled and is_cancelled():
                raise InterruptedError("Pipeline cancelled before execution started.")

            # 2. Probe Media & Audio Track
            item.status = ProcessingStatus.EXTRACTING_AUDIO
            report("Probing video container...", 2.0)

            is_valid, has_audio, duration = self.ffmpeg_service.probe_media(video_path)
            if not is_valid:
                raise ValueError(f"Invalid media file or unreadable container: '{video_path.name}'")
            if not has_audio:
                raise RuntimeError(f"Video file has no audio stream: '{video_path.name}'")

            item.duration_seconds = duration

            # 3. Audio Extraction (Pass duration to avoid duplicate probe)
            report("Extracting audio with FFmpeg...", 10.0)
            extracted_wav = self.ffmpeg_service.extract_audio(
                video_path=video_path,
                duration_seconds=duration,
                is_cancelled=is_cancelled,
                progress_callback=lambda s: report(s, 15.0),
            )

            # Check cancellation
            if is_cancelled and is_cancelled():
                raise InterruptedError("Pipeline cancelled after audio extraction.")

            # 4. Speech Recognition (English faster-whisper)
            item.status = ProcessingStatus.TRANSCRIBING
            report("Transcribing speech with faster-whisper (English)...", 20.0)

            def stt_progress(step_msg: str, pct: float) -> None:
                # Map STT progress (0-100) to overall pipeline progress (20-65 if translating, else 20-90)
                upper = 65.0 if is_persian else 92.0
                mapped_pct = 20.0 + (pct / 100.0) * (upper - 20.0)
                report(step_msg, mapped_pct)

            segments = self.transcription_service.transcribe_audio(
                audio_path=extracted_wav,
                duration_seconds=duration,
                model_size=settings.whisper_model,
                cpu_threads=settings.cpu_threads,
                compute_type=settings.compute_type,
                progress_callback=stt_progress,
                is_cancelled=is_cancelled,
            )

            if not segments:
                get_logger().info(f"No speech was detected in '{video_path.name}'.")
                item.segments_count = 0
                item.status = ProcessingStatus.COMPLETED
                item.progress = 100.0
                item.current_step = "Completed (No speech detected)"
                return None

            item.segments_count = len(segments)

            # Check cancellation
            if is_cancelled and is_cancelled():
                raise InterruptedError("Pipeline cancelled after transcription.")

            # 5. Translation Stage (Only if target language is NOT English)
            final_segments: List[SubtitleSegment] = segments

            if is_persian:
                item.status = ProcessingStatus.TRANSLATING
                report("Translating dialogue to Persian...", 68.0)

                def trans_progress(step_msg: str, pct: float) -> None:
                    # Map translation progress (0-100) to overall pipeline progress (68-94)
                    mapped_pct = 68.0 + (pct / 100.0) * 26.0
                    report(step_msg, mapped_pct)

                final_segments = self.translation_service.translate_segments(
                    segments=segments,
                    target_lang=TargetLanguage.PERSIAN.value,
                    source_lang=TargetLanguage.ENGLISH.value,
                    model_type=settings.translation_model,
                    batch_size=settings.batch_size,
                    cpu_threads=settings.cpu_threads,
                    progress_callback=trans_progress,
                    is_cancelled=is_cancelled,
                )
            else:
                get_logger().info("Target is English: Skipping translation model entirely.")

            # Check cancellation
            if is_cancelled and is_cancelled():
                raise InterruptedError("Pipeline cancelled before writing subtitles.")

            # 6. Formatting & Atomic Write to Destination SRT
            item.status = ProcessingStatus.GENERATING_SRT
            report("Writing and validating final SRT file...", 95.0)

            written_path = write_srt_atomic(
                segments=final_segments,
                destination_path=target_srt,
                overwrite=settings.overwrite_existing,
            )

            # Optionally also save original English transcript if translated
            if is_persian and getattr(settings, "save_original_english", True):
                en_srt_path = target_srt.with_name(f"{video_path.stem}.en.srt")
                try:
                    write_srt_atomic(
                        segments=segments,
                        destination_path=en_srt_path,
                        overwrite=settings.overwrite_existing,
                    )
                    get_logger().info(f"Also saved original English subtitles: '{en_srt_path}'")
                except Exception as ex:
                    get_logger().warning(f"Could not save companion English SRT: {ex}")

            item.status = ProcessingStatus.COMPLETED
            item.progress = 100.0
            item.current_step = "Completed successfully"
            get_logger().info(f"Pipeline completed successfully. Output: '{written_path}'")
            return written_path

        except InterruptedError:
            item.status = ProcessingStatus.CANCELLED
            item.current_step = "Processing cancelled"
            get_logger().info(f"Pipeline cancelled for '{video_path.name}'.")
            raise

        except Exception as e:
            item.status = ProcessingStatus.FAILED
            item.error_message = str(e)
            item.current_step = f"Failed: {e}"
            get_logger().error(f"Pipeline failed for '{video_path.name}': {e}", exc_info=True)
            raise

        finally:
            # 7. Clean up temporary audio files
            if extracted_wav and extracted_wav.is_file():
                try:
                    extracted_wav.unlink()
                    get_logger().debug(f"Removed temporary audio file: {extracted_wav}")
                except OSError:
                    pass

    def unload_models(self) -> None:
        """Unload Whisper and Translation neural networks from memory to reclaim RAM."""
        try:
            self.transcription_service.unload_model()
        except Exception as e:
            get_logger().debug(f"Error unloading speech model: {e}")
        try:
            self.translation_service.unload_backend()
        except Exception as e:
            get_logger().debug(f"Error unloading translation model: {e}")
