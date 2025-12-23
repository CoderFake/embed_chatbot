"""Logging utilities for the chat worker service."""
from __future__ import annotations

import json
import logging
import logging.handlers
import os
import sys
from pathlib import Path
from typing import Optional

from .datetime_utils import now
from app.config.settings import settings


class JsonFormatter(logging.Formatter):
    """Format log messages as JSON for easier ingestion."""

    def format(self, record: logging.LogRecord) -> str:  # pragma: no cover - formatting
        payload = {
            "timestamp": now().isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }

        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)

        extra = getattr(record, "extra", None)
        if isinstance(extra, dict):
            payload.update(extra)

        return json.dumps(payload, ensure_ascii=False)


class ColoredFormatter(logging.Formatter):
    """Simple coloured formatter for development."""

    COLORS = {
        "DEBUG": "\033[36m",
        "INFO": "\033[32m",
        "WARNING": "\033[33m",
        "ERROR": "\033[31m",
        "CRITICAL": "\033[35m",
        "RESET": "\033[0m",
    }

    def format(self, record: logging.LogRecord) -> str:  # pragma: no cover - formatting
        color = self.COLORS.get(record.levelname, self.COLORS["RESET"])
        reset = self.COLORS["RESET"]
        return f"{color}[{record.levelname:8s}] {record.name}: {record.getMessage()}{reset}"


def _ensure_log_dir() -> Path:
    log_dir = Path(os.getenv("LOG_DIR", "./logs"))
    log_dir.mkdir(parents=True, exist_ok=True)
    return log_dir


def setup_logging() -> None:
    """Configure root logger."""

    log_dir = _ensure_log_dir()
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG if settings.DEBUG else logging.INFO)
    root_logger.handlers.clear()

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.DEBUG if settings.DEBUG else logging.INFO)
    console_handler.setFormatter(ColoredFormatter() if settings.DEBUG else JsonFormatter())
    root_logger.addHandler(console_handler)

    file_handler = logging.handlers.RotatingFileHandler(
        log_dir / "worker.log",
        maxBytes=5 * 1024 * 1024,
        backupCount=3,
        encoding="utf-8",
    )
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(JsonFormatter())
    root_logger.addHandler(file_handler)

    error_handler = logging.handlers.RotatingFileHandler(
        log_dir / "worker-error.log",
        maxBytes=5 * 1024 * 1024,
        backupCount=3,
        encoding="utf-8",
    )
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(JsonFormatter())
    root_logger.addHandler(error_handler)

    logging.getLogger("aio_pika").setLevel(logging.WARNING)
    logging.getLogger("pymilvus").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """Return configured logger."""
    root_logger = logging.getLogger()
    if not root_logger.handlers:
        setup_logging()
    return logging.getLogger(name)


class LoggerMixin:
    """Mixin to provide a logger property."""

    @property
    def logger(self) -> logging.Logger:
        return get_logger(self.__class__.__name__)


def get_request_logger(name: str, request_id: str, user_id: Optional[str] = None) -> logging.LoggerAdapter:
    """Attach contextual information to logs."""
    base_logger = get_logger(name)
    return logging.LoggerAdapter(base_logger, {"request_id": request_id, "user_id": user_id})
