"""Loguru-based logging configuration for API-Sports MCP Server."""

import json
import sys
from pathlib import Path
from typing import Any

from loguru import logger

from .config import get_settings


def serialize_record(record: dict[str, Any]) -> str:
    """Serialize log record to JSON format."""
    subset = {
        "timestamp": record["time"].isoformat(),
        "level": record["level"].name,
        "message": record["message"],
        "module": record["name"],
        "function": record["function"],
        "line": record["line"],
    }

    # Add extra fields if present
    if record.get("extra"):
        subset["extra"] = record["extra"]

    # Add exception info if present
    if record.get("exception"):
        subset["exception"] = {
            "type": record["exception"].type.__name__ if record["exception"].type else None,
            "value": str(record["exception"].value) if record["exception"].value else None,
            "traceback": record["exception"].traceback if record["exception"].traceback else None,
        }

    return json.dumps(subset, default=str)


def setup_logging() -> None:
    """Configure loguru logging based on settings."""
    settings = get_settings()

    # Remove default handler
    logger.remove()

    # Console handler - always enabled
    console_format = (
        "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
        "<level>{level: <8}</level> | "
        "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
        "<level>{message}</level>"
    )

    if settings.log_format == "json":
        logger.add(
            sys.stdout,
            format="{message}",
            serialize=True,
            level=settings.log_level,
        )
    else:
        logger.add(
            sys.stdout,
            format=console_format,
            level=settings.log_level,
            colorize=True,
        )

    # File handler
    log_path = Path(settings.log_file_path)
    log_path.parent.mkdir(parents=True, exist_ok=True)

    if settings.log_format == "json":
        logger.add(
            log_path,
            format="{message}",
            serialize=True,
            rotation=settings.log_rotation_size,
            retention=f"{settings.log_retention_days} days",
            compression="gz",
            level=settings.log_level,
        )
    else:
        file_format = (
            "{time:YYYY-MM-DD HH:mm:ss.SSS} | "
            "{level: <8} | "
            "{name}:{function}:{line} | "
            "{message}"
        )
        logger.add(
            log_path,
            format=file_format,
            rotation=settings.log_rotation_size,
            retention=f"{settings.log_retention_days} days",
            compression="gz",
            level=settings.log_level,
        )

    # Add error file handler for ERROR and above
    error_log_path = log_path.parent / f"{log_path.stem}_errors{log_path.suffix}"
    logger.add(
        error_log_path,
        format=file_format if settings.log_format == "text" else "{message}",
        serialize=settings.log_format == "json",
        rotation=settings.log_rotation_size,
        retention=f"{settings.log_retention_days * 2} days",  # Keep errors longer
        compression="gz",
        level="ERROR",
    )


def get_logger(name: str = None) -> "logger":
    """Get a contextualized logger instance."""
    if name:
        return logger.bind(module=name)
    return logger


# Performance logging decorator
def log_performance(func):
    """Decorator to log function performance."""
    import functools
    import time

    @functools.wraps(func)
    async def async_wrapper(*args, **kwargs):
        start_time = time.perf_counter()
        request_id = kwargs.get("request_id", "unknown")

        logger.debug(
            f"Starting {func.__name__}",
            extra={"function": func.__name__, "request_id": request_id}
        )

        try:
            result = await func(*args, **kwargs)
            elapsed_time = time.perf_counter() - start_time

            logger.success(
                f"Completed {func.__name__} in {elapsed_time:.3f}s",
                extra={
                    "function": func.__name__,
                    "elapsed_time": elapsed_time,
                    "request_id": request_id,
                }
            )
            return result

        except Exception as e:
            elapsed_time = time.perf_counter() - start_time
            logger.error(
                f"Failed {func.__name__} after {elapsed_time:.3f}s: {str(e)}",
                extra={
                    "function": func.__name__,
                    "elapsed_time": elapsed_time,
                    "request_id": request_id,
                    "error": str(e),
                }
            )
            raise

    @functools.wraps(func)
    def sync_wrapper(*args, **kwargs):
        start_time = time.perf_counter()
        request_id = kwargs.get("request_id", "unknown")

        logger.debug(
            f"Starting {func.__name__}",
            extra={"function": func.__name__, "request_id": request_id}
        )

        try:
            result = func(*args, **kwargs)
            elapsed_time = time.perf_counter() - start_time

            logger.success(
                f"Completed {func.__name__} in {elapsed_time:.3f}s",
                extra={
                    "function": func.__name__,
                    "elapsed_time": elapsed_time,
                    "request_id": request_id,
                }
            )
            return result

        except Exception as e:
            elapsed_time = time.perf_counter() - start_time
            logger.error(
                f"Failed {func.__name__} after {elapsed_time:.3f}s: {str(e)}",
                extra={
                    "function": func.__name__,
                    "elapsed_time": elapsed_time,
                    "request_id": request_id,
                    "error": str(e),
                }
            )
            raise

    # Return appropriate wrapper based on function type
    import asyncio
    if asyncio.iscoroutinefunction(func):
        return async_wrapper
    return sync_wrapper


# Initialize logging on module import
setup_logging()
