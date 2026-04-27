"""Report persistence: YAML frontmatter, slug filenames, append follow-ups, list reports.

Reports are markdown files with a YAML frontmatter block. The frontmatter lets the
UI and the follow-up CLI identify parent research reports and track follow-up counts.
"""

from __future__ import annotations

import datetime
import logging
import re
from pathlib import Path
from typing import Any

import yaml

from marketia.core import FLASH_MODEL, ImageOut

logger = logging.getLogger("marketia")

_SLUG_MAX_LEN = 60
_TITLE_MAX_LEN = 80
_PROMPT_SUMMARY_MAX_LEN = 200
_CONTEXT_EXCERPT_LEN = 1500
_TAGS_MAX = 5


def slugify(text: str) -> str:
    """Convert free text to a URL-friendly slug (lowercase, hyphen-separated, ``<=60`` chars)."""
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_]+", "-", text)
    text = re.sub(r"-+", "-", text)
    return text[:_SLUG_MAX_LEN]


def generate_frontmatter(
    title: str,
    *,
    report_type: str = "research",
    tags: list[str] | None = None,
    prompt_summary: str = "",
    tokens_used: int = 0,
    estimated_cost: float = 0.0,
    follow_up_count: int = 0,
    interaction_id: str = "",
    agent: str = "",
    plan_rounds: int = 0,
    attachments: list[str] | None = None,
    file_search_stores: list[str] | None = None,
) -> str:
    """Render a YAML frontmatter block (including the ``---`` fences)."""
    now = datetime.datetime.now()
    data = {
        "title": title,
        "type": report_type,
        "date": now.strftime("%Y-%m-%d"),
        "time": now.strftime("%H:%M:%S"),
        "tags": tags or [],
        "prompt_summary": prompt_summary[:_PROMPT_SUMMARY_MAX_LEN] if prompt_summary else "",
        "tokens_used": tokens_used,
        "estimated_cost": f"${estimated_cost:.4f}",
        "follow_up_count": follow_up_count,
        "interaction_id": interaction_id,
        "agent": agent,
        "plan_rounds": plan_rounds,
        "attachments": attachments or [],
        "file_search_stores": file_search_stores or [],
        "last_updated": now.strftime("%Y-%m-%d %H:%M:%S"),
    }
    yaml_str = yaml.dump(data, default_flow_style=False, allow_unicode=True, sort_keys=False)
    return f"---\n{yaml_str}---\n\n"


def parse_frontmatter(content: str) -> tuple[dict, str]:
    """Split markdown with optional YAML frontmatter into (frontmatter_dict, body).

    Returns ``({}, content)`` if no frontmatter is present or if parsing fails.
    """
    if not content.startswith("---"):
        return {}, content

    end_idx = content.find("---", 3)
    if end_idx == -1:
        return {}, content

    yaml_str = content[3:end_idx].strip()
    body = content[end_idx + 3 :].strip()
    try:
        frontmatter = yaml.safe_load(yaml_str) or {}
    except yaml.YAMLError:
        logger.warning("Failed to parse frontmatter; returning empty dict")
        return {}, content
    return frontmatter, body


def update_frontmatter(content: str, updates: dict) -> str:
    """Merge ``updates`` into the content's frontmatter and bump ``last_updated``."""
    frontmatter, body = parse_frontmatter(content)
    frontmatter.update(updates)
    frontmatter["last_updated"] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    yaml_str = yaml.dump(frontmatter, default_flow_style=False, allow_unicode=True, sort_keys=False)
    return f"---\n{yaml_str}---\n\n{body}"


def _resolve_output_dir(output_dir: str) -> Path:
    """Resolve and validate an output directory path, falling back to CWD if empty."""
    if not output_dir:
        return Path.cwd()
    resolved = Path(output_dir).expanduser().resolve()
    if not resolved.is_dir():
        raise NotADirectoryError(f"Output directory does not exist: {resolved}")
    return resolved


_MIME_TO_EXT = {
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "image/gif": ".gif",
    "image/webp": ".webp",
}


def save_report_assets(slug: str, images: list[ImageOut], assets_dir: Path) -> list[str]:
    """Write images to ``assets_dir`` and return relative markdown paths.

    Creates the directory if needed. Returns a list of relative paths like
    ``<slug>_assets/image_01.png`` suitable for embedding in markdown.
    """
    if not images:
        return []
    assets_dir.mkdir(exist_ok=True)
    rel_paths: list[str] = []
    for i, img in enumerate(images, start=1):
        ext = _MIME_TO_EXT.get(img.mime_type, ".png")
        filename = f"image_{i:02d}{ext}"
        (assets_dir / filename).write_bytes(img.data)
        rel_paths.append(f"{assets_dir.name}/{filename}")
    logger.info("Saved %d image(s) to %s", len(images), assets_dir)
    return rel_paths


def _inject_image_links(content: str, images: list[ImageOut], slug: str, assets_dir: Path) -> str:
    """Save images and append markdown links to content."""
    rel_paths = save_report_assets(slug, images, assets_dir)
    if not rel_paths:
        return content
    links = "\n".join(f"![]({p})" for p in rel_paths)
    return f"{content}\n\n{links}"


