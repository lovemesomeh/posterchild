"""
stages/transcribe.py — Transcribe audio using Groq API or local Whisper.

Input:  audio file path
Output: dict with "text" (full string) and "segments" (list of timed chunks)

The segment format is the same whether Groq or local Whisper is used,
so downstream stages don't need to care which provider ran.

Test independently (requires a real audio file and Groq key):
    python3 -c "
    import yaml, logging
    from stages.transcribe import transcribe
    config = yaml.safe_load(open('config.yaml'))
    logger = logging.getLogger(); logging.basicConfig(level=logging.DEBUG)
    result = transcribe('output/test_audio.mp3', config, logger)
    print(result['text'][:200])
    "
"""

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


# ── Groq (cloud, fast, tiny bandwidth — audio only) ──────────────────────────

def _transcribe_groq(audio_path: str, config: dict, logger) -> dict:
    try:
        from groq import Groq
    except ImportError:
        raise ImportError(
            "groq package not installed. Run: pip install groq --break-system-packages"
        )

    client = Groq(api_key=config["transcription"]["api_key"])
    model  = config["transcription"].get("model", "whisper-large-v3")
    lang   = config["transcription"].get("language", "en")

    logger.debug(f"Groq model: {model}")

    with open(audio_path, "rb") as f:
        response = client.audio.transcriptions.create(
            file=f,
            model=model,
            language=lang,
            response_format="verbose_json",  # gives us word-level timestamps
            timestamp_granularities=["segment"],
        )

    # Normalise into our standard format
    segments = [
        {
            "start": seg.start,
            "end":   seg.end,
            "text":  seg.text.strip(),
        }
        for seg in response.segments
    ]

    return {
        "text":     response.text,
        "segments": segments,
    }


# ── Local Whisper (on-device, slower, no network needed) ─────────────────────

def _transcribe_local(audio_path: str, config: dict, logger) -> dict:
    try:
        import whisper
    except ImportError:
        raise ImportError(
            "openai-whisper not installed. "
            "Run: pip install openai-whisper --break-system-packages"
        )

    model_name = config["transcription"].get("local_model", "base")
    logger.debug(f"Loading local Whisper model: {model_name}")
    logger.info("Local Whisper loading — this may take 30-60s on first run")

    model = whisper.load_model(model_name)
    result = model.transcribe(audio_path, language=config["transcription"].get("language", "en"))

    # Normalise into our standard format
    segments = [
        {
            "start": seg["start"],
            "end":   seg["end"],
            "text":  seg["text"].strip(),
        }
        for seg in result.get("segments", [])
    ]

    return {
        "text":     result["text"],
        "segments": segments,
    }
