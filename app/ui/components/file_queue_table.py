"""
LocalSub - File Queue Table Component.
Displays video files in queue with per-item progress bars, status labels,
output path indicators, and right-click context actions.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QHeaderView,
    QMenu,
    QProgressBar,
    QTableWidget,
    QTableWidgetItem,
    QWidget,
)

from app.core.types import FileQueueItem, ProcessingStatus


class FileQueueTable(QTableWidget):
    """Table widget presenting the active queue of video files."""

    item_removed = Signal(str)  # item_id

    COL_FILENAME = 0
    COL_DURATION = 1
    COL_STATUS = 2
    COL_PROGRESS = 3
    COL_OUTPUT = 4

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._items_by_id: Dict[str, FileQueueItem] = {}
        self._progress_bars: Dict[str, QProgressBar] = {}
        self._setup_ui()

    def _setup_ui(self) -> None:
        headers = ["Video File", "Duration", "Status", "Progress", "Output Subtitle (.srt)"]
        self.setColumnCount(len(headers))
        self.setHorizontalHeaderLabels(headers)
        self.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.setAlternatingRowColors(True)
        self.setShowGrid(False)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_context_menu)

        header = self.horizontalHeader()
        header.setSectionResizeMode(self.COL_FILENAME, QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(self.COL_DURATION, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(self.COL_STATUS, QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(self.COL_PROGRESS, QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(self.COL_OUTPUT, QHeaderView.ResizeMode.Stretch)

        self.setColumnWidth(self.COL_FILENAME, 220)
        self.setColumnWidth(self.COL_STATUS, 160)
        self.setColumnWidth(self.COL_PROGRESS, 160)

    def add_queue_item(self, item: FileQueueItem) -> None:
        """Add a video item to the table."""
        if item.id in self._items_by_id:
            return

        row = self.rowCount()
        self.insertRow(row)
        self._items_by_id[item.id] = item

        # 0. Filename
        file_item = QTableWidgetItem(item.file_path.name)
        file_item.setToolTip(str(item.file_path))
        file_item.setData(Qt.ItemDataRole.UserRole, item.id)
        self.setItem(row, self.COL_FILENAME, file_item)

        # 1. Duration
        dur_str = "--:--"
        if item.duration_seconds and item.duration_seconds > 0:
            m = int(item.duration_seconds // 60)
            s = int(item.duration_seconds % 60)
            dur_str = f"{m:02d}:{s:02d}"
        dur_item = QTableWidgetItem(dur_str)
        dur_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setItem(row, self.COL_DURATION, dur_item)

        # 2. Status
        status_item = QTableWidgetItem(item.status.display_name)
        status_item.setTextAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
        self.setItem(row, self.COL_STATUS, status_item)

        # 3. Progress Bar
        pbar = QProgressBar()
        pbar.setRange(0, 100)
        pbar.setValue(int(item.progress))
        pbar.setTextVisible(True)
        self.setCellWidget(row, self.COL_PROGRESS, pbar)
        self._progress_bars[item.id] = pbar

        # 4. Output Path
        out_item = QTableWidgetItem(item.output_srt_path.name)
        out_item.setToolTip(str(item.output_srt_path))
        self.setItem(row, self.COL_OUTPUT, out_item)

    def update_item_progress(self, item_id: str, step_name: str, pct: float) -> None:
        """Update progress bar and status text for a queue item."""
        row = self._find_row_by_id(item_id)
        if row is None:
            return

        status_item = self.item(row, self.COL_STATUS)
        if status_item:
            status_item.setText(step_name)

        pbar = self._progress_bars.get(item_id)
        if pbar:
            pbar.setValue(int(pct))

    def update_item_finished(self, item_id: str, success: bool, message: str) -> None:
        """Mark item completed or failed."""
        row = self._find_row_by_id(item_id)
        if row is None:
            return

        status_item = self.item(row, self.COL_STATUS)
        if status_item:
            if success:
                status_item.setText("Completed")
                status_item.setForeground(Qt.GlobalColor.green)
            else:
                status_item.setText("Failed")
                status_item.setForeground(Qt.GlobalColor.red)
                status_item.setToolTip(message)

        pbar = self._progress_bars.get(item_id)
        if pbar:
            pbar.setValue(100 if success else 0)

    def get_selected_item_id(self) -> Optional[str]:
        row = self.currentRow()
        if row < 0:
            return None
        file_item = self.item(row, self.COL_FILENAME)
        if file_item:
            return file_item.data(Qt.ItemDataRole.UserRole)
        return None

    def remove_selected_item(self) -> None:
        item_id = self.get_selected_item_id()
        if not item_id:
            return
        row = self._find_row_by_id(item_id)
        if row is not None:
            self.removeRow(row)
            self._items_by_id.pop(item_id, None)
            self._progress_bars.pop(item_id, None)
            self.item_removed.emit(item_id)

    def clear_all_items(self) -> None:
        self.setRowCount(0)
        self._items_by_id.clear()
        self._progress_bars.clear()

    def _find_row_by_id(self, item_id: str) -> Optional[int]:
        for r in range(self.rowCount()):
            it = self.item(r, self.COL_FILENAME)
            if it and it.data(Qt.ItemDataRole.UserRole) == item_id:
                return r
        return None

    def _show_context_menu(self, pos) -> None:
        item_id = self.get_selected_item_id()
        if not item_id or item_id not in self._items_by_id:
            return

        item = self._items_by_id[item_id]
        menu = QMenu(self)

        act_open_dir = menu.addAction("Open Video Folder")
        act_open_srt = menu.addAction("Open Generated Subtitle (.srt)")
        act_open_srt.setEnabled(item.output_srt_path.is_file())
        menu.addSeparator()
        act_remove = menu.addAction("Remove from Queue")
        act_remove.setEnabled(item.status != ProcessingStatus.TRANSCRIBING and item.status != ProcessingStatus.TRANSLATING)

        chosen = menu.exec(self.mapToGlobal(pos))
        if chosen == act_open_dir:
            self._open_in_explorer(item.file_path.parent)
        elif chosen == act_open_srt:
            if item.output_srt_path.is_file():
                self._open_in_explorer(item.output_srt_path)
        elif chosen == act_remove:
            self.remove_selected_item()

    @staticmethod
    def _open_in_explorer(path: Path) -> None:
        try:
            if sys.platform == "win32":
                os.startfile(str(path))  # type: ignore[attr-defined]
            else:
                subprocess.run(["xdg-open", str(path)], check=False)
        except Exception:
            pass
