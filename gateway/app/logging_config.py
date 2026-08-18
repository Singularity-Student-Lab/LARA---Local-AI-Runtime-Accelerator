"""Structured JSON logging. Never logs raw API keys, prompts, or responses (PRD 12.4, 16.4)."""

from __future__ import annotations

import logging
import sys

from pythonjsonlogger.json import JsonFormatter

from app.config import get_settings


def configure_logging() -> None:
    settings = get_settings()
    handler = logging.StreamHandler(sys.stdout)
    formatter = JsonFormatter(
        "%(asctime)s %(levelname)s %(name)s %(message)s",
        rename_fields={"asctime": "timestamp", "levelname": "level"},
    )
    handler.setFormatter(formatter)

    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(settings.lara_log_level.upper())

    # uvicorn's own loggers otherwise double-configure with their own formatters
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        logging.getLogger(name).handlers = [handler]
        logging.getLogger(name).propagate = False
