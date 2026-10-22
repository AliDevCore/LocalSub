"""
LocalSub - Model Selection and Readiness Component.
Allows choosing target subtitle language, Whisper speech model, and local translation model.
Provides live status badges and on-demand model download triggers.
"""

from __future__ import annotations

from typing import Callable, Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.core.config import AppSettings
from app.core.types import TargetLanguage, TranslationModelType, WhisperModelSize
from app.services.model_manager import ModelManager


class ModelSelectorWidget(QGroupBox):
    """Configuration box for Subtitle Language and AI Models."""

    settings_changed = Signal()
    download_requested = Signal(str, str)  # category ("whisper"|"translation"), identifier

    def __init__(
        self,
        settings: AppSettings,
        model_manager: Optional[ModelManager] = None,
        parent: Optional[QWidget] = None,
    ):
        super().__init__("Subtitle Language & AI Model Configuration", parent)
        self.settings = settings
        self.model_manager = model_manager or ModelManager()
        self._setup_ui()
        self.refresh_status()

    def _setup_ui(self) -> None:
        layout = QGridLayout(self)
        layout.setContentsMargins(16, 20, 16, 16)
        layout.setHorizontalSpacing(16)
        layout.setVerticalSpacing(12)

        # 1. Subtitle Target Language
        lbl_lang = QLabel("Subtitle Language:")
        lbl_lang.setStyleSheet("font-weight: 600;")
        self.combo_lang = QComboBox()
        self.combo_lang.addItem(TargetLanguage.PERSIAN.display_name, TargetLanguage.PERSIAN.value)
        self.combo_lang.addItem(TargetLanguage.ENGLISH.display_name, TargetLanguage.ENGLISH.value)

        # Select saved language
        idx = self.combo_lang.findData(self.settings.target_language)
        if idx >= 0:
            self.combo_lang.setCurrentIndex(idx)
        self.combo_lang.currentIndexChanged.connect(self._on_lang_changed)

        layout.addWidget(lbl_lang, 0, 0)
        layout.addWidget(self.combo_lang, 0, 1, 1, 2)

        # 2. Whisper Speech Recognition Model
        lbl_whisper = QLabel("Speech Recognition Model:")
        lbl_whisper.setStyleSheet("font-weight: 600;")
        self.combo_whisper = QComboBox()
        for size in [WhisperModelSize.BASE, WhisperModelSize.SMALL, WhisperModelSize.MEDIUM]:
            self.combo_whisper.addItem(size.display_name, size.value)

        w_idx = self.combo_whisper.findData(self.settings.whisper_model)
        if w_idx >= 0:
            self.combo_whisper.setCurrentIndex(w_idx)
        self.combo_whisper.currentIndexChanged.connect(self._on_whisper_changed)

        self.badge_whisper = QLabel("Checking...")
        self.badge_whisper.setObjectName("StatusBadgeNeutral")

        self.btn_download_whisper = QPushButton("Download")
        self.btn_download_whisper.clicked.connect(self._on_download_whisper_clicked)

        layout.addWidget(lbl_whisper, 1, 0)
        layout.addWidget(self.combo_whisper, 1, 1)
        layout.addWidget(self.badge_whisper, 1, 2)
        layout.addWidget(self.btn_download_whisper, 1, 3)

        # 3. Local Translation Model
        self.lbl_translation = QLabel("Translation Model (EN -> FA):")
        self.lbl_translation.setStyleSheet("font-weight: 600;")
        self.combo_translation = QComboBox()
        for t_model in [TranslationModelType.NLLB_DISTILLED_600M, TranslationModelType.OPUS_MT_EN_FA]:
            self.combo_translation.addItem(t_model.display_name, t_model.value)

        t_idx = self.combo_translation.findData(self.settings.translation_model)
        if t_idx >= 0:
            self.combo_translation.setCurrentIndex(t_idx)
        self.combo_translation.currentIndexChanged.connect(self._on_translation_changed)

        self.badge_translation = QLabel("Checking...")
        self.badge_translation.setObjectName("StatusBadgeNeutral")

        self.btn_download_translation = QPushButton("Download")
        self.btn_download_translation.clicked.connect(self._on_download_translation_clicked)

        layout.addWidget(self.lbl_translation, 2, 0)
        layout.addWidget(self.combo_translation, 2, 1)
        layout.addWidget(self.badge_translation, 2, 2)
        layout.addWidget(self.btn_download_translation, 2, 3)

        # 4. Download Progress Indicator (Hidden by default)
        self.download_pbar = QProgressBar()
        self.download_pbar.setVisible(False)
        self.download_status_lbl = QLabel("")
        self.download_status_lbl.setVisible(False)
        layout.addWidget(self.download_status_lbl, 3, 0, 1, 4)
        layout.addWidget(self.download_pbar, 4, 0, 1, 4)

    def refresh_status(self) -> None:
        """Update live readiness badges."""
        curr_lang = self.combo_lang.currentData()
        curr_whisper = self.combo_whisper.currentData()
        curr_trans = self.combo_translation.currentData()

        # Whisper status
        w_ready = self.model_manager.is_whisper_model_ready(curr_whisper)
        if w_ready:
            self.badge_whisper.setText("Ready (Offline)")
            self.badge_whisper.setObjectName("StatusBadgeReady")
            self.btn_download_whisper.setEnabled(False)
            self.btn_download_whisper.setText("Downloaded")
        else:
            self.badge_whisper.setText("Not Downloaded")
            self.badge_whisper.setObjectName("StatusBadgeMissing")
            self.btn_download_whisper.setEnabled(True)
            self.btn_download_whisper.setText("Download / Import...")

        # Translation status
        if curr_lang == TargetLanguage.ENGLISH.value:
            # English mode: Translation model is completely skipped and disabled
            self.combo_translation.setEnabled(False)
            self.badge_translation.setText("Not Needed (Original EN)")
            self.badge_translation.setObjectName("StatusBadgeNeutral")
            self.btn_download_translation.setEnabled(False)
            self.btn_download_translation.setText("N/A")
        else:
            # Persian mode: Translation model required
            self.combo_translation.setEnabled(True)
            t_ready = self.model_manager.is_translation_model_ready(curr_trans)
            if t_ready:
                self.badge_translation.setText("Ready (Offline)")
                self.badge_translation.setObjectName("StatusBadgeReady")
                self.btn_download_translation.setEnabled(False)
                self.btn_download_translation.setText("Downloaded")
            else:
                self.badge_translation.setText("Not Downloaded")
                self.badge_translation.setObjectName("StatusBadgeMissing")
                self.btn_download_translation.setEnabled(True)
                self.btn_download_translation.setText("Download / Import...")

        # Re-apply styles
        self.badge_whisper.style().unpolish(self.badge_whisper)
        self.badge_whisper.style().polish(self.badge_whisper)
        self.badge_translation.style().unpolish(self.badge_translation)
        self.badge_translation.style().polish(self.badge_translation)

    def _on_lang_changed(self) -> None:
        self.settings.target_language = self.combo_lang.currentData()
        self.settings.save()
        self.refresh_status()
        self.settings_changed.emit()

    def _on_whisper_changed(self) -> None:
        self.settings.whisper_model = self.combo_whisper.currentData()
        self.settings.save()
        self.refresh_status()
        self.settings_changed.emit()

    def _on_translation_changed(self) -> None:
        self.settings.translation_model = self.combo_translation.currentData()
        self.settings.save()
        self.refresh_status()
        self.settings_changed.emit()

    def _on_download_whisper_clicked(self) -> None:
        from app.ui.components.model_import_dialog import ModelImportDialog

        curr_whisper = self.combo_whisper.currentData()
        dlg = ModelImportDialog(
            category="whisper",
            identifier=curr_whisper,
            model_manager=self.model_manager,
            parent=self.window(),
        )
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self.refresh_status()
            self.settings_changed.emit()

    def _on_download_translation_clicked(self) -> None:
        from app.ui.components.model_import_dialog import ModelImportDialog

        curr_trans = self.combo_translation.currentData()
        dlg = ModelImportDialog(
            category="translation",
            identifier=curr_trans,
            model_manager=self.model_manager,
            parent=self.window(),
        )
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self.refresh_status()
            self.settings_changed.emit()

    def show_download_progress(self, message: str, pct: float) -> None:
        self.download_status_lbl.setVisible(True)
        self.download_status_lbl.setText(message)
        self.download_pbar.setVisible(True)
        self.download_pbar.setValue(int(pct))

    def hide_download_progress(self) -> None:
        self.download_status_lbl.setVisible(False)
        self.download_pbar.setVisible(False)
