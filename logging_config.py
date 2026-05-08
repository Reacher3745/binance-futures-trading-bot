"""
Structured logging configuration for the trading bot.
Outputs INFO+ to console (human-readable) and DEBUG+ to rotating file (JSON).
"""

import logging
import logging.handlers
import json
import os
from datetime import datetime, timezone


LOG_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "logs")
LOG_FILE = os.path.join(LOG_DIR, "trading_bot.log")


class JSONFormatter(logging.Formatter):
    """Formats log records as newline-delimited JSON for the log file."""

    EXCLUDED_ATTRS = {
        "msg", "args", "levelname", "levelno", "pathname", "filename",
        "module", "exc_info", "exc_text", "stack_info", "lineno",
        "funcName", "created", "msecs", "relativeCreated", "thread",
        "threadName", "processName", "process", "name", "message",
    }

    def format(self, record: logging.LogRecord) -> str:
        record.message = record.getMessage()
        payload: dict = {
            "timestamp": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.message,
        }
        # Attach extra fields (e.g. request/response dicts)
        for key, value in record.__dict__.items():
            if key not in self.EXCLUDED_ATTRS and not key.startswith("_"):
                payload[key] = value

        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)

        return json.dumps(payload, default=str)


class ColorConsoleFormatter(logging.Formatter):
    """Human-readable console formatter with ANSI color coding."""

    COLORS = {
        "DEBUG":    "\033[36m",   # Cyan
        "INFO":     "\033[32m",   # Green
        "WARNING":  "\033[33m",   # Yellow
        "ERROR":    "\033[31m",   # Red
        "CRITICAL": "\033[35m",   # Magenta
    }
    RESET = "\033[0m"
    BOLD  = "\033[1m"

    def format(self, record: logging.LogRecord) -> str:
        color = self.COLORS.get(record.levelname, "")
        ts = datetime.fromtimestamp(record.created).strftime("%H:%M:%S")
        level = f"{color}{self.BOLD}{record.levelname:<8}{self.RESET}"
        return f"{ts} {level} {record.getMessage()}"


def setup_logging(verbose: bool = False) -> logging.Logger:
    """
    Configure root logger:
      • Console  → INFO (DEBUG if verbose)  – ColorConsoleFormatter
      • Log file → DEBUG                    – JSONFormatter (rotating 5 MB × 3)

    Returns the 'trading_bot' logger.
    """
    os.makedirs(LOG_DIR, exist_ok=True)

    root = logging.getLogger()
    root.setLevel(logging.DEBUG)

    # Remove any handlers already attached (e.g. during testing)
    root.handlers.clear()

    # ── Console handler ──────────────────────────────────────────────────────
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.DEBUG if verbose else logging.INFO)
    console_handler.setFormatter(ColorConsoleFormatter())
    root.addHandler(console_handler)

    # ── Rotating file handler ─────────────────────────────────────────────────
    file_handler = logging.handlers.RotatingFileHandler(
        LOG_FILE,
        maxBytes=5 * 1024 * 1024,   # 5 MB
        backupCount=3,
        encoding="utf-8",
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(JSONFormatter())
    root.addHandler(file_handler)

    return logging.getLogger("trading_bot")
