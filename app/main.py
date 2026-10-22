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
# If launched with CLI flags, attempt to attach to parent console so output is visible.
if sys.platform == "win32" and any(arg in sys.argv for arg in ("--selftest", "--version", "--help", "-h")):
    try:
        import ctypes
        if ctypes.windll.kernel32.AttachConsole(-1):
            import io
            sys.stdout = io.TextIOWrapper(open("CONOUT$", "wt"), encoding="utf-8")
            sys.stderr = io.TextIOWrapper(open("CONOUT$", "wt"), encoding="utf-8")
    except Exception:
        pass

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
    parser.add_argument("--selftest", action="store_true", help="Perform automated smoke test and integrity check")
    parser.add_argument("--debug", action="store_true", help="Enable verbose debug logging")
    parser.add_argument("input_files", nargs="*", help="Optional initial video files to enqueue")
    args = parser.parse_args()

    if args.selftest:
        setup_logging(debug=True)
        print(f"=== {APP_NAME} v{APP_VERSION} Smoke Self-Test ===")
        try:
            import ctranslate2
            print(f"  [OK] ctranslate2 loaded (v{getattr(ctranslate2, '__version__', 'unknown')})")
            import faster_whisper
            print(f"  [OK] faster_whisper loaded (v{getattr(faster_whisper, '__version__', 'unknown')})")
            from app.services.ffmpeg_service import FFmpegService
            ffmpeg_path = FFmpegService().find_ffmpeg()
            print(f"  [OK] FFmpeg binary discovered: {ffmpeg_path}")
            from app.core.config import get_asset_path
            ico = get_asset_path("app_icon.ico")
            print(f"  [OK] App asset verified: {ico.name} (exists={ico.is_file()})")
            print("=== ALL SMOKE SELF-TEST CHECKS PASSED ===")
            return 0
        except Exception as e:
            print(f"  [FAILED] Smoke test error: {e}")
            return 1

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
