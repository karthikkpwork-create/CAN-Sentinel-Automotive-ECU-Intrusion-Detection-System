"""Logging setup: quiet console, detailed rotating file."""
from __future__ import annotations

import logging
import logging.handlers
import os


def setup_logging(name: str, console_level: str, log_file: str) -> logging.Logger:
    """Console shows `console_level` and above; the file always records DEBUG.

    Per-frame messages are logged at DEBUG, so they land in the file without
    flooding the terminal. The file rotates (1 MB x 3) so it cannot grow forever.
    """
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)
    logger.handlers.clear()
    logger.propagate = False

    console = logging.StreamHandler()
    console.setLevel(getattr(logging, console_level.upper(), logging.INFO))
    console.setFormatter(logging.Formatter("%(asctime)s %(levelname)-7s %(message)s", "%H:%M:%S"))
    logger.addHandler(console)

    try:
        folder = os.path.dirname(log_file)
        if folder:
            os.makedirs(folder, exist_ok=True)
        fh = logging.handlers.RotatingFileHandler(
            log_file, maxBytes=1_000_000, backupCount=3, encoding="utf-8"
        )
        fh.setLevel(logging.DEBUG)
        fh.setFormatter(logging.Formatter("%(asctime)s.%(msecs)03d %(levelname)-7s %(message)s", "%Y-%m-%d %H:%M:%S"))
        logger.addHandler(fh)
    except OSError as exc:
        logger.warning("cannot write log file %s (%s); logging to console only", log_file, exc.strerror)
    return logger
