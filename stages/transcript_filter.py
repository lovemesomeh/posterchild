"""
stages/transcript_filter.py — Mechanical cleanup of raw Whisper transcript.

Runs BEFORE the LLM editorial pass. Handles things that are
always wrong and don't need AI judgment:
  - Remove spoken cue words ("look here")
  - Strip filler words ("um", "uh", "you know")
  - Fix punctuation artifacts
  - Normalize whitespace

Each filter is a separate, named function. To add a new filter:
  1. Write a function that takes a string and returns a string
  2. Add it to the FILTERS list at the bottom of this file
  3. Toggle it on/off in config.yaml under transcript_filter:

To disable the entire stage, set in config.yaml:
    transcript_filter:
      enabled: false
"""

import re


# ── Individual filter functions ───────────────────────────────────────────────
# Each takes a text string and returns a cleaned text string.
# Keep them small and single-purpose.

def remove_cue_words(text: str, config: dict) -> str:
    """
    Remove the spoken keyword trigger(s) from the transcript text.
    Uses the same keyword defined in config['keyword']['trigger']
    so there's only one place to change it.
    """
    cue = config["keyword"]["trigger"]
    # Case-insensitive, remove the word plus any surrounding comma/period
    pattern = rf'\s*,?\s*{re.escape(cue)}\s*,?\s*'
    return re.sub(pattern, ' ', text, flags=re.IGNORECASE).strip()


def remove_filler_words(text: str, config: dict) -> str:
    """
    Remove common spoken filler words.
    Add to the list below as you notice patterns in your transcripts.
    """
    fillers = [
        r'\bum+\b',
        r'\buh+\b',
        r'\bmhm\b',
        r'\bhmm+\b',
        r'\byou know\b',
        r'\blike I said\b',
        r'\bbasically\b',
        r'\bactually\b',        # remove if you use this intentionally
        r'\bright\?\s*',        # "right?" as a verbal tic
        r'\bokay so\b',
        r'\bso yeah\b',
        r'\band stuff\b',
        r'\band things\b',
    ]
    for pattern in fillers:
        text = re.sub(pattern, '', text, flags=re.IGNORECASE)
    return text


def fix_whitespace(text: str, config: dict) -> str:
    """
    Collapse multiple spaces, fix space-before-punctuation,
    and strip leading/trailing whitespace.
    """
    text = re.sub(r'  +', ' ', text)           # multiple spaces → one
    text = re.sub(r'\s+([.,!?;:])', r'\1', text)  # space before punctuation
    text = re.sub(r'\n{3,}', '\n\n', text)     # excessive blank lines
    return text.strip()


def fix_repeated_words(text: str, config: dict) -> str:
    """
    Remove immediately repeated words — common Whisper artifact.
    e.g. "the the bracket" → "the bracket"
    """
    return re.sub(r'\b(\w+)\s+\1\b', r'\1', text, flags=re.IGNORECASE)


def capitalize_sentences(text: str, config: dict) -> str:
    """
    Ensure first letter of each sentence is capitalized.
    Whisper usually handles this, but just in case.
    """
    return re.sub(
        r'(^|[.!?]\s+)([a-z])',
        lambda m: m.group(1) + m.group(2).upper(),
        text
    )


# ── Filter registry ───────────────────────────────────────────────────────────
# Controls which filters run and in what order.
# To disable a filter without deleting it, comment it out here
# OR use the per-filter config flags in config.yaml.

FILTERS = [
    ("remove_cue_words",     remove_cue_words),
    ("remove_filler_words",  remove_filler_words),
    ("fix_repeated_words",   fix_repeated_words),
    ("fix_whitespace",       fix_whitespace),
    ("capitalize_sentences", capitalize_sentences),
]


# ── Stage entry point ─────────────────────────────────────────────────────────

def filter_transcript(text: str, config: dict, logger) -> str:
    """
    Run all enabled filters on the transcript text in order.

    Each filter can be individually toggled in config.yaml:
        transcript_filter:
          enabled: true
          filters:
            remove_cue_words: true
            remove_filler_words: true
            fix_repeated_words: true
            fix_whitespace: true
            capitalize_sentences: true

    Args:
        text:   raw transcript string
        config: full config dict
        logger: pipeline logger

    Returns:
        Cleaned transcript string.
    """
    filter_cfg = config.get("transcript_filter", {})
    per_filter  = filter_cfg.get("filters", {})

    original_len = len(text.split())
    logger.debug(f"Transcript filter input: {original_len} words")

    for name, fn in FILTERS:
        # Default to enabled unless explicitly set to false
        if per_filter.get(name, True):
            text = fn(text, config)
            logger.debug(f"  Applied: {name}")
        else:
            logger.debug(f"  Skipped: {name} (disabled in config)")

    cleaned_len = len(text.split())
    removed     = original_len - cleaned_len
    logger.info(f"Transcript filter: {removed} word(s) removed, "
                f"{cleaned_len} words remaining")
    return text
