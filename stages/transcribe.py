"""
stages/transcribe.py — Transcribe audio using Groq API or local Whisper.

Uses direct HTTP requests — no Groq SDK, no pydantic dependency.

Input:  audio file path
Output: dict with "text" (full string) and "segments" (list of timed chunks)

Test independently:
    python3 -c "
    import yaml, logging
    from stages.transcribe import transcribe
    config = yaml.safe_load(open('config.yaml'))
    logger = logging.getLogger(); logging.basicConfig(level=logging.DEBUG)
    result = transcribe('output/test_audio.mp3', config, logger)
    print(result['text'][:200])
    "
"""

import requests
from pathlib import Path


def transcribe(audio_path: str, config: dict, logger) -> dict:
    """
    Transcribe audio file. Routes to Groq or local Whisper
    based on config['transcription']['provider'].

    Args:
        audio_path: path to audio file
        config:     full config dict
        logger:     pipeline logger

    Returns:
        {
            "text":     "full transcript as one string",
            "segments": [{"start": 4.2, "end": 5.1, "text": "..."}, ...]
        }
    """
    provider = config["transcription"]["provider"]
    logger.debug(f"Transcription provider: {provider}")

    if provider == "groq":
        return _transcribe_groq(audio_path, config, logger)
    elif provider == "local":
        return _transcribe_local(audio_path, config, logger)
    else:
        raise ValueError(f"Unknown transcription provider: '{provider}'. "
                         f"Choose 'groq' or 'local' in config.yaml")


# ── Groq (direct HTTP, no SDK) ────────────────────────────────────────────────

def _transcribe_groq(audio_path: str, config: dict, logger) -> dict:
    """
    Call Groq's Whisper endpoint directly via multipart form upload.
    Docs: https://console.groq.com/docs/speech-text
    """
    api_key = config["transcription"]["api_key"]
    model   = config["transcription"].get("model", "whisper-large-v3")
    lang    = config["transcription"].get("language", "en")
    path    = Path(audio_path)

    logger.debug(f"Groq transcription: model={model}, file={path.name}, "
                 f"size={path.stat().st_size / 1_000_000:.2f}MB")

    with open(path, "rb") as f:
        response = requests.post(
            "https://api.groq.com/openai/v1/audio/transcriptions",
            headers={
                "Authorization": f"Bearer {api_key}",
                # Do NOT set Content-Type manually here —
                # requests sets it automatically with the correct
                # multipart boundary when using files=
            },
            files={
                "file": (path.name, f, _mime_type(path)),
            },
            data={
                "model":                   model,
                "language":                lang,
                "response_format":         "verbose_json",
            },
            timeout=120,   # large files can take a moment
        )

    if response.status_code != 200:
        logger.error(f"Groq API error {response.status_code}: {response.text[:500]}")
        response.raise_for_status()

    data = response.json()
    logger.debug(f"Groq response: {len(data.get('segments', []))} segments")
    return _normalise(data)


# ── Local Whisper (on-device, no network) ─────────────────────────────────────

def _transcribe_local(audio_path: str, config: dict, logger) -> dict:
    try:
        import whisper
    except ImportError:
        raise ImportError(
            "openai-whisper not installed. "
            "Run: pip install openai-whisper --break-system-packages\n"
            "Note: also requires ffmpeg and a model download on first run."
        )

    model_name = config["transcription"].get("local_model", "base")
    logger.debug(f"Loading local Whisper model: {model_name}")
    logger.info("Local Whisper loading — may take 30-60s on first run "
                "while the model downloads")

    model  = whisper.load_model(model_name)
    result = model.transcribe(
        audio_path,
        language=config["transcription"].get("language", "en"),
    )
    return _normalise(result)


# ── Shared helpers ────────────────────────────────────────────────────────────

def _normalise(data: dict) -> dict:
    """
    Convert either a Groq or local Whisper response into our
    standard internal format so downstream stages don't care
    which provider ran.
    """
    segments = [
        {
            "start": seg.get("start", 0),
            "end":   seg.get("end",   0),
            "text":  seg.get("text",  "").strip(),
        }
        for seg in data.get("segments", [])
    ]
    return {
        "text":     data.get("text", "").strip(),
        "segments": segments,
    }


def _mime_type(path: Path) -> str:
    return {
        ".mp3":  "audio/mpeg",
        ".wav":  "audio/wav",
        ".m4a":  "audio/mp4",
        ".ogg":  "audio/ogg",
        ".flac": "audio/flac",
    }.get(path.suffix.lower(), "audio/mpeg")
