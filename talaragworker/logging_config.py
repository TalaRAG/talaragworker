from __future__ import annotations

import logging
import sys
from logging.handlers import WatchedFileHandler
from pathlib import Path


def configure_logging(app_env: str) -> logging.Logger:
    logger = logging.getLogger("talaragworker")
    logger.setLevel(logging.INFO)
    logger.handlers.clear()
    logger.propagate = False

    formatter = logging.Formatter(
        fmt="%(asctime)s %(levelname)s [%(name)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    stdout_handler = logging.StreamHandler(sys.stdout)
    stdout_handler.setFormatter(formatter)
    logger.addHandler(stdout_handler)

    if app_env == "development":
        log_dir = Path("logs")
        log_dir.mkdir(parents=True, exist_ok=True)
        file_handler = WatchedFileHandler(log_dir / "development.log")
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    return logger
