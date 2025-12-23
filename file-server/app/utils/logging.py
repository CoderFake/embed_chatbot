"""
Logging utilities for file server
"""
import logging
import logging.handlers
import sys
import json
from pathlib import Path

from app.utils.datetime_utils import now


class JsonFormatter(logging.Formatter):
    """JSON formatter for structured logging"""
    
    def format(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": now().isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        
        # Add extra fields
        if hasattr(record, 'task_id'):
            log_entry['task_id'] = record.task_id
        if hasattr(record, 'task_type'):
            log_entry['task_type'] = record.task_type
        if hasattr(record, 'bot_id'):
            log_entry['bot_id'] = record.bot_id
        if hasattr(record, 'user_id'):
            log_entry['user_id'] = record.user_id
        if hasattr(record, 'progress'):
            log_entry['progress'] = record.progress
        
        if record.exc_info:
            log_entry['exception'] = self.formatException(record.exc_info)
        
        return json.dumps(log_entry, ensure_ascii=False)


class ColoredFormatter(logging.Formatter):
    """Colored formatter for console output"""
    
    COLORS = {
        'DEBUG': '\033[36m',     # Cyan
        'INFO': '\033[32m',      # Green
        'WARNING': '\033[33m',   # Yellow
        'ERROR': '\033[31m',     # Red
        'CRITICAL': '\033[35m',  # Magenta
        'RESET': '\033[0m'       # Reset
    }
    
    def format(self, record: logging.LogRecord) -> str:
        color = self.COLORS.get(record.levelname, self.COLORS['RESET'])
        reset = self.COLORS['RESET']
        timestamp = now().strftime('%Y-%m-%d %H:%M:%S')
        formatted_message = (
            f"{color}[{timestamp}] {record.levelname:8s}{reset} "
            f"{record.name:20s} | {record.getMessage()}"
        )
        
        return formatted_message


def setup_logging(log_level: str = "INFO", log_format: str = "json") -> None:
    """
    Setup logging configuration for file server
    
    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_format: Format type ("json" or "text")
    """
    log_dir = Path("./logs")
    log_dir.mkdir(parents=True, exist_ok=True)
    
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, log_level.upper()))
    root_logger.handlers.clear()
    
    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(getattr(logging, log_level.upper()))
    
    if log_format == "json":
        console_handler.setFormatter(JsonFormatter())
    else:
        console_handler.setFormatter(ColoredFormatter())
    
    root_logger.addHandler(console_handler)
    
    # File handler for all logs (JSON)
    file_handler = logging.handlers.RotatingFileHandler(
        filename=log_dir / "file_server.log",
        maxBytes=10 * 1024 * 1024,  # 10MB
        backupCount=5,
        encoding='utf-8'
    )
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(JsonFormatter())
    root_logger.addHandler(file_handler)
    
    # Error handler
    error_handler = logging.handlers.RotatingFileHandler(
        filename=log_dir / "error.log",
        maxBytes=10 * 1024 * 1024,  # 10MB
        backupCount=5,
        encoding='utf-8'
    )
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(JsonFormatter())
    root_logger.addHandler(error_handler)


def get_logger(name: str) -> logging.Logger:
    """
    Get logger instance
    
    Args:
        name: Logger name (usually __name__)
        
    Returns:
        Logger instance
    """
    return logging.getLogger(name)
