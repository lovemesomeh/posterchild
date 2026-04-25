"""
stages/editorial.py — Optional LLM pass to clean up the transcript.

Input:  raw transcript text string
Output: edited text string

The prompt lives in config.yaml so you can tune it without
touching this file.
"""


def editorial_pass(text: str, config: dict, logger) -> str:
    """
    Send transcript text to configured LLM for an editorial pass.

    Args:
        text:   raw transcript text
        config: full config dict
        logger: pipeline logger

    Returns:
        Edited text string.
    """
    provider = config["llm_editorial"]["provider"]
    prompt   = config["llm_editorial"]["prompt"]
    model    = config["llm_editorial"]["model"]

    logger.debug(f"LLM editorial provider: {provider}, model: {model}")

    if provider == "anthropic":
        return _run_anthropic(text, prompt, model, config, logger)
    elif provider == "openai":
        return _run_openai(text, prompt, model, config, logger)
    elif provider == "groq":
        return _run_groq_llm(text, prompt, model, config, logger)
    else:
        raise ValueError(f"Unknown LLM provider: '{provider}'. "
                         f"Choose 'anthropic', 'openai', or 'groq'.")


# ── Anthropic (Claude) ────────────────────────────────────────────────────────

def _run_anthropic(text, prompt, model, config, logger) -> str:
    try:
        import anthropic
    except ImportError:
        raise ImportError(
            "anthropic package not installed. "
            "Run: pip install anthropic --break-system-packages"
        )

    client = anthropic.Anthropic(api_key=config["llm_editorial"]["api_key"])
    response = client.messages.create(
        model=model,
        max_tokens=config["llm_editorial"].get("max_tokens", 4096),
        messages=[{
            "role": "user",
            "content": f"{prompt}\n\n---\n\n{text}"
        }]
    )
    result = response.content[0].text
    logger.debug(f"LLM output: {len(result.split())} words")
    return result


# ── OpenAI ────────────────────────────────────────────────────────────────────

def _run_openai(text, prompt, model, config, logger) -> str:
    try:
        from openai import OpenAI
    except ImportError:
        raise ImportError(
            "openai package not installed. "
            "Run: pip install openai --break-system-packages"
        )

    client = OpenAI(api_key=config["llm_editorial"]["api_key"])
    response = client.chat.completions.create(
        model=model,
        max_tokens=config["llm_editorial"].get("max_tokens", 4096),
        messages=[
            {"role": "system", "content": prompt},
            {"role": "user",   "content": text},
        ]
    )
    result = response.choices[0].message.content
    logger.debug(f"LLM output: {len(result.split())} words")
    return result


# ── Groq (LLM, not Whisper) ───────────────────────────────────────────────────

def _run_groq_llm(text, prompt, model, config, logger) -> str:
    try:
        from groq import Groq
    except ImportError:
        raise ImportError(
            "groq package not installed. "
            "Run: pip install groq --break-system-packages"
        )

    client = Groq(api_key=config["llm_editorial"]["api_key"])
    response = client.chat.completions.create(
        model=model,
        max_tokens=config["llm_editorial"].get("max_tokens", 4096),
        messages=[
            {"role": "system", "content": prompt},
            {"role": "user",   "content": text},
        ]
    )
    result = response.choices[0].message.content
    logger.debug(f"LLM output: {len(result.split())} words")
    return result
