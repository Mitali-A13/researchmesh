"""Collects the sources for a report.

The code (not the LLM) owns the source list. Every source gets a number
that never changes, and the Writer must cite those numbers.
"""

import os
from concurrent.futures import ThreadPoolExecutor

from dotenv import load_dotenv

from backend.custom_tools import fetch_page, search_web

load_dotenv()

MAX_SOURCES = int(os.getenv("MAX_SOURCES", "5"))


def _read_source(found: dict) -> dict:
    """Try to read the full page. Fall back to the search snippet if that fails."""
    try:
        return {
            **found,
            "text": fetch_page(found["url"]),
            "read": "full",
            "error": None,
        }
    except Exception as exc:
        snippet = found.get("snippet", "")
        return {
            **found,
            "text": snippet,
            "read": "snippet" if snippet else "failed",
            "error": str(exc)[:150],
        }


def gather_sources(
    topic: str, max_sources: int = MAX_SOURCES
) -> tuple[list[dict], list[str]]:
    """Search, then read all pages at the same time.

    Returns (sources, warnings). Each source looks like:
        {"id": 1, "title": ..., "url": ..., "text": ..., "read": "full" | "snippet"}
    """
    found = search_web(topic, max_results=max_sources)
    if not found:
        raise ValueError("No search results found for this topic.")

    with ThreadPoolExecutor(max_workers=len(found)) as pool:
        read = list(pool.map(_read_source, found))

    sources, warnings = [], []
    for item in read:
        if item["read"] == "failed":
            warnings.append(f"Could not read {item['url']}")
            continue
        if item["read"] == "snippet":
            warnings.append(
                f"Only a short snippet was available for {item['url']} ({item['error']})"
            )
        sources.append(
            {
                "id": len(sources) + 1,
                "title": item["title"],
                "url": item["url"],
                "text": item["text"],
                "read": item["read"],
            }
        )

    if not sources:
        raise ValueError("Could not read any of the sources. Please try again.")

    return sources, warnings


def format_sources_for_prompt(sources: list[dict]) -> str:
    """Numbered text block that is handed to the Writer."""
    blocks = []
    for s in sources:
        blocks.append(
            f"[{s['id']}] {s['title']}\nURL: {s['url']}\nContent: {s['text']}"
        )
    return "\n\n".join(blocks)


def format_sources_section(sources: list[dict]) -> str:
    """The 'Sources' list added to the final report by code, using real URLs only."""
    lines = ["## Sources", ""]
    for s in sources:
        note = "" if s["read"] == "full" else " _(snippet only)_"
        lines.append(f"- **[{s['id']}]** [{s['title']}]({s['url']}){note}")
    return "\n".join(lines)


def public_view(sources: list[dict]) -> list[dict]:
    """Sources without the big text, safe to send to the frontend."""
    return [
        {"id": s["id"], "title": s["title"], "url": s["url"], "read": s["read"]}
        for s in sources
    ]
