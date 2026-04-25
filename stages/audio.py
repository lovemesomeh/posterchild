"""
stages/audio.py — Extract audio from video using FFmpeg.

Input:  video file path
Output: path to extracted audio file (mp3)

This stage is entirely local — no API calls, no network.
Test it independently:
    python3 -c "
    import yaml, logging
    from stages.audio import extract_audio
    config = yaml.safe_load(open('config.yaml'))
    logger = logging.getLogger(); logging.basicConfig(level=logging.DEBUG)
    print(extract_audio('test_media/test.mp4', config, logger))
    "
"""

import subprocess
from pathlib import Path


def extract_audio(video_path, config: dict, logger) -> str:
    """
    Extract audio from video file using FFmpeg.

    Args:
        video_path: Path to input video (str or Path)
        config:     full config dict
        logger:     pipeline logger

    Returns:
        Path to extracted audio file as string.

    Raises:
        RuntimeError if FFmpeg fails or is not installed.
    """
    video = Path(video_path)
    audio_cfg = config["audio"]
    output_dir = Path(config["pipeline"]["output_dir"]).expanduser()
    output_dir.mkdir(parents=True, exist_ok=True)

    audio_out = output_dir / f"{video.stem}_audio.{audio_cfg['format']}"

    cmd = [
        "ffmpeg",
        "-y",                               # overwrite if exists
        "-i", str(video),
        "-vn",                              # drop video stream
        "-ar", str(audio_cfg["sample_rate"]),
        "-ac", str(audio_cfg["channels"]),
        "-ab", audio_cfg["bitrate"],
        str(audio_out),
    ]

    logger.debug(f"FFmpeg audio cmd: {' '.join(cmd)}")

    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        logger.error(f"FFmpeg stderr: {result.stderr[-500:]}")  # last 500 chars
        raise RuntimeError(f"FFmpeg audio extraction failed (exit {result.returncode})")

    size_mb = audio_out.stat().st_size / 1_000_000
    logger.debug(f"Audio size: {size_mb:.2f} MB")

    return str(audio_out)
