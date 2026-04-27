"""
stages/article.py — Assemble transcript text and stills into a markdown file.

Input:  edited text, list of (path, alt_text) tuples, video name stem
Output: self-contained post folder:
    ~/pipeline/output/my_video_2026-04-24_143022/
        post.md          ← article with alt_text in image references
        still_01.jpg     ← images copied here alongside the markdown
        still_02.jpg

Alt text comes from the transcript sentence spoken immediately after
each "look here" cue — no extra API calls needed.
"""

import re
import shutil
from datetime import datetime
from pathlib import Path


def compile_article(text: str, stills: list, video_stem: str,
                    config: dict, logger) -> str:
    """
    Build a self-contained post folder with markdown and images.

    Args:
        text:       body text (raw or LLM-edited transcript)
        stills:     list of (path, alt_text) tuples
        video_stem: filename of source video without extension
        config:     full config dict
        logger:     pipeline logger

    Returns:
        Path to the compiled markdown file.
    """
    cfg        = config["article"]
    output_dir = Path(config["pipeline"]["output_dir"]).expanduser()

    timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    post_dir  = output_dir / f"{video_stem}_{timestamp}"
    post_dir.mkdir(parents=True, exist_ok=True)
    logger.debug(f"Post folder: {post_dir}")

    # Copy stills into post folder, rename sequentially, preserve alt_text
    local_stills = []   # list of (relative_filename, alt_text)
    for i, still in enumerate(stills):
        path, alt_text = _unpack(still)
        src_path  = Path(path)
        dest_name = f"still_{i+1:02d}{src_path.suffix}"
        dest_path = post_dir / dest_name
        shutil.copy2(src_path, dest_path)
        local_stills.append((dest_name, alt_text))
        logger.debug(f"Copied: {src_path.name} → {dest_name}  alt={repr(alt_text)}")

    # Title
    prefix        = cfg.get("default_title_prefix", "Show Your Work:")
    readable_name = video_stem.replace("_", " ").replace("-", " ").title()
    title         = f"{prefix} {readable_name}"

    # Build markdown
    placement = cfg.get("image_placement", "after_section")
    md = _build_markdown(title, text, local_stills, placement)

    md_path = post_dir / "post.md"
    md_path.write_text(md, encoding="utf-8")

    logger.info(f"Post folder ready: {post_dir}")
    logger.debug(f"Article: {len(md.split())} words, {len(local_stills)} image(s)")
    return str(md_path)


# ── Markdown builders ─────────────────────────────────────────────────────────

def _build_markdown(title: str, text: str,
                    stills: list, placement: str) -> str:
    date_str = datetime.now().strftime("%B %d, %Y")
    header   = f"# {title}\n\n*{date_str}*\n\n"

    if placement == "top":
        return header + _images_md(stills) + "\n" + _paragraphs_md(text)
    elif placement == "end":
        return header + _paragraphs_md(text) + "\n" + _images_md(stills)
    else:
        return header + _interleaved_md(text, stills)


def _images_md(stills: list) -> str:
    """Markdown image references with alt text."""
    lines = []
    for name, alt in stills:
        alt_safe = alt if alt else "Show your work image"
        lines.append(f"![{alt_safe}]({name})\n")
    return "\n".join(lines)


def _paragraphs_md(text: str) -> str:
    sentences = re.split(r'(?<=[.!?])\s+', text.strip())
    paras, chunk = [], []
    for i, sent in enumerate(sentences):
        chunk.append(sent)
        if len(chunk) >= 3 or i == len(sentences) - 1:
            paras.append(" ".join(chunk))
            chunk = []
    return "\n\n".join(paras) + "\n"


def _interleaved_md(text: str, stills: list) -> str:
    sentences = re.split(r'(?<=[.!?])\s+', text.strip())
    paras, chunk = [], []
    for i, sent in enumerate(sentences):
        chunk.append(sent)
        if len(chunk) >= 3 or i == len(sentences) - 1:
            paras.append(" ".join(chunk))
            chunk = []

    if not stills:
        return "\n\n".join(paras) + "\n"

    interval  = max(1, len(paras) // (len(stills) + 1))
    insert_at = {interval * (j + 1) for j in range(len(stills))}

    parts      = []
    still_iter = iter(stills)
    for i, para in enumerate(paras):
        parts.append(para)
        if i + 1 in insert_at:
            try:
                name, alt = next(still_iter)
                alt_safe  = alt if alt else "Show your work image"
                parts.append(f"\n![{alt_safe}]({name})\n")
            except StopIteration:
                pass

    for name, alt in still_iter:
        alt_safe = alt if alt else "Show your work image"
        parts.append(f"\n![{alt_safe}]({name})\n")

    return "\n\n".join(parts) + "\n"


# ── Helper ────────────────────────────────────────────────────────────────────

def _unpack(still) -> tuple:
    """Accept either a (path, alt_text) tuple or a plain path string."""
    if isinstance(still, tuple):
        return still[0], still[1]
    return str(still), ""