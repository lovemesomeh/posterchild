"""
stages/article.py — Assemble transcript text and stills into a markdown file.

Input:  edited text, list of still paths, video name stem
Output: path to compiled .md file inside a self-contained post folder

Each run produces a folder like:
    ~/pipeline/output/my_video_2026-04-24_143022/
        post.md          <- the article, images referenced by filename only
        still_01.jpg     <- images copied here alongside the markdown
        still_02.jpg

This makes the post fully portable — grab the folder, take it anywhere.
Drop it into a blog editor, zip it, sync it to a PC — images always
travel with the text.
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
        stills:     list of absolute paths to still images
        video_stem: filename of source video without extension (used for title)
        config:     full config dict
        logger:     pipeline logger

    Returns:
        Path to the compiled markdown file (inside the post folder).
    """
    cfg        = config["article"]
    output_dir = Path(config["pipeline"]["output_dir"]).expanduser()

    # -- Create a timestamped folder for this post
    timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    post_dir  = output_dir / f"{video_stem}_{timestamp}"
    post_dir.mkdir(parents=True, exist_ok=True)
    logger.debug(f"Post folder: {post_dir}")

    # -- Copy stills into the post folder, rename sequentially
    local_stills = []
    for i, src in enumerate(stills):
        src_path  = Path(src)
        dest_name = f"still_{i+1:02d}{src_path.suffix}"
        dest_path = post_dir / dest_name
        shutil.copy2(src_path, dest_path)
        local_stills.append(dest_name)   # relative name only
        logger.debug(f"Copied still: {src_path.name} -> {dest_name}")

    # -- Title
    prefix        = cfg.get("default_title_prefix", "Show Your Work:")
    readable_name = video_stem.replace("_", " ").replace("-", " ").title()
    title         = f"{prefix} {readable_name}"

    # -- Build markdown using relative image filenames
    placement = cfg.get("image_placement", "after_section")
    md = _build_markdown(title, text, local_stills, placement)

    # -- Write markdown into the post folder
    md_path = post_dir / "post.md"
    md_path.write_text(md, encoding="utf-8")

    logger.info(f"Post folder ready: {post_dir}")
    logger.debug(f"Article: {len(md.split())} words, {len(local_stills)} images")
    return str(md_path)


# -- Markdown builders --------------------------------------------------------

def _build_markdown(title: str, text: str, stills: list, placement: str) -> str:
    """Build the full markdown document."""
    date_str = datetime.now().strftime("%B %d, %Y")
    header   = f"# {title}\n\n*{date_str}*\n\n"

    if placement == "top":
        return header + _images_md(stills) + "\n" + _paragraphs_md(text)
    elif placement == "end":
        return header + _paragraphs_md(text) + "\n" + _images_md(stills)
    else:  # "after_section" — interleave images between paragraphs
        return header + _interleaved_md(text, stills)


def _paragraphs_md(text: str) -> str:
    """
    Split text into paragraphs. Whisper output is often one long string;
    we break on sentence boundaries to create readable paragraphs.
    """
    sentences = re.split(r'(?<=[.!?])\s+', text.strip())

    paras = []
    chunk = []
    for i, sent in enumerate(sentences):
        chunk.append(sent)
        if len(chunk) >= 3 or i == len(sentences) - 1:
            paras.append(" ".join(chunk))
            chunk = []

    return "\n\n".join(paras) + "\n"


def _images_md(stills: list) -> str:
    """Generate markdown image references using relative filenames."""
    return "\n".join(f"![Still {i+1}]({name})\n" for i, name in enumerate(stills))


def _interleaved_md(text: str, stills: list) -> str:
    """
    Distribute images evenly through the text.
    With 2 stills and 6 paragraphs: image after para 2 and para 4.
    """
    sentences = re.split(r'(?<=[.!?])\s+', text.strip())

    paras = []
    chunk = []
    for i, sent in enumerate(sentences):
        chunk.append(sent)
        if len(chunk) >= 3 or i == len(sentences) - 1:
            paras.append(" ".join(chunk))
            chunk = []

    if not stills:
        return "\n\n".join(paras) + "\n"

    n_paras  = len(paras)
    n_images = len(stills)
    interval  = max(1, n_paras // (n_images + 1))
    insert_at = {interval * (j + 1) for j in range(n_images)}

    parts      = []
    still_iter = iter(stills)
    for i, para in enumerate(paras):
        parts.append(para)
        if i + 1 in insert_at:
            try:
                parts.append(f"\n![]({next(still_iter)})\n")
            except StopIteration:
                pass

    for remaining in still_iter:
        parts.append(f"\n![]({remaining})\n")

    return "\n\n".join(parts) + "\n"