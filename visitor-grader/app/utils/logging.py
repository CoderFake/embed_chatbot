"""Logging utilities."""
import logging
import sys

from app.config.settings import settings
from app.utils.datetime_utils import now


class JsonFormatter(logging.Formatter):
    """JSON formatter for structured logging."""
    
    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON."""
        import json
        
        log_data = {
            "timestamp": now().isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        
        # Add extra fields
        if hasattr(record, "task_id"):
            log_data["task_id"] = record.task_id
        if hasattr(record, "visitor_id"):
            log_data["visitor_id"] = record.visitor_id
        if hasattr(record, "bot_id"):
            log_data["bot_id"] = record.bot_id
        
        # Add exception info
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)
        
        return json.dumps(log_data)


def get_logger(name: str) -> logging.Logger:
    """
    Get or create a logger with the given name.
    
    Args:
        name: Logger name (usually __name__)
        
    Returns:
        Configured logger instance
    """
    logger = logging.getLogger(name)
    
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(JsonFormatter())
        logger.addHandler(handler)
        logger.setLevel(getattr(logging, settings.LOG_LEVEL.upper()))
        logger.propagate = False
    
    return logger
