import json
import logging
import sys
from datetime import datetime, timezone
from typing import Any


class JSONFormatter(logging.Formatter):
    """Structured JSON formatter for application and chaos event logs."""

    def format(self, record: logging.LogRecord) -> str:
        log_obj: dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }

        # Include custom extra attributes if passed to logger
        for key in ("experiment_id", "service_id", "fault_type", "phase", "event_type"):
            if hasattr(record, key):
                log_obj[key] = getattr(record, key)

        if record.exc_info:
            log_obj["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_obj)


def setup_logging(level: str = "INFO", json_format: bool = False) -> logging.Logger:
    """Configures root and app logging."""
    root_logger = logging.getLogger()
    root_logger.setLevel(level.upper())

    # Clear existing handlers to avoid duplicates
    root_logger.handlers.clear()

    handler = logging.StreamHandler(sys.stdout)
    if json_format:
        handler.setFormatter(JSONFormatter())
    else:
        standard_formatter = logging.Formatter(
            fmt="%(asctime)s [%(levelname)s] [%(name)s] %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        handler.setFormatter(standard_formatter)

    root_logger.addHandler(handler)

    # Set specific third-party library log levels to avoid noise
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("docker").setLevel(logging.INFO)
    logging.getLogger("uvicorn.access").setLevel(logging.INFO)

    logger = logging.getLogger("chaos_probe")
    logger.setLevel(level.upper())
    return logger


def get_logger(name: str = "chaos_probe") -> logging.Logger:
    """Helper to return a named logger under the chaos_probe namespace."""
    return logging.getLogger(name)


logger = logging.getLogger("chaos_probe")
