"""Standardized logging configuration for local-first AI tools."""
import logging
from typing import Optional

from rich.console import Console
from rich.logging import RichHandler


def setup_logging(
    level: int = logging.INFO,
    show_path: bool = False,
    console: Optional[Console] = None,
) -> None:
    """Configure global logging using Rich for pretty terminal output.

    Args:
        level: The logging level (e.g. logging.DEBUG).
        show_path: Whether to show the file path in log output.
        console: Optional Rich Console instance.
    """
    logging.basicConfig(
        level=level,
        format="%(message)s",
        datefmt="[%X]",
        handlers=[
            RichHandler(
                rich_tracebacks=True,
                show_path=show_path,
                console=console,
                markup=True,
            )
        ],
    )

    # Suppress verbose logs from noisy third-party libraries
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("ollama").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """Return a logger instance with the given name."""
    return logging.getLogger(name)
