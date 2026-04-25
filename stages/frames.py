"""
stages/frames.py — Find keyword timestamps in transcript, extract stills with FFmpeg.

Input:  video path, transcript dict
Output: list of paths to extracted still images

Test independently:
    python3 -c "
    import yaml, logging
    from stages.frames import extract_frames
    config = yaml.safe_load(open('config.yaml'))
    logger = logging.getLogger(); logging.basicConfig(level=logging.DEBUG)
    transcript = {
        'text': 'Today look here we go',
        'segments': [{'start': 4.2, 'end': 5.1, 'text': 'look here'}]
    }
    stills = extract_frames('test_media/test.mp4', transcript, config, logger)
    print(stills)
    "
"""

import subprocess
from pathlib import Path


def extract_frames(video_path, transcript: dict, config: dict, logger) -> list:
    """
    Search transcript segments for the trigger keyword,
    then use FFmpeg to grab a still image at each match.

    Args:
        video_path: path to original video
        transcript: dict with 'text' and 'segments' keys
        config:     full config dict
        logger:     pipeline logger

    Returns:
        List of paths to extracted still images (may be empty if
        keyword not found — pipeline continues gracefully).
    """
    video      = Path(video_path)
    keyword    = config["keyword"]["trigger"].lower().strip()
    padding_ms = config["keyword"].get("padding_ms", 500)
    fmt        = config["keyword"].get("format", "jpg")
    quality    = config["keyword"].get("quality", 85)

    output_dir = Path(config["pipeline"]["output_dir"]).expanduser()
    output_dir.mkdir(parents=True, exist_ok=True)

    # ── Find all segments that contain the keyword ────────────────────────
    matches = _find_keyword_segments(transcript["segments"], keyword)
    logger.info(f"Keyword '{keyword}' found {len(matches)} time(s)")

    if not matches:
        logger.warning(
            f"Keyword '{keyword}' not found in transcript. "
            f"Pipeline will continue but no stills will be extracted. "
            f"Check the transcript in output/ to verify the spoken cue."
        )
        return []

    # ── Extract a still at each match ─────────────────────────────────────
    stills = []
    for i, seg in enumerate(matches):
        # Timestamp = end of keyword segment + padding
        # (end of segment = camera has moved to show the thing)
        timestamp_s = seg["end"] + (padding_ms / 1000)
        timestamp_s = max(0, timestamp_s)   # don't go negative

        out_path = output_dir / f"{video.stem}_still_{i+1:02d}.{fmt}"

        success = _grab_frame(
            video_path=str(video),
            timestamp_s=timestamp_s,
            out_path=str(out_path),
            quality=quality,
            logger=logger,
        )

        if success:
            stills.append(str(out_path))
            logger.debug(
                f"Still {i+1}: t={timestamp_s:.2f}s → {out_path.name}"
            )
        else:
            logger.warning(f"Failed to extract still {i+1} at t={timestamp_s:.2f}s")

    return stills


# ── Internal helpers ──────────────────────────────────────────────────────────

def _find_keyword_segments(segments: list, keyword: str) -> list:
    """
    Return all segments whose text contains the trigger keyword.
    Case-insensitive. A keyword like 'look here' may span partial
    text in a single segment, which is fine — Whisper tends to group
    short phrases together.
    """
    matches = []
    for seg in segments:
        if keyword in seg["text"].lower():
            matches.append(seg)
    return matches


def _grab_frame(video_path: str, timestamp_s: float,
                out_path: str, quality: int, logger) -> bool:
    """
    Use FFmpeg to extract one frame at the given timestamp.

    Returns True on success, False on failure.
    """
    # Convert quality (0-100) to FFmpeg's qscale (2-31, lower = better)
    qscale = max(2, int(2 + (100 - quality) * 29 / 100))

    cmd = [
        "ffmpeg",
        "-y",
        "-ss", f"{timestamp_s:.3f}",    # seek BEFORE -i for speed
        "-i", video_path,
        "-frames:v", "1",               # grab exactly one frame
        "-q:v", str(qscale),
        out_path,
    ]

    logger.debug(f"FFmpeg frame cmd: {' '.join(cmd)}")

    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode != 0:
        logger.error(f"FFmpeg frame error: {result.stderr[-300:]}")
        return False

    return True