def save_research_report(
    content: str,
    title: str,
    *,
    tags: list[str] | None = None,
    prompt_summary: str = "",
    tokens_used: int = 0,
    estimated_cost: float = 0.0,
    interaction_id: str = "",
    agent: str = "",
    plan_rounds: int = 0,
    attachments: list[str] | None = None,
    images: list[ImageOut] | None = None,
    file_search_stores: list[str] | None = None,
    output_dir: str = "",
) -> Path:
    """Write a new research report with frontmatter and a slug-based filename.

    Handles filename collisions by appending ``-2``, ``-3``, ... before the suffix.
    Returns the absolute path of the written file.
    """
    target_dir = _resolve_output_dir(output_dir)
    slug = slugify(title) if title else "research"
    date_str = datetime.datetime.now().strftime("%Y-%m-%d")
    base_name = f"{slug}_{date_str}.md"

    path = target_dir / base_name
    counter = 2
    while path.exists():
        path = target_dir / f"{slug}_{date_str}-{counter}.md"
        counter += 1

    final_content = content
    if images:
        assets_dir = target_dir / f"{slug}_assets"
        final_content = _inject_image_links(content, images, slug, assets_dir)

    frontmatter = generate_frontmatter(
        title=title,
        tags=tags,
        prompt_summary=prompt_summary,
        tokens_used=tokens_used,
        estimated_cost=estimated_cost,
        interaction_id=interaction_id,
        agent=agent,
        plan_rounds=plan_rounds,
        attachments=attachments,
        file_search_stores=file_search_stores,
    )
    path.write_text(
        f"{frontmatter}# {title}\n\n## Research Report\n\n{final_content}", encoding="utf-8"
    )
    logger.info("Saved report: %s", path)
    return path


def append_followup_to_report(
    report_path: str | Path,
    followup_content: str,
    question: str,
    *,
    tokens_used: int = 0,
    estimated_cost: float = 0.0,
    mode: str = "",
) -> int:
    """Append a follow-up section to an existing report and bump ``follow_up_count``.

    Returns the new follow-up count (1-based).
    """
    path = Path(report_path)
    existing = path.read_text(encoding="utf-8")
    frontmatter, body = parse_frontmatter(existing)

    count = int(frontmatter.get("follow_up_count", 0)) + 1
    frontmatter["follow_up_count"] = count
    frontmatter["last_updated"] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    header_suffix = f"{question[:50]}{'...' if len(question) > 50 else ''}"
    mode_tag = f" | Mode: {mode}" if mode else ""
    section = (
        f"\n\n---\n\n## Follow-up {count}: {header_suffix}\n"
        f"*Asked: {timestamp} | Tokens: {tokens_used:,} | Cost: ${estimated_cost:.4f}"
        f"{mode_tag}*\n\n"
        f"{followup_content}"
    )

    yaml_str = yaml.dump(frontmatter, default_flow_style=False, allow_unicode=True, sort_keys=False)
    path.write_text(f"---\n{yaml_str}---\n\n{body}{section}", encoding="utf-8")
    logger.info("Appended follow-up #%d to %s", count, path)
    return count


def list_reports(search_dir: str = "") -> list[dict]:
    """List research reports (markdown with ``type: research`` or no frontmatter).

    Returns a list of dicts with keys ``filename`` (full path string), ``basename``,
    ``title``, ``follow_up_count``, and ``display`` — sorted by modification time,
    newest first.
    """
    target = Path(search_dir) if search_dir else Path.cwd()
    try:
        candidates = [p for p in target.iterdir() if p.suffix == ".md" and p.name != "README.md"]
    except OSError:
        logger.warning("Cannot list directory: %s", target)
        return []

    reports: list[dict] = []
    for path in candidates:
        try:
            content = path.read_text(encoding="utf-8")
            frontmatter, _ = parse_frontmatter(content)
        except (OSError, UnicodeDecodeError):
            reports.append(
                {
                    "filename": str(path),
                    "basename": path.name,
                    "title": path.name,
                    "follow_up_count": 0,
                    "display": path.name,
                }
            )
            continue

        if frontmatter and frontmatter.get("type") not in (None, "research"):
            continue

        title = frontmatter.get("title", path.name) if frontmatter else path.name
        follow_ups = int(frontmatter.get("follow_up_count", 0)) if frontmatter else 0
        reports.append(
            {
                "filename": str(path),
                "basename": path.name,
                "title": title,
                "follow_up_count": follow_ups,
                "display": f"{title} ({follow_ups} follow-ups)" if follow_ups else title,
            }
        )

    reports.sort(key=lambda r: Path(r["filename"]).stat().st_mtime, reverse=True)
    return reports


def generate_title_and_tags(
    prompt: str,
    report_content: str,
    api_client: Any,
    *,
    model: str = FLASH_MODEL,
) -> tuple[str, list[str]]:
    """Ask a fast model to propose a title and tags for a research report.

    On any failure, falls back to ``(prompt[:60], [])`` so the caller can always
    produce a usable filename.
    """
    extraction_prompt = f"""Based on this research prompt and report, generate:
1. A concise, descriptive title (5-8 words max, no quotes)
2. 3-5 relevant tags (lowercase, single words or hyphenated)

PROMPT: {prompt[:500]}

REPORT EXCERPT: {report_content[:_CONTEXT_EXCERPT_LEN]}

Respond in this exact format:
TITLE: <your title here>
TAGS: tag1, tag2, tag3, tag4"""

    try:
        response = api_client.models.generate_content(model=model, contents=extraction_prompt)
        result_text = (response.text or "").strip()
    except Exception:
        # Any SDK or transport error — fall back cleanly rather than failing the save.
        logger.exception("Title/tag generation failed; falling back to prompt excerpt")
        return prompt[:60].strip(), []

    title = prompt[:60].strip()
    tags: list[str] = []
    for line in result_text.split("\n"):
        upper = line.upper()
        if upper.startswith("TITLE:"):
            title = line.split(":", 1)[1].strip()[:_TITLE_MAX_LEN]
        elif upper.startswith("TAGS:"):
            raw = line.split(":", 1)[1].strip()
            tags = [t.strip().lower().replace(" ", "-") for t in raw.split(",") if t.strip()][
                :_TAGS_MAX
            ]
    return title, tags
