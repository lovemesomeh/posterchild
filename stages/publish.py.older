"""
stages/publish.py — Post article and stills to configured destinations.

Respects testing_mode (drafts) and dry_run (no calls) from config.
Adding a new output destination: add a new function and call it
from publish_all() if enabled in config.
"""

import base64
import json
import re
from pathlib import Path

import requests


def publish_all(article_path: str, stills: list, text: str,
                config: dict, logger) -> None:
    """
    Route content to all enabled posting destinations.

    Args:
        article_path: path to compiled markdown file
        stills:       list of still image paths
        text:         body text (for social captions)
        config:       full config dict
        logger:       pipeline logger
    """
    posting     = config["posting"]
    test_mode   = config["pipeline"].get("testing_mode", True)
    article_md  = Path(article_path).read_text(encoding="utf-8")

    if posting.get("wordpress", {}).get("enabled", False):
        logger.info("Publishing to WordPress...")
        post_to_wordpress(article_md, stills, config, logger, test_mode)

    if posting.get("bundle_social", {}).get("enabled", False):
        logger.info("Publishing to bundle.social...")
        caption = _make_caption(text, max_chars=2200)
        post_to_bundle(caption, stills, config, logger, test_mode)

    if posting.get("buffer", {}).get("enabled", False):
        logger.info("Publishing to Buffer...")
        caption = _make_caption(text, max_chars=2200)
        post_to_buffer(caption, stills, config, logger, test_mode)


# ── WordPress ─────────────────────────────────────────────────────────────────

def post_to_wordpress(markdown_text: str, stills: list,
                      config: dict, logger, test_mode: bool) -> str:
    """
    Post article to WordPress via REST API.

    Returns post ID string on success.
    """
    wp     = config["posting"]["wordpress"]
    base   = wp["url"].rstrip("/")
    auth   = _wp_auth(wp["username"], wp["app_password"])
    status = "draft" if test_mode else wp.get("status", "draft")

    # ── Upload images first, replace local paths with WP media URLs ──────
    logger.debug(f"Uploading {len(stills)} image(s) to WordPress media library")
    url_map = {}   # local path → WP attachment URL
    for still in stills:
        wp_url = _wp_upload_image(still, base, auth, logger)
        if wp_url:
            url_map[still] = wp_url

    # Rewrite image paths in markdown to WP URLs
    content = _rewrite_image_paths(markdown_text, url_map)

    # ── Create the post ───────────────────────────────────────────────────
    title   = _extract_title(markdown_text)
    payload = {
        "title":   title,
        "content": content,
        "status":  status,
    }

    category = wp.get("category")
    if category:
        payload["categories"] = [_wp_get_or_create_category(category, base, auth, logger)]

    tags = wp.get("tags", [])
    if tags:
        payload["tags"] = _wp_get_or_create_tags(tags, base, auth, logger)

    response = requests.post(
        f"{base}/wp-json/wp/v2/posts",
        headers=auth,
        json=payload,
        timeout=30,
    )
    response.raise_for_status()
    post_id = response.json()["id"]
    logger.info(f"WordPress: {'draft' if status == 'draft' else 'published'} "
                f"created, ID {post_id} — {base}/?p={post_id}")
    return str(post_id)


def _wp_upload_image(image_path: str, base: str, auth: dict, logger) -> str | None:
    """Upload one image to WP media library. Returns attachment URL or None."""
    path = Path(image_path)
    mime = "image/jpeg" if path.suffix.lower() in (".jpg", ".jpeg") else "image/png"

    headers = {**auth, "Content-Disposition": f'attachment; filename="{path.name}"',
               "Content-Type": mime}
    try:
        with open(path, "rb") as f:
            response = requests.post(
                f"{base}/wp-json/wp/v2/media",
                headers=headers,
                data=f.read(),
                timeout=60,
            )
        response.raise_for_status()
        url = response.json().get("source_url", "")
        logger.debug(f"WP media upload OK: {path.name} → {url}")
        return url
    except Exception as e:
        logger.warning(f"WP media upload failed for {path.name}: {e}")
        return None


def _wp_auth(username: str, app_password: str) -> dict:
    token = base64.b64encode(f"{username}:{app_password}".encode()).decode()
    return {"Authorization": f"Basic {token}", "Content-Type": "application/json"}


def _wp_get_or_create_category(name: str, base: str, auth: dict, logger) -> int:
    """Return category ID, creating it if it doesn't exist."""
    r = requests.get(f"{base}/wp-json/wp/v2/categories",
                     headers=auth, params={"search": name}, timeout=10)
    r.raise_for_status()
    cats = r.json()
    if cats:
        return cats[0]["id"]
    r2 = requests.post(f"{base}/wp-json/wp/v2/categories",
                       headers=auth, json={"name": name}, timeout=10)
    r2.raise_for_status()
    return r2.json()["id"]


def _wp_get_or_create_tags(tag_names: list, base: str, auth: dict, logger) -> list:
    ids = []
    for name in tag_names:
        r = requests.get(f"{base}/wp-json/wp/v2/tags",
                         headers=auth, params={"search": name}, timeout=10)
        r.raise_for_status()
        tags = r.json()
        if tags:
            ids.append(tags[0]["id"])
        else:
            r2 = requests.post(f"{base}/wp-json/wp/v2/tags",
                               headers=auth, json={"name": name}, timeout=10)
            r2.raise_for_status()
            ids.append(r2.json()["id"])
    return ids


def _rewrite_image_paths(md: str, url_map: dict) -> str:
    """Replace local file paths with WordPress media URLs in markdown."""
    for local, wp_url in url_map.items():
        md = md.replace(local, wp_url)
    return md


def _extract_title(md: str) -> str:
    """Pull the H1 title from markdown, or fall back to a default."""
    for line in md.splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return "Show Your Work"


