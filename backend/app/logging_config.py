"""Centralized logging configuration. Writes structured JSON logs to logs/savepilot.log."""

import json
import logging
import os
import time
from datetime import UTC, datetime
from logging.handlers import RotatingFileHandler
from typing import Any


LOG_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "logs")
LOG_FILE = os.path.join(LOG_DIR, "savepilot.log")
MAX_BYTES = 10 * 1024 * 1024  # 10 MB per file
BACKUP_COUNT = 5


class JSONFormatter(logging.Formatter):
    """Emits one JSON object per line with structured fields."""

    def format(self, record: logging.LogRecord) -> str:
        entry: dict[str, Any] = {
            "ts": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if hasattr(record, "extra_data"):
            entry["data"] = record.extra_data
        if record.exc_info and record.exc_info[1]:
            entry["error"] = {
                "type": type(record.exc_info[1]).__name__,
                "message": str(record.exc_info[1]),
            }
        return json.dumps(entry, default=str)


def setup_logging() -> None:
    os.makedirs(LOG_DIR, exist_ok=True)

    root = logging.getLogger()
    root.setLevel(logging.INFO)

    if any(isinstance(h, RotatingFileHandler) for h in root.handlers):
        return

    file_handler = RotatingFileHandler(
        LOG_FILE, maxBytes=MAX_BYTES, backupCount=BACKUP_COUNT, encoding="utf-8"
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(JSONFormatter())
    root.addHandler(file_handler)

    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)-8s %(name)s  %(message)s")
    )
    if not any(isinstance(h, logging.StreamHandler) and not isinstance(h, RotatingFileHandler) for h in root.handlers):
        root.addHandler(console_handler)


def log_event(logger: logging.Logger, level: int, message: str, **data: Any) -> None:
    """Convenience: attach arbitrary key-value data to a log record."""
    record = logger.makeRecord(
        logger.name, level, "(log_event)", 0, message, (), None
    )
    record.extra_data = data  # type: ignore[attr-defined]
    logger.handle(record)


class StepTimer:
    """Context-manager that measures wall-clock time for a pipeline step."""

    def __init__(self):
        self.start: float = 0
        self.elapsed_ms: float = 0

    def __enter__(self):
        self.start = time.perf_counter()
        return self

    def __exit__(self, *_):
        self.elapsed_ms = round((time.perf_counter() - self.start) * 1000, 2)
