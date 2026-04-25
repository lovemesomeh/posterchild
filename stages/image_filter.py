"""
stages/image_filter.py — Optional image adjustments via FFmpeg.

Input:  list of still image paths
Output: list of filtered image paths (originals preserved)

Disabled by default in config. Enable and tune in config.yaml:
    image_filter:
      enabled: true
      brightness: 0.05
      saturation: 1.2
      watermark: true
      watermark_text: "yoursite.com"
"""

import subprocess
from pathlib import Path


def filter_images(stills: list, config: dict, logger) -> list:
    """
    Apply configured filters to each still image.
    Saves filtered versions as separate files (originals untouched).

    Args:
        stills: list of paths to source images
        config: full config dict
        logger: pipeline logger

    Returns:
        List of paths to filtered images.
    """
    cfg = config["image_filter"]
    filtered = []

    for src in stills:
        src_path = Path(src)
        dst_path = src_path.parent / f"{src_path.stem}_filtered{src_path.suffix}"

        vf = _build_vf(cfg)
        cmd = ["ffmpeg", "-y", "-i", str(src_path), "-vf", vf, str(dst_path)]

        logger.debug(f"Filter cmd: {' '.join(cmd)}")

        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            logger.warning(f"Filter failed for {src_path.name}, using original")
            filtered.append(src)
        else:
            logger.debug(f"Filtered: {dst_path.name}")
            filtered.append(str(dst_path))

    return filtered


def _build_vf(cfg: dict) -> str:
    """Build the FFmpeg -vf filter string from config."""
    filters = []

    brightness = cfg.get("brightness", 0)
    saturation = cfg.get("saturation", 1)
    if brightness != 0 or saturation != 1:
        filters.append(f"eq=brightness={brightness}:saturation={saturation}")

    if cfg.get("watermark", False):
        text     = cfg.get("watermark_text", "")
        position = cfg.get("watermark_position", "bottom_right")
        x, y = _watermark_position(position)
        # drawtext requires ffmpeg built with --enable-libfreetype
        filters.append(
            f"drawtext=text='{text}':fontsize=24:fontcolor=white@0.7:"
            f"x={x}:y={y}"
        )

    return ",".join(filters) if filters else "copy"


def _watermark_position(position: str) -> tuple:
    """Return (x, y) FFmpeg expressions for common positions."""
    positions = {
        "bottom_right": ("W-tw-10", "H-th-10"),
        "bottom_left":  ("10",      "H-th-10"),
        "top_right":    ("W-tw-10", "10"),
        "top_left":     ("10",      "10"),
    }
    return positions.get(position, ("W-tw-10", "H-th-10"))
