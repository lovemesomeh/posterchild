"""
stages/article.py — Assemble transcript text and stills into a markdown file.

Input:  edited text, list of still paths, video name stem
Output: path to compiled .md file

The markdown file is what gets sent to WordPress and forms the
basis of social captions. Easy to inspect and edit before posting.
"""

from datetime import datetime
from pathlib import Path


def compile_article(text: str, stills: list, video_stem: str,
                    config: dict, logger) -> str:
    """
    Build a markdown article from text and still images.

    Args:
        text:       body text (raw or LLM-edited transcript)
        stills:     list of absolute paths to still images
        video_stem: filename of source video without extension (used for title)
        config:     full config dict
        logger:     pipeline logger

    Returns:
        Path to the compiled markdown file.
    """
    cfg        = config["article"]
    output_dir = Path(config["pipeline"]["output_dir"]).expanduser()
    output_dir.mkdir(parents=True, exist_ok=True)

    # ── Title ─────────────────────────────────────────────────────────────
    prefix = cfg.get("default_title_prefix", "Show Your Work:")
    # Convert snake_case or kebab-case filename to readable words
    readable_name = video_stem.replace("_", " ").replace("-", " ").title()
    title = f"{prefix} {readable_name}"

    # ── Build markdown ────────────────────────────────────────────────────
    placement = cfg.get("image_placement", "after_section")
    md = _build_markdown(title, text, stills, placement)

    # ── Write file ────────────────────────────────────────────────────────
    timestamp  = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    out_path   = output_dir / f"{video_stem}_{timestamp}.md"
    out_path.write_text(md, encoding="utf-8")

    logger.debug(f"Article: {len(md.split())} words, {len(stills)} images")
    return str(out_path)


# ── Markdown builders ─────────────────────────────────────────────────────────

def _build_markdown(title: str, text: str, stills: list, placement: str) -> str:
    """Build the full markdown document."""
    date_str = datetime.now().strftime("%B %d, %Y")
    header   = f"# {title}\n\n*{date_str}*\n\n"

    if placement == "top":
        images_block = _images_md(stills)
        body         = _paragraphs_md(text)
        return header + images_block + "\n" + body

    elif placement == "end":
        body         = _paragraphs_md(text)
        images_block = _images_md(stills)
        return header + body + "\n" + images_block

    else:  # "after_section" — interleave images between paragraphs
        return header + _interleaved_md(text, stills)


def _paragraphs_md(text: str) -> str:
    """
    Split text into paragraphs. Whisper output is often one long string;
    we break on sentence boundaries to create readable paragraphs.
    """
    import re
    # Split on ". " followed by a capital letter (rough sentence boundary)
    sentences = re.split(r'(?<=[.!?])\s+', text.strip())

    # Group into ~3-sentence paragraphs
    paras = []
    chunk = []
    for i, sent in enumerate(sentences):
        chunk.append(sent)
        if len(chunk) >= 3 or i == len(sentences) - 1:
            paras.append(" ".join(chunk))
            chunk = []

    return "\n\n".join(paras) + "\n"


def _images_md(stills: list) -> str:
    """Generate markdown image references for all stills."""
    lines = []
    for i, path in enumerate(stills):
        name = Path(path).name
        lines.append(f"![Still {i+1}]({path})\n")
    return "\n".join(lines)


def _interleaved_md(text: str, stills: list) -> str:
    """
    Distribute images evenly through the text.
    With 2 stills and 6 paragraphs: image after para 2 and para 4.
    """
    import re
    sentences = re.split(r'(?<=[.!?])\s+', text.strip())

    # Group into paragraphs
    paras = []
    chunk = []
    for i, sent in enumerate(sentences):
        chunk.append(sent)
        if len(chunk) >= 3 or i == len(sentences) - 1:
            paras.append(" ".join(chunk))
            chunk = []

    if not stills:
        return "\n\n".join(paras) + "\n"

    # Calculate insertion points
    n_paras  = len(paras)
    n_images = len(stills)
    # Insert image after every (n_paras // (n_images + 1)) paragraphs
    interval  = max(1, n_paras // (n_images + 1))
    insert_at = {interval * (j + 1) for j in range(n_images)}

    parts      = []
    still_iter = iter(stills)
    for i, para in enumerate(paras):
        parts.append(para)
        if i + 1 in insert_at:
            try:
                still_path = next(still_iter)
                parts.append(f"\n![Still]({still_path})\n")
            except StopIteration:
                pass

    # Any remaining stills go at the end
    for remaining in still_iter:
        parts.append(f"\n![Still]({remaining})\n")

    return "\n\n".join(parts) + "\n"
