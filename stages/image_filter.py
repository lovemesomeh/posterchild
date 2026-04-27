"""
stages/image_filter.py — Image crops and aesthetic filters.

All functions accept and return (path, alt_text) tuples so alt_text
is never lost as images pass through processing stages.

Two independent features:
  crop_for_instagram()  — center-crop to safe aspect ratio (always runs
                          before social posting regardless of other settings)
  filter_images()       — brightness/saturation/watermark (optional, config-driven)
"""

import subprocess
from pathlib import Path


# ── Platform crop ─────────────────────────────────────────────────────────────

def crop_for_instagram(stills: list, logger) -> list:
    """
    Center-crop each still to a platform-safe aspect ratio.

    Instagram requires width/height >= 0.8 (4:5 portrait minimum).
    We target 4:5 for portrait sources, 5:4 for landscape — always
    cropping inward, never scaling up. Alt_text is preserved unchanged.

    Portrait source  (e.g. 1080x1920, ratio=0.56):
        → 1080x1350  (4:5, ratio=0.80) ✓
    Landscape source (e.g. 1920x1080, ratio=1.78):
        → 1350x1080  (5:4, ratio=1.25) ✓

    Args:
        stills: list of (path, alt_text) tuples
        logger: pipeline logger

    Returns:
        List of (cropped_path, alt_text) tuples.
    """
    cropped = []

    for still in stills:
        path, alt_text = _unpack(still)
        src_path  = Path(path)
        dest_path = src_path.parent / f"{src_path.stem}_crop{src_path.suffix}"

        # Portrait (iw < ih): keep width, crop height to iw*5/4  → 4:5
        # Landscape (iw > ih): crop width to ih*5/4, keep height → 5:4
        vf = r"crop=if(gt(iw\,ih)\,ih*5/4\,iw):if(gt(iw\,ih)\,ih\,iw*5/4)"
        cmd = ["ffmpeg", "-y", "-i", str(src_path), "-vf", vf, str(dest_path)]

        logger.debug(f"Crop: {src_path.name} → {dest_path.name}")
        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode != 0:
            logger.warning(f"Crop failed for {src_path.name}: "
                           f"{result.stderr[-200:].strip()} — using original")
            cropped.append((str(src_path), alt_text))
        else:
            cropped.append((str(dest_path), alt_text))

    return cropped


# ── Aesthetic filter (optional) ───────────────────────────────────────────────

def filter_images(stills: list, config: dict, logger) -> list:
    """
    Apply aesthetic filters (brightness, saturation, watermark).
    Alt_text is preserved unchanged.

    Args:
        stills: list of (path, alt_text) tuples
        config: full config dict
        logger: pipeline logger

    Returns:
        List of (filtered_path, alt_text) tuples.
    """
    cfg      = config["image_filter"]
    filtered = []

    for still in stills:
        path, alt_text = _unpack(still)
        src_path = Path(path)
        dst_path = src_path.parent / f"{src_path.stem}_filtered{src_path.suffix}"

        vf  = _build_vf(cfg)
        cmd = ["ffmpeg", "-y", "-i", str(src_path), "-vf", vf, str(dst_path)]

        logger.debug(f"Filter: {src_path.name}")
        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode != 0:
            logger.warning(f"Filter failed for {src_path.name} — using original")
            filtered.append((str(src_path), alt_text))
        else:
            filtered.append((str(dst_path), alt_text))

    return filtered


# ── Helpers ───────────────────────────────────────────────────────────────────

def _unpack(still) -> tuple:
    """Accept either a (path, alt_text) tuple or a plain path string."""
    if isinstance(still, tuple):
        return still[0], still[1]
    return str(still), ""


def _build_vf(cfg: dict) -> str:
    filters = []
    brightness = cfg.get("brightness", 0)
    saturation = cfg.get("saturation", 1)
    if brightness != 0 or saturation != 1:
        filters.append(f"eq=brightness={brightness}:saturation={saturation}")
    if cfg.get("watermark", False):
        text     = cfg.get("watermark_text", "")
        position = cfg.get("watermark_position", "bottom_right")
        x, y    = _watermark_position(position)
        filters.append(
            f"drawtext=text='{text}':fontsize=24:fontcolor=white@0.7:x={x}:y={y}"
        )
    return ",".join(filters) if filters else "copy"


def _watermark_position(position: str) -> tuple:
    return {
        "bottom_right": ("W-tw-10", "H-th-10"),
        "bottom_left":  ("10",      "H-th-10"),
        "top_right":    ("W-tw-10", "10"),
        "top_left":     ("10",      "10"),
    }.get(position, ("W-tw-10", "H-th-10"))