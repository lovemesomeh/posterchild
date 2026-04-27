"""
logger.py — Pipeline logging setup.

Creates one timestamped log file per run, plus a
'last_run.log' symlink always pointing at the most recent.
Sends a Termux notification on completion if enabled.
"""

import logging
import os
import subprocess
from datetime import datetime
from pathlib import Path


def setup_logger(config: dict, run_id: str) -> logging.Logger:
    """
    Set up and return the pipeline logger for this run.

    Args:
        config:  full parsed config dict
        run_id:  timestamp string identifying this run, e.g. "2026-04-24_143022"

    Returns:
        Configured Logger instance.
    """
    log_dir = Path(config["pipeline"]["log_dir"]).expanduser()
    log_dir.mkdir(parents=True, exist_ok=True)

    log_file = log_dir / f"{run_id}.log"
    last_run_link = log_dir / "last_run.log"

    # --- formatter ---
    fmt = "%(asctime)s  %(levelname)-7s %(message)s"
    datefmt = "%Y-%m-%d %H:%M:%S"
    formatter = logging.Formatter(fmt, datefmt=datefmt)

    # --- file handler (this run) ---
    file_handler = logging.FileHandler(log_file)
    file_handler.setFormatter(formatter)

    # --- console handler (visible in Termux terminal) ---
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)

    # --- assemble logger ---
    logger = logging.getLogger("pipeline")
    logger.setLevel(logging.DEBUG)
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    # --- update last_run.log symlink ---
    try:
        if last_run_link.is_symlink() or last_run_link.exists():
            last_run_link.unlink()
        last_run_link.symlink_to(log_file)
    except OSError:
        pass  # non-fatal if symlink fails (e.g. filesystem limitation)

    logger.info(f"Log file: {log_file}")
    return logger


def notify(message: str, config: dict, logger: logging.Logger) -> None:
    """
    Send a Termux notification if enabled in config.
    Silently skips if termux-notification is not available
    (e.g. when testing on a desktop).

    Args:
        message: notification body text
        config:  full parsed config dict
        logger:  pipeline logger
    """
    if not config["pipeline"].get("notify_on_complete", False):
        return

    try:
        subprocess.run(
            ["termux-notification",
             "--title", "Pipeline",
             "--content", message],
            timeout=5,
            check=False,
            capture_output=True,
        )
    except FileNotFoundError:
        logger.debug("termux-notification not available — skipping notification")
    except subprocess.TimeoutExpired:
        logger.debug("termux-notification timed out — skipping")


def clean_old_logs(config: dict, logger: logging.Logger) -> None:
    """
    Delete log files older than log_keep_days.

    Args:
        config: full parsed config dict
        logger: pipeline logger
    """
    keep_days = config["pipeline"].get("log_keep_days", 30)
    log_dir = Path(config["pipeline"]["log_dir"]).expanduser()
    cutoff = datetime.now().timestamp() - (keep_days * 86400)
    deleted = 0

    for f in log_dir.glob("*.log"):
        if f.is_symlink():
            continue
        if f.stat().st_mtime < cutoff:
            f.unlink()
            deleted += 1

    if deleted:
        logger.info(f"Cleaned {deleted} log file(s) older than {keep_days} days")