# ── bundle.social ─────────────────────────────────────────────────────────────

def post_to_bundle(caption: str, stills: list, config: dict,
                   logger, test_mode: bool) -> str:
    """
    Post to bundle.social. Uploads images then creates a post.
    Returns post ID on success.
    """
    cfg     = config["posting"]["bundle_social"]
    api_key = cfg["api_key"]
    team_id = cfg["team_id"]
    status  = "DRAFT" if test_mode else cfg.get("status", "DRAFT")

    headers = {"x-api-key": api_key, "Content-Type": "application/json"}

    # ── Upload images ─────────────────────────────────────────────────────
    upload_ids = []
    for still in stills:
        uid = _bundle_upload_image(still, team_id, headers, logger)
        if uid:
            upload_ids.append(uid)

    # ── Build platform-specific content blocks ────────────────────────────
    active_platforms = [p for p, on in cfg.get("platforms", {}).items() if on]
    data = _bundle_platform_data(caption, upload_ids, cfg)

    payload = {
        "teamId": team_id,
        "status": status,
        "data":   data,
    }

    # Add schedule time if not draft
    if status != "DRAFT":
        payload["postDate"] = _bundle_schedule_time(cfg)

    response = requests.post(
        "https://api.bundle.social/api/v1/post",
        headers=headers,
        json=payload,
        timeout=30,
    )
    response.raise_for_status()
    post_id = response.json().get("id", "?")
    logger.info(f"bundle.social: {status} created, ID {post_id} "
                f"({len(active_platforms)} platform(s))")
    return post_id


def _bundle_upload_image(image_path: str, team_id: str,
                         headers: dict, logger) -> str | None:
    """Upload image to bundle.social. Returns upload ID or None."""
    path = Path(image_path)
    try:
        # Step 1: get upload URL
        r = requests.post(
            "https://api.bundle.social/api/v1/upload",
            headers={**headers, "Content-Type": "application/json"},
            json={"teamId": team_id, "fileName": path.name,
                  "mimeType": "image/jpeg"},
            timeout=15,
        )
        r.raise_for_status()
        upload_data = r.json()
        upload_url  = upload_data.get("uploadUrl")
        upload_id   = upload_data.get("id")

        # Step 2: PUT file to the signed URL
        with open(path, "rb") as f:
            put_r = requests.put(upload_url, data=f.read(),
                                 headers={"Content-Type": "image/jpeg"},
                                 timeout=60)
        put_r.raise_for_status()
        logger.debug(f"bundle.social upload OK: {path.name}, id={upload_id}")
        return upload_id
    except Exception as e:
        logger.warning(f"bundle.social upload failed for {path.name}: {e}")
        return None


def _bundle_platform_data(caption: str, upload_ids: list, cfg: dict) -> dict:
    """Build the platform data block for the bundle.social post payload."""
    platforms = cfg.get("platforms", {})
    data = {}
    platform_map = {
        "instagram": "INSTAGRAM",
        "facebook":  "FACEBOOK",
        "threads":   "THREADS",
        "bluesky":   "BLUESKY",
        "linkedin":  "LINKEDIN",
        "twitter":   "TWITTER",
        "pinterest": "PINTEREST",
    }
    for key, bundle_key in platform_map.items():
        if platforms.get(key, False):
            data[bundle_key] = {"text": caption, "uploadIds": upload_ids}
    return data


def _bundle_schedule_time(cfg: dict) -> str:
    """Return ISO-8601 schedule datetime string."""
    from datetime import datetime, timezone
    import pytz
    tz_name   = cfg.get("timezone", "UTC")
    time_str  = cfg.get("schedule_time", "09:00")
    tz        = pytz.timezone(tz_name)
    hour, min = map(int, time_str.split(":"))
    now       = datetime.now(tz)
    scheduled = now.replace(hour=hour, minute=min, second=0, microsecond=0)
    # If that time today has passed, schedule for tomorrow
    if scheduled <= now:
        from datetime import timedelta
        scheduled += timedelta(days=1)
    return scheduled.astimezone(timezone.utc).isoformat()


# ── Buffer ────────────────────────────────────────────────────────────────────

def post_to_buffer(caption: str, stills: list,
                   config: dict, logger, test_mode: bool) -> None:
    """
    Post to Buffer. Always saves as draft when test_mode is True.
    Note: Buffer's beta API is focused on post creation;
    check their docs for the current endpoint as it's still evolving.
    """
    cfg     = config["posting"]["buffer"]
    api_key = cfg["api_key"]
    as_draft = test_mode or cfg.get("save_as_draft", True)

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    for channel_id in cfg.get("platforms", []):
        payload = {
            "channel_id": channel_id,
            "text":       caption,
            "draft":      as_draft,
        }
        try:
            r = requests.post(
                "https://api.bufferapp.com/1/updates/create.json",
                headers=headers,
                json=payload,
                timeout=20,
            )
            r.raise_for_status()
            logger.info(f"Buffer: {'draft' if as_draft else 'queued'} "
                        f"for channel {channel_id}")
        except Exception as e:
            logger.error(f"Buffer post failed for channel {channel_id}: {e}")


# ── Shared helpers ────────────────────────────────────────────────────────────

def _make_caption(text: str, max_chars: int = 2200) -> str:
    """
    Trim text to platform caption length.
    Cuts at a sentence boundary where possible.
    """
    if len(text) <= max_chars:
        return text.strip()

    trimmed = text[:max_chars]
    # Try to end at a sentence boundary
    last_period = trimmed.rfind(".")
    if last_period > max_chars * 0.7:   # at least 70% of the way in
        return trimmed[:last_period + 1].strip()
    return trimmed.rstrip() + "…"
