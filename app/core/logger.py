"""Logging infrastructure for JARVIS."""

import logging
import os
import sys
from pathlib import Path

# Sensitive patterns to redact if encountered
_SENSITIVE_PATTERNS = ["api_key", "password", "token", "secret", "bearer"]


class SensitiveDataFilter(logging.Filter):
    """Filter to ensure sensitive credentials are not accidentally logged."""

    def filter(self, record: logging.LogRecord) -> bool:
        message = record.getMessage().lower()
        for pattern in _SENSITIVE_PATTERNS:
            if f"{pattern}=" in message or f"{pattern}:" in message:
                # If sensitive keyword pattern detected, do not log full record raw
                return False
        return True


def setup_logger(
    name: str = "jarvis",
    log_level: str = "INFO",
    log_to_file: bool = True,
    log_to_console: bool = False,
) -> logging.Logger:
    """Configures and returns the application logger.

    Args:
        name: Name of the logger.
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR).
        log_to_file: Whether to write logs to logs/jarvis.log.
        log_to_console: Whether to duplicate logs to sys.stderr.
    """
    logger = logging.getLogger(name)
    level = getattr(logging, log_level.upper(), logging.INFO)
    logger.setLevel(level)

    # Prevent duplicate handlers if re-initialized
    if logger.handlers:
        return logger

    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | [%(name)s] %(filename)s:%(lineno)d - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    sensitive_filter = SensitiveDataFilter()

    if log_to_file:
        project_root = Path(__file__).resolve().parent.parent.parent
        log_dir = project_root / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        log_file = log_dir / "jarvis.log"

        file_handler = logging.FileHandler(str(log_file), encoding="utf-8")
        file_handler.setLevel(level)
        file_handler.setFormatter(formatter)
        file_handler.addFilter(sensitive_filter)
        logger.addHandler(file_handler)

    if log_to_console:
        console_handler = logging.StreamHandler(sys.stderr)
        console_handler.setLevel(level)
        console_handler.setFormatter(formatter)
        console_handler.addFilter(sensitive_filter)
        logger.addHandler(console_handler)

    return logger
