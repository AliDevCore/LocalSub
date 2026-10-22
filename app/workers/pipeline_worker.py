"""
LocalSub - Background Pipeline Worker Thread.
Executes batch video queue in a dedicated QThread to guarantee
UI responsiveness, real-time progress events, and responsive cancellation.
"""

from __future__ import annotations

import copy
import time
from typing import List, Optional

from PySide6.QtCore import QObject, QThread, Signal

from app.core.config import AppSettings
from app.core.types import FileQueueItem, ProcessingStatus
from app.services.logging_service import get_logger
from app.services.pipeline import SubtitlePipeline


class PipelineWorkerSignals(QObject):
    """Qt signals emitted by the background pipeline worker."""
    item_started = Signal(str)  # item_id
    item_progress = Signal(str, str, float)  # item_id, step_name, progress_pct
    item_finished = Signal(str, bool, str)  # item_id, success, message
    queue_progress = Signal(int, int)  # completed_count, total_count
    all_completed = Signal(int, int)  # total_success, total_failed
    cancelled = Signal()
    error_occurred = Signal(str)  # global fatal error message


class PipelineWorker(QThread):
    """QThread worker processing a queue of video items."""

    def __init__(
        self,
        queue_items: List[FileQueueItem],
        settings: AppSettings,
        pipeline: Optional[SubtitlePipeline] = None,
        parent: Optional[QObject] = None,
    ):
        super().__init__(parent)
        self.queue_items = queue_items
        self.settings = copy.deepcopy(settings)
        self.pipeline = pipeline or SubtitlePipeline()
        self.signals = PipelineWorkerSignals()
        self._is_cancelled = False

    def cancel(self) -> None:
        """Signal cooperative cancellation to pipeline and worker."""
        get_logger().info("Cancel signal received by PipelineWorker.")
        self._is_cancelled = True

    def is_cancelled(self) -> bool:
        return self._is_cancelled

    def run(self) -> None:
        """Main thread execution loop."""
        total = len(self.queue_items)
        success_count = 0
        failed_count = 0

        get_logger().info(f"PipelineWorker started with {total} items.")

        try:
            for idx, item in enumerate(self.queue_items):
                if self._is_cancelled:
                    get_logger().info("Pipeline loop detected cancellation before processing next item.")
                    item.status = ProcessingStatus.CANCELLED
                    item.current_step = "Cancelled"
                    self.signals.item_finished.emit(item.id, False, "Cancelled by user")
                    break

                # Skip items that are already completed
                if item.status == ProcessingStatus.COMPLETED:
                    success_count += 1
                    self.signals.queue_progress.emit(idx + 1, total)
                    continue

                self.signals.item_started.emit(item.id)

                def on_progress(it: FileQueueItem, step: str, pct: float) -> None:
                    self.signals.item_progress.emit(it.id, step, pct)

                try:
                    out_path = self.pipeline.process_item(
                        item=item,
                        settings=self.settings,
                        progress_callback=on_progress,
                        is_cancelled=self.is_cancelled,
                    )
                    success_count += 1
                    msg = f"Saved: {out_path.name}" if out_path else "Completed (No speech detected)"
                    self.signals.item_finished.emit(item.id, True, msg)
                except InterruptedError:
                    item.status = ProcessingStatus.CANCELLED
                    item.current_step = "Cancelled"
                    self.signals.item_finished.emit(item.id, False, "Processing cancelled")
                    break
                except Exception as e:
                    failed_count += 1
                    item.status = ProcessingStatus.FAILED
                    item.error_message = str(e)
                    self.signals.item_finished.emit(item.id, False, str(e))
                    # Individual file failure does NOT abort remaining queue
                    get_logger().error(f"Error processing item '{item.file_path.name}': {e}")

                self.signals.queue_progress.emit(idx + 1, total)

            if self._is_cancelled:
                self.signals.cancelled.emit()
            else:
                self.signals.all_completed.emit(success_count, failed_count)

            get_logger().info(
                f"PipelineWorker finished: {success_count} succeeded, {failed_count} failed."
            )
        finally:
            # Unload neural network models from memory upon queue completion or cancellation
            get_logger().info("PipelineWorker cleanup: Releasing AI models from memory...")
            self.pipeline.unload_models()
