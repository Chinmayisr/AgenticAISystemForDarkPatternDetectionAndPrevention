# utils/logger.py

import logging
import sys
from rich.logging import RichHandler
from config import get_settings


def get_logger(name: str) -> logging.Logger:
    settings = get_settings()
    logger = logging.getLogger(name)

    if not logger.handlers:
        level = getattr(logging, settings.log_level.upper(), logging.INFO)
        logger.setLevel(level)
        handler = RichHandler(
            rich_tracebacks=True,
            show_path=settings.environment == "development"
        )
        handler.setFormatter(logging.Formatter("%(message)s", datefmt="[%X]"))
        logger.addHandler(handler)

    return logger