"""Custom Logger Using Loguru, inspired by Riki-1mg gist custom_logging.py

- In AWS Lambda: Logs only to stdout (CloudWatch), never to file, and never uses multiprocessing (enqueue=False).
- Locally: Logs to both stdout and file, uses enqueue=True for performance.
"""

import logging
import os
import sys
from pathlib import Path
from typing import ClassVar

from loguru import logger as loguru_logger

from .config import settings

class InterceptHandler(logging.Handler):
    """
    Handler to intercept standard library logs and reroute them through Loguru,
    so logs from other libraries (uvicorn, FastAPI, etc.) are unified.
    """
    loglevel_mapping: ClassVar[dict] = {
        50: "CRITICAL",
        40: "ERROR",
        30: "WARNING",
        20: "INFO",
        10: "DEBUG",
        0: "NOTSET",
    }

    def emit(self, record):  # pragma: no cover
        try:
            level = loguru_logger.level(record.levelname).name
        except AttributeError:
            level = self.loglevel_mapping.get(record.levelno, "INFO")

        frame, depth = logging.currentframe(), 2
        while frame and frame.f_code.co_filename == logging.__file__:
            frame = frame.f_back
            depth += 1

        loguru_logger.opt(depth=depth, exception=record.exc_info).log(
            level,
            record.getMessage(),
        )

class OverFastLogger:
    @classmethod
    def make_logger(cls):
        """
        Configures Loguru logger for both Lambda and local environments.
        - In Lambda: logs only to stdout, enqueue=False.
        - Locally: logs to both stdout and file, enqueue=True.
        """
        return cls.customize_logging(
            f"{settings.logs_root_path}/access.log",
            level=settings.log_level,
            rotation="1 day",
            retention="1 year",
            compression="gz",
            log_format=(
                "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
                "<level>{level: <8}</level> | "
                "<cyan>{name}</cyan> - <level>{message}</level>"
            ),
        )

    @classmethod
    def customize_logging(
        cls,
        filepath: Path,
        level: str,
        rotation: str,
        retention: str,
        compression: str,
        log_format: str,
    ):
        loguru_logger.remove()

        # Detect if running in AWS Lambda (standard env var)
        is_lambda = "AWS_LAMBDA_FUNCTION_NAME" in os.environ

        # Always log to stdout, but use enqueue=False in Lambda (no multiprocessing)
        loguru_logger.add(
            sys.stdout,
            enqueue=not is_lambda,   # False in Lambda, True locally
            backtrace=True,
            level=level.upper(),
            format=log_format,
        )

        # Only log to file if NOT running in Lambda
        if not is_lambda:
            loguru_logger.add(
                str(filepath),
                rotation=rotation,
                retention=retention,
                compression=compression,
                enqueue=True,
                backtrace=True,
                level=level.upper(),
                format=log_format,
            )

        # Intercept standard logging and Uvicorn/FastAPI logs
        logging.basicConfig(handlers=[InterceptHandler()], level=0)
        logging.getLogger("uvicorn.access").handlers = [InterceptHandler()]
        for _log in ("uvicorn", "uvicorn.error", "fastapi"):
            _logger = logging.getLogger(_log)
            _logger.handlers = [InterceptHandler()]

        return loguru_logger.bind(method=None)

# Instantiate and bind logger for the whole app
logger = OverFastLogger.make_logger()
