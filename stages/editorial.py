"""
stages/editorial.py — Optional LLM pass to clean up the transcript.

Uses direct HTTP requests — no Anthropic/OpenAI SDK, no pydantic dependency.

Input:  raw transcript text string
Output: edited text string

The prompt lives in config.yaml so you can tune it without
touching this file.

Test independently:
    python3 -c "
    import yaml, logging
    from stages.editorial import editorial_pass
    config = yaml.safe_load(open('config.yaml'))
    config['llm_editorial']['enabled'] = True
    logger = logging.getLogger(); logging.basicConfig(level=logging.DEBUG)
    result = editorial_pass('Today I built a thing. look here it is.', config, logger)
    print(result)
    "
"""

import requests


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
    api_key  = config["llm_editorial"]["api_key"]
    max_tok  = config["llm_editorial"].get("max_tokens", 4096)

    logger.debug(f"LLM editorial: provider={provider}, model={model}")

    if provider == "anthropic":
        return _run_anthropic(text, prompt, model, api_key, max_tok, logger)
    elif provider == "openai":
        return _run_openai(text, prompt, model, api_key, max_tok, logger)
    elif provider == "groq":
        return _run_groq_llm(text, prompt, model, api_key, max_tok, logger)
    else:
        raise ValueError(f"Unknown LLM provider: '{provider}'. "
                         f"Choose 'anthropic', 'openai', or 'groq'.")


# ── Anthropic (Claude) — direct HTTP ─────────────────────────────────────────

def _run_anthropic(text, prompt, model, api_key, max_tok, logger) -> str:
    """
    Call Anthropic Messages API directly.
    Docs: https://docs.anthropic.com/en/api/messages
    """
    response = requests.post(
        "https://api.anthropic.com/v1/messages",
        headers={
            "x-api-key":         api_key,
            "anthropic-version": "2023-06-01",
            "content-type":      "application/json",
        },
        json={
            "model":      model,
            "max_tokens": max_tok,
            "system":     prompt,
            "messages": [
                {"role": "user", "content": text}
            ],
        },
        timeout=120,
    )

    if response.status_code != 200:
        logger.error(f"Anthropic API error {response.status_code}: {response.text[:500]}")
        response.raise_for_status()

    data   = response.json()
    result = data["content"][0]["text"]
    logger.debug(f"Anthropic response: {len(result.split())} words")
    return result


# ── OpenAI — direct HTTP ──────────────────────────────────────────────────────

def _run_openai(text, prompt, model, api_key, max_tok, logger) -> str:
    """
    Call OpenAI Chat Completions API directly.
    Docs: https://platform.openai.com/docs/api-reference/chat
    """
    response = requests.post(
        "https://api.openai.com/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type":  "application/json",
        },
        json={
            "model":      model,
            "max_tokens": max_tok,
            "messages": [
                {"role": "system", "content": prompt},
                {"role": "user",   "content": text},
            ],
        },
        timeout=120,
    )

    if response.status_code != 200:
        logger.error(f"OpenAI API error {response.status_code}: {response.text[:500]}")
        response.raise_for_status()

    data   = response.json()
    result = data["choices"][0]["message"]["content"]
    logger.debug(f"OpenAI response: {len(result.split())} words")
    return result


# ── Groq LLM (not Whisper) — direct HTTP ─────────────────────────────────────

def _run_groq_llm(text, prompt, model, api_key, max_tok, logger) -> str:
    """
    Call Groq Chat Completions API directly.
    Same shape as OpenAI — Groq is OpenAI-compatible.
    Docs: https://console.groq.com/docs/text-chat
    """
    response = requests.post(
        "https://api.groq.com/openai/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type":  "application/json",
        },
        json={
            "model":      model,
            "max_tokens": max_tok,
            "messages": [
                {"role": "system", "content": prompt},
                {"role": "user",   "content": text},
            ],
        },
        timeout=120,
    )

    if response.status_code != 200:
        logger.error(f"Groq LLM API error {response.status_code}: {response.text[:500]}")
        response.raise_for_status()

    data   = response.json()
    result = data["choices"][0]["message"]["content"]
    logger.debug(f"Groq LLM response: {len(result.split())} words")
    return result
