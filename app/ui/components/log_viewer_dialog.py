"""
LocalSub - Log Viewer Dialog.
Displays application logs in an accessible modal dialog with refresh,
clipboard copy, and open folder functionality.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.core.config import get_logs_dir
from app.services.logging_service import open_logs_directory


class LogViewerDialog(QDialog):
    """Dialog displaying application runtime logs."""

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setWindowTitle("LocalSub - Application Runtime Logs")
        self.resize(750, 480)
        self._setup_ui()
        self.refresh_logs()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)

        self.text_edit = QPlainTextEdit()
        self.text_edit.setReadOnly(True)
        self.text_edit.setStyleSheet(
            "background-color: #020617; color: #94a3b8; font-family: Consolas, monospace; font-size: 11px; padding: 8px;"
        )
        layout.addWidget(self.text_edit)

        btn_layout = QHBoxLayout()
        btn_refresh = QPushButton("Refresh")
        btn_refresh.clicked.connect(self.refresh_logs)

        btn_copy = QPushButton("Copy to Clipboard")
        btn_copy.clicked.connect(self._copy_to_clipboard)

        btn_open_folder = QPushButton("Open Logs Folder")
        btn_open_folder.clicked.connect(open_logs_directory)

        btn_close = QPushButton("Close")
        btn_close.clicked.connect(self.accept)

        btn_layout.addWidget(btn_refresh)
        btn_layout.addWidget(btn_copy)
        btn_layout.addWidget(btn_open_folder)
        btn_layout.addStretch()
        btn_layout.addWidget(btn_close)

        layout.addLayout(btn_layout)

    def refresh_logs(self) -> None:
        log_file = get_logs_dir() / "localsub.log"
        if log_file.is_file():
            try:
                # Read last 200 KB if huge
                size = log_file.stat().st_size
                max_bytes = 200 * 1024
                with open(log_file, "r", encoding="utf-8", errors="replace") as f:
                    if size > max_bytes:
                        f.seek(size - max_bytes)
                    content = f.read()
                self.text_edit.setPlainText(content)
                self.text_edit.verticalScrollBar().setValue(
                    self.text_edit.verticalScrollBar().maximum()
                )
            except Exception as e:
                self.text_edit.setPlainText(f"Failed to read log file: {e}")
        else:
            self.text_edit.setPlainText("Log file has not been created yet.")

    def _copy_to_clipboard(self) -> None:
        self.text_edit.selectAll()
        self.text_edit.copy()
        # Deselect
        cursor = self.text_edit.textCursor()
        cursor.clearSelection()
        self.text_edit.setTextCursor(cursor)
