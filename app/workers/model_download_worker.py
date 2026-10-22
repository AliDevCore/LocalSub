"""
LocalSub - Background Model Download Worker Thread.
Handles non-blocking downloading and integrity verification of Whisper and Translation models.
"""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import QObject, QThread, Signal

from app.services.logging_service import get_logger
from app.services.model_manager import ModelManager


class ModelDownloadWorkerSignals(QObject):
    progress = Signal(str, float)  # message, percentage
    finished = Signal(bool, str)  # success, message


class ModelDownloadWorker(QThread):
    """Worker thread for downloading models without blocking GUI."""

    def __init__(
        self,
        model_type: str,  # "whisper" or "translation"
        model_identifier: str,  # e.g. "small" or "nllb-200-distilled-600M"
        model_manager: Optional[ModelManager] = None,
        parent: Optional[QObject] = None,
    ):
        super().__init__(parent)
        self.model_type = model_type
        self.model_identifier = model_identifier
        self.model_manager = model_manager or ModelManager()
        self.signals = ModelDownloadWorkerSignals()
        self._is_cancelled = False

    def cancel(self) -> None:
        self._is_cancelled = True

    def is_cancelled(self) -> bool:
        return self._is_cancelled

    def run(self) -> None:
        get_logger().info(f"ModelDownloadWorker started: {self.model_type} -> {self.model_identifier}")
        try:
            if self.model_type == "whisper":
                self.model_manager.download_whisper_model(
                    model_size=self.model_identifier,
                    progress_callback=lambda msg, pct: self.signals.progress.emit(msg, pct),
                    is_cancelled=self.is_cancelled,
                )
            elif self.model_type == "translation":
                self.model_manager.download_translation_model(
                    model_type=self.model_identifier,
                    progress_callback=lambda msg, pct: self.signals.progress.emit(msg, pct),
                    is_cancelled=self.is_cancelled,
                )
            else:
                raise ValueError(f"Unknown model download category: {self.model_type}")

            self.signals.finished.emit(True, f"Model '{self.model_identifier}' downloaded and verified successfully.")
        except InterruptedError:
            self.signals.finished.emit(False, "Model download was cancelled.")
        except Exception as e:
            get_logger().error(f"Download failed for '{self.model_identifier}': {e}")
            self.signals.finished.emit(False, f"Download failed: {e}")
