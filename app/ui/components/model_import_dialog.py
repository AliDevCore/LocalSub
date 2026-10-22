"""
LocalSub - Model Download Guide and Import Dialog.
Provides direct download links, browser launch, and automatic ZIP/folder extraction.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices, QGuiApplication
from PySide6.QtWidgets import (
    QDialog,
    QFileDialog,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from app.services.model_manager import ModelManager


class ModelImportDialog(QDialog):
    """Dialog providing manual download links and ZIP/folder import functionality."""

    def __init__(
        self,
        category: str,
        identifier: str,
        model_manager: ModelManager,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self.category = category
        self.identifier = identifier
        self.model_manager = model_manager
        self.model_info = self.model_manager.get_model_download_info(category, identifier)

        self.setWindowTitle(f"دانلود و نصب مدل - {identifier}")
        self.resize(680, 540)
        self.setModal(True)

        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(16)

        # 1. Header Information
        header_frame = QFrame()
        header_frame.setStyleSheet(
            "background-color: #1e293b; border-radius: 8px; border: 1px solid #334155; padding: 12px;"
        )
        h_layout = QVBoxLayout(header_frame)
        h_layout.setContentsMargins(8, 8, 8, 8)
        h_layout.setSpacing(6)

        cat_title = "مدل تشخیص گفتار (Whisper)" if self.category == "whisper" else "مدل ترجمه عصبی فارسی (NLLB-200)"
        lbl_title = QLabel(f"<b style='font-size: 15px; color: #38bdf8;'>{cat_title}</b>")
        lbl_info = QLabel(
            f"<b>شناسه مدل:</b> <code style='color: #a5f3fc;'>{self.identifier}</code> &nbsp;&nbsp;|&nbsp;&nbsp; "
            f"<b>حجم تقریبی:</b> ~{self.model_info.get('size_mb', 0)} مگابایت"
        )
        lbl_dest = QLabel(
            f"<span style='color: #94a3b8;'>مسیر نصب نهایی در سیستم شما:</span><br>"
            f"<code style='color: #cbd5e1; font-size: 11px;'>{self._get_target_dir()}</code>"
        )
        lbl_dest.setWordWrap(True)

        h_layout.addWidget(lbl_title)
        h_layout.addWidget(lbl_info)
        h_layout.addWidget(lbl_dest)
        layout.addWidget(header_frame)

        # 2. Download Links Section
        dl_group = QGroupBox("گام اول: لینک‌های دریافت مدل (Download Links)")
        dl_group.setStyleSheet("font-weight: 600;")
        dl_layout = QVBoxLayout(dl_group)
        dl_layout.setContentsMargins(16, 16, 16, 16)
        dl_layout.setSpacing(10)

        desc_lbl = QLabel(
            "به دلیل محدودیت‌ها یا قطعی اینترنت، می‌توانید فایل‌های مدل را مستقیماً با "
            "<b>مرورگر</b> یا <b>دانلود منیجر (IDM)</b> دریافت کنید:"
        )
        desc_lbl.setWordWrap(True)
        dl_layout.addWidget(desc_lbl)

        # Quick action buttons
        btn_box = QHBoxLayout()
        btn_box.setSpacing(10)

        page_url = self.model_info.get("page_url", "")
        if page_url:
            btn_browser = QPushButton("🌐 باز کردن صفحه دانلود در مرورگر")
            btn_browser.setStyleSheet("background-color: #0284c7; font-weight: bold; padding: 8px 14px;")
            btn_browser.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(page_url)))
            btn_box.addWidget(btn_browser)

        direct_links = self.model_info.get("direct_links", [])
        if direct_links:
            # Main model.bin direct link
            main_bin_url = direct_links[0][1]
            btn_copy_main = QPushButton("📋 کپی لینک مستقیم فایل اصلی (model.bin)")
            btn_copy_main.setStyleSheet("background-color: #334155; padding: 8px 14px;")
            btn_copy_main.clicked.connect(lambda: self._copy_to_clipboard(main_bin_url, "لینک مستقیم model.bin کپی شد!"))
            btn_box.addWidget(btn_copy_main)

        dl_layout.addLayout(btn_box)

        # Direct links list
        if direct_links:
            links_frame = QFrame()
            links_frame.setStyleSheet("background-color: #0f172a; border-radius: 6px; padding: 6px;")
            links_layout = QGridLayout(links_frame)
            links_layout.setContentsMargins(8, 8, 8, 8)
            links_layout.setSpacing(8)

            for i, (label, url) in enumerate(direct_links):
                f_lbl = QLabel(f"<b>• {label}</b>")
                f_lbl.setStyleSheet("color: #e2e8f0; font-size: 11px;")
                btn_copy = QPushButton("کپی لینک")
                btn_copy.setMaximumWidth(80)
                btn_copy.setStyleSheet("font-size: 11px; padding: 4px;")
                btn_copy.clicked.connect(lambda checked=False, u=url, n=label: self._copy_to_clipboard(u, f"لینک {n} کپی شد."))
                links_layout.addWidget(f_lbl, i, 0)
                links_layout.addWidget(btn_copy, i, 1)

            dl_layout.addWidget(links_frame)

        layout.addWidget(dl_group)

        # 3. Import ZIP / Folder Section
        import_group = QGroupBox("گام دوم: وارد کردن و اکسترکت خودکار فایل (Import & Extract)")
        import_group.setStyleSheet("font-weight: 600;")
        imp_layout = QVBoxLayout(import_group)
        imp_layout.setContentsMargins(16, 16, 16, 16)
        imp_layout.setSpacing(12)

        tip_lbl = QLabel(
            "پس از دانلود فایل(ها)، آن‌ها را در قالب یک فایل ZIP قرار دهید (یا پوشه حاوی آن‌ها را انتخاب کنید). "
            "نرم‌افزار به‌صورت هوشمند فایل‌ها را در محل مناسب استخراج، نرمال‌سازی و تأیید سلامت می‌کند:"
        )
        tip_lbl.setWordWrap(True)
        imp_layout.addWidget(tip_lbl)

        imp_btn_layout = QHBoxLayout()
        imp_btn_layout.setSpacing(12)

        btn_zip = QPushButton("📦 انتخاب فایل ZIP مدل (Select ZIP)...")
        btn_zip.setStyleSheet(
            "background-color: #059669; font-size: 13px; font-weight: bold; padding: 10px 18px; border-radius: 6px;"
        )
        btn_zip.clicked.connect(self._on_select_zip)
        imp_btn_layout.addWidget(btn_zip)

        btn_folder = QPushButton("📁 یا انتخاب پوشه فایل‌های دانلودشده...")
        btn_folder.setStyleSheet("background-color: #334155; padding: 10px 14px; border-radius: 6px;")
        btn_folder.clicked.connect(self._on_select_folder)
        imp_btn_layout.addWidget(btn_folder)

        imp_layout.addLayout(imp_btn_layout)

        # Progress bar & status
        self.pbar = QProgressBar()
        self.pbar.setVisible(False)
        self.status_lbl = QLabel("")
        self.status_lbl.setVisible(False)
        imp_layout.addWidget(self.status_lbl)
        imp_layout.addWidget(self.pbar)

        layout.addWidget(import_group)

        # 4. Close Button
        btn_close = QPushButton("بستن (Close)")
        btn_close.clicked.connect(self.reject)
        layout.addWidget(btn_close, 0, Qt.AlignmentFlag.AlignRight)

    def _get_target_dir(self) -> Path:
        if self.category == "whisper":
            return self.model_manager.get_whisper_model_path(self.identifier)
        return self.model_manager.get_translation_model_path(self.identifier)

    def _copy_to_clipboard(self, text: str, notice: str) -> None:
        clipboard = QGuiApplication.clipboard()
        clipboard.setText(text)
        QMessageBox.information(self, "کپی شد", f"{notice}\n\nآدرس در کلیپ‌بورد قرار گرفت و می‌توانید در IDM یا مرورگر Paste کنید.")

    def _on_select_zip(self) -> None:
        zip_file, _ = QFileDialog.getOpenFileName(
            self,
            "انتخاب فایل زیپ حاوی مدل",
            "",
            "ZIP Files (*.zip);;All Files (*.*)",
        )
        if not zip_file:
            return

        self.pbar.setVisible(True)
        self.status_lbl.setVisible(True)
        self.pbar.setValue(20)
        self.status_lbl.setText("در حال استخراج و اعتبارسنجی فایل ZIP...")

        try:
            out_dir = self.model_manager.import_model_from_zip(
                category=self.category,
                identifier=self.identifier,
                zip_path=Path(zip_file),
                progress_callback=self._update_progress,
            )
            self.pbar.setValue(100)
            QMessageBox.information(
                self,
                "نصب موفقیت‌آمیز مدل",
                f"مدل با موفقیت استخراج و تأیید سلامت شد!\n\nمسیر ذخیره: {out_dir}\nاکنون مدل کاملاً آفلاین و آماده استفاده است.",
            )
            self.accept()
        except Exception as e:
            self.pbar.setVisible(False)
            self.status_lbl.setVisible(False)
            QMessageBox.critical(
                self,
                "خطا در وارد کردن مدل",
                f"فایل زیپ انتخاب‌شده نامعتبر است یا فایل‌های ضروری مدل در آن موجود نیستند:\n\n{e}",
            )

    def _on_select_folder(self) -> None:
        folder = QFileDialog.getExistingDirectory(
            self,
            "انتخاب پوشه حاوی فایل‌های دانلودشده مدل",
            "",
        )
        if not folder:
            return

        self.pbar.setVisible(True)
        self.status_lbl.setVisible(True)
        self.pbar.setValue(20)
        self.status_lbl.setText("در حال کپی و اعتبارسنجی فایل‌های مدل...")

        try:
            out_dir = self.model_manager.import_model_from_folder(
                category=self.category,
                identifier=self.identifier,
                folder_path=Path(folder),
                progress_callback=self._update_progress,
            )
            self.pbar.setValue(100)
            QMessageBox.information(
                self,
                "نصب موفقیت‌آمیز مدل",
                f"مدل با موفقیت در پوشه نرم‌افزار قرار گرفت و آماده استفاده است!\n\nمسیر ذخیره: {out_dir}",
            )
            self.accept()
        except Exception as e:
            self.pbar.setVisible(False)
            self.status_lbl.setVisible(False)
            QMessageBox.critical(
                self,
                "خطا در کپی مدل",
                f"پوشه انتخاب‌شده فاقد فایل‌های ضروری مدل است:\n\n{e}",
            )

    def _update_progress(self, message: str, pct: float) -> None:
        self.status_lbl.setText(message)
        self.pbar.setValue(int(pct))
