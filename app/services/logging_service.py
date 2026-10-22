"""
LocalSub - Logging and Privacy Service.
Provides rotating file logs and console logs strictly respecting user privacy.
Dialogue content and video audio are NEVER logged.
"""

from __future__ import annotations

import logging
import os
import subprocess
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Optional

from app.core.config import APP_NAME, APP_VERSION, get_logs_dir

LOGGER_NAME = "LocalSub"
_logger: Optional[logging.Logger] = None


def setup_logging(debug: bool = False) -> logging.Logger:
    """
    Initialize rotating file logger and console logger.
    
    Log format:
    YYYY-MM-DD HH:MM:SS [LEVEL] [module] message
    """
    global _logger
    if _logger is not None:
        return _logger

    log_dir = get_logs_dir()
    log_file = log_dir / "localsub.log"

    logger = logging.getLogger(LOGGER_NAME)
    logger.setLevel(logging.DEBUG if debug else logging.INFO)
    logger.propagate = False

    # Prevent duplicate handlers
    if not logger.handlers:
        formatter = logging.Formatter(
            fmt="%(asctime)s [%(levelname)s] [%(name)s.%(module)s] %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )

        # 1. Rotating File Handler (5 MB per file, max 3 backup files)
        file_handler = RotatingFileHandler(
            filename=str(log_file),
            maxBytes=5 * 1024 * 1024,
            backupCount=3,
            encoding="utf-8",
        )
        file_handler.setLevel(logging.DEBUG if debug else logging.INFO)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

        # 2. Console Stream Handler (only if stdout is an active terminal stream)
        if sys.stdout is not None and hasattr(sys.stdout, "write"):
            console_handler = logging.StreamHandler(sys.stdout)
            console_handler.setLevel(logging.DEBUG if debug else logging.INFO)
            console_handler.setFormatter(formatter)
            logger.addHandler(console_handler)

    _logger = logger
    _logger.info(f"=== {APP_NAME} v{APP_VERSION} initialized ===")
    _logger.info(f"Operating System: {sys.platform} ({os.name})")
    _logger.info(f"Python Runtime: {sys.version.split()[0]}")
    _logger.info(f"Log directory: {log_dir}")
    _logger.info("Privacy notice: Subtitle dialogues and audio data are strictly excluded from logs.")
    return logger


def get_logger() -> logging.Logger:
    """Retrieve application logger instance."""
    global _logger
    if _logger is None:
        return setup_logging()
    return _logger


def open_logs_directory() -> bool:
    """Open the application logs folder in Windows Explorer."""
    log_dir = get_logs_dir()
    try:
        if sys.platform == "win32":
            os.startfile(str(log_dir))  # type: ignore[attr-defined]
        elif sys.platform == "darwin":
            subprocess.run(["open", str(log_dir)], check=False)
        else:
            subprocess.run(["xdg-open", str(log_dir)], check=False)
        return True
    except Exception as e:
        get_logger().error(f"Failed to open logs directory '{log_dir}': {e}")
        return False
