"""
LocalSub - Application Entry Point.
Initializes logging, DPI scaling policies, Qt Application instance, and Main Window.
"""

from __future__ import annotations

import argparse
import sys
import traceback
from pathlib import Path


class SafeStdWriter:
    """Safe fallback stream for PyInstaller GUI mode where sys.stdout/stderr are None."""
    def write(self, text: str) -> None:
        pass

    def flush(self) -> None:
        pass

    def isatty(self) -> bool:
        return False


# In Windows GUI executables (compiled with console=False), sys.stdout and sys.stderr are None.
# Third-party libraries like tqdm, huggingface_hub, and urllib attempt to call .write() on them.
if sys.stdout is None:
    sys.stdout = SafeStdWriter()
if sys.stderr is None:
    sys.stderr = SafeStdWriter()

from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication, QMessageBox

from app.core.config import APP_NAME, APP_TITLE, APP_VERSION
from app.services.logging_service import get_logger, setup_logging
from app.ui.main_window import MainWindow


def handle_uncaught_exception(exc_type, exc_value, exc_traceback) -> None:
    """Global exception hook to ensure crashes are recorded in local log file."""
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return

    logger = get_logger()
    logger.critical("Uncaught fatal exception occurred:", exc_info=(exc_type, exc_value, exc_traceback))

    # Try to alert user with message box if Qt is alive
    app = QApplication.instance()
    if app:
        err_msg = "".join(traceback.format_exception(exc_type, exc_value, exc_traceback))
        QMessageBox.critical(
            None,
            "LocalSub - Critical Error",
            f"An unexpected critical error occurred:\n\n{exc_type.__name__}: {exc_value}\n\nPlease check logs for details.",
        )


def main() -> int:
    """Main application execution routine."""
    parser = argparse.ArgumentParser(description=f"{APP_TITLE} (v{APP_VERSION})")
    parser.add_argument("--version", action="version", version=f"{APP_NAME} {APP_VERSION}")
    parser.add_argument("--debug", action="store_true", help="Enable verbose debug logging")
    parser.add_argument("input_files", nargs="*", help="Optional initial video files to enqueue")
    args = parser.parse_args()

    # Initialize logging
    logger = setup_logging(debug=args.debug)
    logger.info(f"Starting {APP_NAME} graphical interface...")

    # Set exception hook
    sys.excepthook = handle_uncaught_exception

    # Configure Qt high DPI attributes
    if hasattr(Qt.ApplicationAttribute, "AA_EnableHighDpiScaling"):
        QApplication.setAttribute(Qt.ApplicationAttribute.AA_EnableHighDpiScaling, True)
    if hasattr(Qt.ApplicationAttribute, "AA_UseHighDpiPixmaps"):
        QApplication.setAttribute(Qt.ApplicationAttribute.AA_UseHighDpiPixmaps, True)

    # Configure Windows Application ID for proper taskbar and window title icon association
    if sys.platform == "win32":
        try:
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("LocalSub.SubtitlingStudio.AI.1.0")
        except Exception:
            pass

    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationDisplayName(APP_TITLE)
    app.setApplicationVersion(APP_VERSION)

    # Set icon with multi-resolution formats
    from app.core.config import get_asset_path

    app_icon = QIcon()
    ico_file = get_asset_path("app_icon.ico")
    png_file = get_asset_path("app_icon.png")
    if ico_file.is_file():
        app_icon.addFile(str(ico_file))
    if png_file.is_file():
        app_icon.addFile(str(png_file))

    if not app_icon.isNull():
        app.setWindowIcon(app_icon)

    window = MainWindow()
    if not app_icon.isNull():
        window.setWindowIcon(app_icon)

    # If input files were passed via CLI / file association
    if args.input_files:
        valid_paths = [Path(f) for f in args.input_files if Path(f).is_file()]
        if valid_paths:
            window._add_files_to_queue(valid_paths)

    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
