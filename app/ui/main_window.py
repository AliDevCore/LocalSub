"""
LocalSub - Main Application Window.
Integrates Model Configuration, File Queue Management, Asynchronous Processing,
Real-time Progress Reporting, and Windows 11 Fluent UX.
"""

from __future__ import annotations

import os
import subprocess
import sys
import uuid
from pathlib import Path
from typing import List, Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QDragEnterEvent, QDropEvent, QIcon
from PySide6.QtWidgets import (
    QCheckBox,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.core.config import (
    APP_NAME,
    APP_TITLE,
    APP_VERSION,
    SUPPORTED_VIDEO_EXTENSIONS,
    AppSettings,
)
from app.core.types import FileQueueItem, ProcessingStatus, TargetLanguage
from app.services.ffmpeg_service import FFmpegService
from app.services.logging_service import get_logger, open_logs_directory
from app.services.model_manager import ModelManager
from app.services.pipeline import SubtitlePipeline
from app.ui.components.file_queue_table import FileQueueTable
from app.ui.components.log_viewer_dialog import LogViewerDialog
from app.ui.components.model_selector import ModelSelectorWidget
from app.ui.styles import APP_STYLESHEET
from app.workers.model_download_worker import ModelDownloadWorker
from app.workers.pipeline_worker import PipelineWorker


class MainWindow(QMainWindow):
    """LocalSub main application window."""

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setWindowTitle(f"{APP_TITLE} (v{APP_VERSION})")
        self.resize(1000, 720)
        self.setMinimumSize(850, 580)
        self.setAcceptDrops(True)

        self.settings = AppSettings.load()
        self.model_manager = ModelManager()
        self.ffmpeg_service = FFmpegService(custom_path=self.settings.custom_ffmpeg_path or None)
        self.pipeline = SubtitlePipeline(
            ffmpeg_service=self.ffmpeg_service,
            model_manager=self.model_manager,
        )

        self.queue_items: List[FileQueueItem] = []
        self._current_worker: Optional[PipelineWorker] = None
        self._download_worker: Optional[ModelDownloadWorker] = None

        self._setup_ui()
        self.setStyleSheet(APP_STYLESHEET)

        # Pre-check FFmpeg
        try:
            self.ffmpeg_service.find_ffmpeg()
        except Exception as e:
            get_logger().warning(f"FFmpeg not found initially: {e}")

    def _setup_ui(self) -> None:
        central_widget = QWidget(self)
        central_widget.setObjectName("CentralWidget")
        self.setCentralWidget(central_widget)

        root_layout = QVBoxLayout(central_widget)
        root_layout.setContentsMargins(20, 16, 20, 16)
        root_layout.setSpacing(14)

        # 1. Header Bar
        header_layout = QHBoxLayout()
        header_text_layout = QVBoxLayout()
        lbl_title = QLabel(APP_NAME)
        lbl_title.setObjectName("HeaderTitle")
        lbl_subtitle = QLabel("Local AI Video Subtitle Transcription & Neural Persian Translation")
        lbl_subtitle.setObjectName("HeaderSubtitle")
        header_text_layout.addWidget(lbl_title)
        header_text_layout.addWidget(lbl_subtitle)
        header_layout.addLayout(header_text_layout)
        header_layout.addStretch()

        btn_about = QPushButton("About / Help")
        btn_about.clicked.connect(self._show_about_dialog)
        header_layout.addWidget(btn_about)
        root_layout.addLayout(header_layout)

        # 2. Model Configuration Widget
        self.model_selector = ModelSelectorWidget(
            settings=self.settings,
            model_manager=self.model_manager,
            parent=self,
        )
        self.model_selector.download_requested.connect(self._on_download_requested)
        self.model_selector.settings_changed.connect(self._on_settings_changed)
        root_layout.addWidget(self.model_selector)

        # 3. Output Directory & Queue Options Group
        opts_group = QGroupBox("Output & Queue Settings")
        opts_layout = QVBoxLayout(opts_group)
        opts_layout.setContentsMargins(16, 16, 16, 16)
        opts_layout.setSpacing(10)

        dir_row = QHBoxLayout()
        dir_row.setSpacing(10)
        lbl_out = QLabel("Output Folder:")
        self.edit_output_dir = QLineEdit()
        self.edit_output_dir.setPlaceholderText("Leave empty to save next to video file")
        self.edit_output_dir.setText(self.settings.last_output_dir)
        self.edit_output_dir.textChanged.connect(self._on_output_dir_changed)

        btn_browse_out = QPushButton("Browse...")
        btn_browse_out.clicked.connect(self._browse_output_dir)

        dir_row.addWidget(lbl_out)
        dir_row.addWidget(self.edit_output_dir, stretch=1)
        dir_row.addWidget(btn_browse_out)
        opts_layout.addLayout(dir_row)

        chk_row = QHBoxLayout()
        chk_row.setSpacing(24)

        self.chk_save_en = QCheckBox("ذخیره هم‌زمان زیرنویس انگلیسی در حالت فارسی (Also save English .en.srt)")
        self.chk_save_en.setChecked(self.settings.save_original_english)
        self.chk_save_en.setToolTip("در صورت انتخاب زبان فارسی، زیرنویس اصلی انگلیسی نیز به صورت جداگانه در کنار فایل فارسی ذخیره می‌شود")
        self.chk_save_en.toggled.connect(self._on_save_en_toggled)

        self.chk_overwrite = QCheckBox("Overwrite existing .srt files")
        self.chk_overwrite.setChecked(self.settings.overwrite_existing)
        self.chk_overwrite.toggled.connect(self._on_overwrite_toggled)

        chk_row.addWidget(self.chk_save_en)
        chk_row.addWidget(self.chk_overwrite)
        chk_row.addStretch()
        opts_layout.addLayout(chk_row)

        root_layout.addWidget(opts_group)

        # 4. Video Files Queue Group
        queue_group = QGroupBox("Video Files Queue")
        queue_layout = QVBoxLayout(queue_group)
        queue_layout.setContentsMargins(16, 16, 16, 16)
        queue_layout.setSpacing(10)

        queue_btn_layout = QHBoxLayout()
        btn_add_files = QPushButton("Add Video Files...")
        btn_add_files.setObjectName("PrimaryButton")
        btn_add_files.clicked.connect(self._browse_video_files)

        btn_add_folder = QPushButton("Add Folder...")
        btn_add_folder.clicked.connect(self._browse_video_folder)

        btn_remove = QPushButton("Remove Selected")
        btn_remove.clicked.connect(self._remove_selected_file)

        btn_clear = QPushButton("Clear All")
        btn_clear.clicked.connect(self._clear_queue)

        queue_btn_layout.addWidget(btn_add_files)
        queue_btn_layout.addWidget(btn_add_folder)
        queue_btn_layout.addWidget(btn_remove)
        queue_btn_layout.addWidget(btn_clear)
        queue_btn_layout.addStretch()

        self.lbl_queue_count = QLabel("0 files in queue")
        queue_btn_layout.addWidget(self.lbl_queue_count)
        queue_layout.addLayout(queue_btn_layout)

        # Queue Table
        self.table_queue = FileQueueTable(self)
        self.table_queue.item_removed.connect(self._on_item_removed_from_table)
        queue_layout.addWidget(self.table_queue)
        root_layout.addWidget(queue_group, stretch=1)

        # 5. Bottom Action & Execution Bar
        bottom_layout = QHBoxLayout()
        bottom_layout.setSpacing(14)

        self.btn_start = QPushButton("Start Subtitling")
        self.btn_start.setObjectName("PrimaryButton")
        self.btn_start.setMinimumHeight(38)
        self.btn_start.setStyleSheet("font-size: 14px; font-weight: 700; padding: 6px 24px;")
        self.btn_start.clicked.connect(self._start_processing)

        self.btn_cancel = QPushButton("Cancel")
        self.btn_cancel.setObjectName("CancelButton")
        self.btn_cancel.setMinimumHeight(38)
        self.btn_cancel.setEnabled(False)
        self.btn_cancel.clicked.connect(self._cancel_processing)

        bottom_layout.addWidget(self.btn_start)
        bottom_layout.addWidget(self.btn_cancel)

        # Overall Queue Progress
        self.total_pbar = QProgressBar()
        self.total_pbar.setRange(0, 100)
        self.total_pbar.setValue(0)
        self.total_pbar.setTextVisible(True)
        self.total_pbar.setFormat("Ready")
        bottom_layout.addWidget(self.total_pbar, stretch=1)

        btn_open_out = QPushButton("Open Output Folder")
        btn_open_out.clicked.connect(self._open_output_folder)

        btn_view_logs = QPushButton("View Logs")
        btn_view_logs.clicked.connect(self._open_log_viewer)

        bottom_layout.addWidget(btn_open_out)
        bottom_layout.addWidget(btn_view_logs)
        root_layout.addLayout(bottom_layout)

    # --------------------------------------------------------------------------
    # Drag & Drop Support
    # --------------------------------------------------------------------------

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent) -> None:
        file_paths = []
        for url in event.mimeData().urls():
            local_file = Path(url.toLocalFile())
            if local_file.is_file() and local_file.suffix.lower() in SUPPORTED_VIDEO_EXTENSIONS:
                file_paths.append(local_file)
            elif local_file.is_dir():
                for p in local_file.rglob("*"):
                    if p.is_file() and p.suffix.lower() in SUPPORTED_VIDEO_EXTENSIONS:
                        file_paths.append(p)
        if file_paths:
            self._add_files_to_queue(file_paths)
            event.acceptProposedAction()

    # --------------------------------------------------------------------------
    # Queue Management
    # --------------------------------------------------------------------------

    def _browse_video_files(self) -> None:
        ext_filter = "Video Files (*.mp4 *.mkv *.avi *.mov *.wmv *.m4v *.webm *.flv *.ts);;All Files (*.*)"
        files, _ = QFileDialog.getOpenFileNames(
            self,
            "Select Video Files",
            self.settings.last_input_dir or "",
            ext_filter,
        )
        if files:
            paths = [Path(f) for f in files]
            self.settings.last_input_dir = str(paths[0].parent)
            self.settings.save()
            self._add_files_to_queue(paths)

    def _browse_video_folder(self) -> None:
        folder = QFileDialog.getExistingDirectory(
            self,
            "Select Folder with Video Files",
            self.settings.last_input_dir or "",
        )
        if folder:
            f_path = Path(folder)
            self.settings.last_input_dir = folder
            self.settings.save()
            found_paths = [
                p
                for p in f_path.rglob("*")
                if p.is_file() and p.suffix.lower() in SUPPORTED_VIDEO_EXTENSIONS
            ]
            if found_paths:
                self._add_files_to_queue(found_paths)
            else:
                QMessageBox.information(
                    self, "No Videos Found", f"No supported video files found in:\n{folder}"
                )

    def _add_files_to_queue(self, paths: List[Path]) -> None:
        existing_paths = {item.file_path for item in self.queue_items}
        added_count = 0

        for p in paths:
            if p in existing_paths:
                continue

            # Determine destination SRT path
            out_srt = self._compute_srt_path(p)

            item = FileQueueItem(
                id=str(uuid.uuid4()),
                file_path=p,
                output_srt_path=out_srt,
                status=ProcessingStatus.QUEUED,
            )
            self.queue_items.append(item)
            self.table_queue.add_queue_item(item)
            added_count += 1

        self.lbl_queue_count.setText(f"{len(self.queue_items)} files in queue")
        get_logger().info(f"Added {added_count} video files to queue. Total: {len(self.queue_items)}")

    def _compute_srt_path(self, video_path: Path) -> Path:
        """Compute output SRT path according to target language and output settings."""
        lang_suffix = ".fa.srt" if self.settings.target_language == TargetLanguage.PERSIAN.value else ".en.srt"
        base_name = f"{video_path.stem}{lang_suffix}"

        if self.settings.last_output_dir and Path(self.settings.last_output_dir).is_dir():
            return Path(self.settings.last_output_dir) / base_name
        return video_path.parent / base_name

    def _remove_selected_file(self) -> None:
        self.table_queue.remove_selected_item()

    def _on_item_removed_from_table(self, item_id: str) -> None:
        self.queue_items = [it for it in self.queue_items if it.id != item_id]
        self.lbl_queue_count.setText(f"{len(self.queue_items)} files in queue")

    def _clear_queue(self) -> None:
        if self._current_worker and self._current_worker.isRunning():
            QMessageBox.warning(self, "Busy", "Cannot clear queue while processing is active.")
            return
        self.queue_items.clear()
        self.table_queue.clear_all_items()
        self.lbl_queue_count.setText("0 files in queue")

    # --------------------------------------------------------------------------
    # Output Directory & Settings Callbacks
    # --------------------------------------------------------------------------

    def _browse_output_dir(self) -> None:
        dir_path = QFileDialog.getExistingDirectory(
            self,
            "Select Output Subtitle Directory",
            self.settings.last_output_dir or "",
        )
        if dir_path:
            self.edit_output_dir.setText(dir_path)

    def _on_output_dir_changed(self, text: str) -> None:
        self.settings.last_output_dir = text.strip()
        self.settings.save()
        # Update output paths in queue
        self._update_all_output_paths()

    def _on_overwrite_toggled(self, checked: bool) -> None:
        self.settings.overwrite_existing = checked
        self.settings.save()

    def _on_save_en_toggled(self, checked: bool) -> None:
        self.settings.save_original_english = checked
        self.settings.save()

    def _on_settings_changed(self) -> None:
        # Re-compute destination SRT extensions (.en.srt vs .fa.srt)
        self._update_all_output_paths()

    def _update_all_output_paths(self) -> None:
        for it in self.queue_items:
            it.output_srt_path = self._compute_srt_path(it.file_path)
            # Update table widget display
            row = self.table_queue._find_row_by_id(it.id)
            if row is not None:
                out_item = self.table_queue.item(row, FileQueueTable.COL_OUTPUT)
                if out_item:
                    out_item.setText(it.output_srt_path.name)
                    out_item.setToolTip(str(it.output_srt_path))

    # --------------------------------------------------------------------------
    # Model Download Handling
    # --------------------------------------------------------------------------

    def _on_download_requested(self, category: str, identifier: str) -> None:
        if self._download_worker and self._download_worker.isRunning():
            QMessageBox.information(self, "Download in Progress", "A model download is already running.")
            return

        self.model_selector.show_download_progress(f"Starting download for {identifier}...", 5.0)
        self._download_worker = ModelDownloadWorker(
            model_type=category,
            model_identifier=identifier,
            model_manager=self.model_manager,
            parent=self,
        )
        self._download_worker.signals.progress.connect(
            lambda msg, pct: self.model_selector.show_download_progress(msg, pct)
        )
        self._download_worker.signals.finished.connect(self._on_model_download_finished)
        self._download_worker.start()

    def _on_model_download_finished(self, success: bool, message: str) -> None:
        self.model_selector.hide_download_progress()
        self.model_selector.refresh_status()
        if success:
            QMessageBox.information(self, "Download Complete", message)
        else:
            QMessageBox.critical(self, "Download Failed", message)

    # --------------------------------------------------------------------------
    # Processing Pipeline Execution
    # --------------------------------------------------------------------------

    def _start_processing(self) -> None:
        if not self.queue_items:
            QMessageBox.information(self, "Empty Queue", "Please add at least one video file to the queue.")
            return

        # Pre-check FFmpeg
        try:
            self.ffmpeg_service.find_ffmpeg()
        except Exception as e:
            QMessageBox.critical(
                self,
                "FFmpeg Error",
                f"Cannot start processing: {e}\nPlease ensure FFmpeg is installed or in system PATH.",
            )
            return

        # Pre-check AI models readiness
        summary = self.model_manager.get_status_summary(
            whisper_size=self.settings.whisper_model,
            translation_type=self.settings.translation_model,
            target_lang=self.settings.target_language,
        )

        missing_models = []
        if not summary["whisper_ready"]:
            missing_models.append(f"Speech Recognition ({summary['whisper_size']}, ~{summary['whisper_size_mb']} MB)")
        if summary["translation_required"] and not summary["translation_ready"]:
            missing_models.append(f"Translation Model ({summary['translation_type']}, ~{summary['translation_size_mb']} MB)")

        if missing_models:
            from app.ui.components.model_import_dialog import ModelImportDialog

            msg = (
                "مدل‌های هوش مصنوعی مورد نیاز هنوز نصب نشده‌اند:\n\n• "
                + "\n• ".join(missing_models)
                + "\n\nآیا مایلید پنجره دریافت لینک دانلود و وارد کردن فایل زیپ مدل باز شود؟"
            )
            reply = QMessageBox.question(
                self,
                "مدل‌های هوش مصنوعی آماده نیستند",
                msg,
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if reply == QMessageBox.StandardButton.Yes:
                if not summary["whisper_ready"]:
                    dlg = ModelImportDialog("whisper", self.settings.whisper_model, self.model_manager, self)
                    dlg.exec()
                elif summary["translation_required"] and not summary["translation_ready"]:
                    dlg = ModelImportDialog("translation", self.settings.translation_model, self.model_manager, self)
                    dlg.exec()
                self.model_selector.refresh_status()
            return

        # Toggle UI state
        self.btn_start.setEnabled(False)
        self.btn_cancel.setEnabled(True)
        self.total_pbar.setValue(0)
        self.total_pbar.setFormat("Processing queue: 0 / %m")

        # Launch background worker
        self._current_worker = PipelineWorker(
            queue_items=self.queue_items,
            settings=self.settings,
            pipeline=self.pipeline,
            parent=self,
        )
        self._current_worker.signals.item_progress.connect(self._on_item_progress)
        self._current_worker.signals.item_finished.connect(self._on_item_finished)
        self._current_worker.signals.queue_progress.connect(self._on_queue_progress)
        self._current_worker.signals.all_completed.connect(self._on_all_completed)
        self._current_worker.signals.cancelled.connect(self._on_pipeline_cancelled)
        self._current_worker.start()

    def _cancel_processing(self) -> None:
        if self._current_worker and self._current_worker.isRunning():
            self.btn_cancel.setEnabled(False)
            self.total_pbar.setFormat("Cancelling processing...")
            self._current_worker.cancel()

    def _on_item_progress(self, item_id: str, step_name: str, pct: float) -> None:
        self.table_queue.update_item_progress(item_id, step_name, pct)

    def _on_item_finished(self, item_id: str, success: bool, message: str) -> None:
        self.table_queue.update_item_finished(item_id, success, message)

    def _on_queue_progress(self, completed: int, total: int) -> None:
        pct = int((completed / total) * 100)
        self.total_pbar.setValue(pct)
        self.total_pbar.setFormat(f"Queue Progress: {completed} / {total} files ({pct}%)")

    def _on_all_completed(self, success_count: int, failed_count: int) -> None:
        self.btn_start.setEnabled(True)
        self.btn_cancel.setEnabled(False)
        self.total_pbar.setValue(100)
        self.total_pbar.setFormat(f"Finished: {success_count} succeeded, {failed_count} failed")
        self.model_selector.refresh_status()

        msg = f"Queue processing complete!\n\n• Succeeded: {success_count}\n• Failed: {failed_count}"
        if failed_count == 0:
            QMessageBox.information(self, "Processing Finished", msg)
        else:
            QMessageBox.warning(self, "Processing Finished with Errors", msg)

    def _on_pipeline_cancelled(self) -> None:
        self.btn_start.setEnabled(True)
        self.btn_cancel.setEnabled(False)
        self.total_pbar.setFormat("Processing was cancelled by user")
        QMessageBox.information(self, "Cancelled", "Processing was cancelled.")

    # --------------------------------------------------------------------------
    # Utility Actions
    # --------------------------------------------------------------------------

    def _open_output_folder(self) -> None:
        out_dir = self.settings.last_output_dir
        if out_dir and Path(out_dir).is_dir():
            target = Path(out_dir)
        elif self.queue_items:
            target = self.queue_items[0].output_srt_path.parent
        else:
            target = Path.home()

        try:
            if sys.platform == "win32":
                os.startfile(str(target))  # type: ignore[attr-defined]
            else:
                subprocess.run(["xdg-open", str(target)], check=False)
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to open folder: {e}")

    def _open_log_viewer(self) -> None:
        dlg = LogViewerDialog(self)
        dlg.exec()

    def _show_about_dialog(self) -> None:
        msg = (
            f"<b>{APP_TITLE}</b><br>"
            f"Version {APP_VERSION}<br><br>"
            "A high-performance Windows desktop application for 100% local video subtitle generation and neural Persian translation.<br><br>"
            "<b>Key Features:</b><br>"
            "• Local speech recognition with <code>faster-whisper</code> on CPU (INT8).<br>"
            "• Local neural translation to Persian using <code>Meta NLLB-200</code> / <code>Opus-MT</code>.<br>"
            "• 100% offline and private: zero cloud API calls or telemetry.<br>"
            "• SubRip (.srt) standard formatting with exact timestamp preservation.<br>"
            "• Batch video processing with non-blocking UI and cancellation.<br><br>"
            "Licensed under MIT License."
        )
        QMessageBox.about(self, f"About {APP_NAME}", msg)
