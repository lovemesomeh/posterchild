"""
stages/frames.py — Find keyword timestamps in transcript, extract stills with FFmpeg.

Input:  video path, transcript dict
Output: list of (path, alt_text) tuples — one per keyword occurrence

alt_text is taken from the first sentence of the segment immediately
following the keyword — exactly what you said out loud while pointing
at the thing you're showing.

Test independently:
    python3 -c "
    import yaml, logging
    from stages.frames import extract_frames
    config = yaml.safe_load(open('config.yaml'))
    logger = logging.getLogger(); logging.basicConfig(level=logging.DEBUG)
    transcript = {
        'text': 'I built this bracket. Look here, this is the bracket. Then I mounted it. Look here, this is the finished result.',
        'segments': [
            {'start': 0.0,  'end': 3.0,  'text': 'I built this bracket.'},
            {'start': 3.0,  'end': 5.1,  'text': 'Look here,'},
            {'start': 5.1,  'end': 8.0,  'text': 'this is the bracket.'},
            {'start': 8.0,  'end': 11.0, 'text': 'Then I mounted it.'},
            {'start': 11.0, 'end': 13.5, 'text': 'Look here,'},
            {'start': 13.5, 'end': 16.0, 'text': 'this is the finished result.'},
        ]
    }
    stills = extract_frames('test_media/test.mp4', transcript, config, logger)
    for path, alt in stills:
        print(f'  {path}  alt={repr(alt)}')
    "
"""

import re
import subprocess
from pathlib import Path


def extract_frames(video_path, transcript: dict, config: dict, logger) -> list:
    """
    Search transcript segments for the trigger keyword,
    extract a still image at each match, and derive alt_text from
    the sentence spoken immediately after the keyword.

    Args:
        video_path: path to original video
        transcript: dict with 'text' and 'segments' keys
        config:     full config dict
        logger:     pipeline logger

    Returns:
        List of (image_path, alt_text) tuples.
        alt_text is "" if no following segment was found.
        Returns [] if keyword not found — pipeline continues gracefully.
    """
    video      = Path(video_path)
    keyword    = config["keyword"]["trigger"].lower().strip()
    padding_ms = config["keyword"].get("padding_ms", 500)
    fmt        = config["keyword"].get("format", "jpg")
    quality    = config["keyword"].get("quality", 85)

    output_dir = Path(config["pipeline"]["output_dir"]).expanduser()
    output_dir.mkdir(parents=True, exist_ok=True)

    segments = transcript["segments"]

    # ── Find all segments containing the keyword (with their index) ───────
    matches = _find_keyword_matches(segments, keyword)
    logger.info(f"Keyword '{keyword}' found {len(matches)} time(s)")

    if not matches:
        logger.warning(
            f"Keyword '{keyword}' not found in transcript. "
            f"No stills extracted. Check output/*/post.md transcript."
        )
        return []

    # ── Extract still + alt_text at each match ────────────────────────────
    stills = []
    for i, (seg_idx, seg) in enumerate(matches):
        timestamp_s = seg["end"] + (padding_ms / 1000)
        timestamp_s = max(0, timestamp_s)

        out_path = output_dir / f"{video.stem}_still_{i+1:02d}.{fmt}"

        success = _grab_frame(str(video), timestamp_s, str(out_path), quality, logger)

        if success:
            # Alt text = first sentence of the segment right after the keyword
            alt_text = _extract_alt_text(segments, seg_idx, keyword, logger)
            stills.append((str(out_path), alt_text))
            logger.debug(
                f"Still {i+1}: t={timestamp_s:.2f}s → {out_path.name}  "
                f"alt={repr(alt_text)}"
            )
        else:
            logger.warning(f"Failed to extract still {i+1} at t={timestamp_s:.2f}s")

    return stills


# ── Internal helpers ──────────────────────────────────────────────────────────

def _find_keyword_matches(segments: list, keyword: str) -> list:
    """
    Return list of (index, segment) for every segment containing the keyword.
    Case-insensitive.
    """
    return [
        (i, seg)
        for i, seg in enumerate(segments)
        if keyword in seg["text"].lower()
    ]


def _extract_alt_text(segments: list, keyword_idx: int,
                      keyword: str, logger) -> str:
    """
    Find the first usable sentence after the keyword segment.

    Skips segments that are themselves just the keyword or a short filler.
    Returns the first sentence of the first substantive segment found.
    Returns "" if nothing suitable follows.
    """
    for seg in segments[keyword_idx + 1:]:
        text = seg["text"].strip()

        # Skip empty or very short segments (likely just the cue word itself)
        words = text.split()
        if len(words) <= 2:
            continue

        # Skip if this segment is also just the keyword
        if keyword.lower() in text.lower() and len(words) <= 4:
            continue

        # Take the first sentence
        sentences = re.split(r'(?<=[.!?,])\s+', text)
        candidate = sentences[0].strip().rstrip(",.!?")
        if candidate:
            return candidate

    logger.debug("No alt_text found after keyword — using empty string")
    return ""


def _grab_frame(video_path: str, timestamp_s: float,
                out_path: str, quality: int, logger) -> bool:
    """
    Use FFmpeg to extract one frame at the given timestamp.
    Returns True on success, False on failure.
    """
    qscale = max(2, int(2 + (100 - quality) * 29 / 100))

    cmd = [
        "ffmpeg", "-y",
        "-ss", f"{timestamp_s:.3f}",
        "-i", video_path,
        "-frames:v", "1",
        "-q:v", str(qscale),
        out_path,
    ]

    logger.debug(f"FFmpeg frame cmd: {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode != 0:
        logger.error(f"FFmpeg frame error: {result.stderr[-300:]}")
        return False

    return True