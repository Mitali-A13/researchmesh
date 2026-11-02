"""Plain-code tools for finding and reading web pages.

Searching and scraping do not need an LLM, so they are normal functions.
That makes them faster, cheaper and predictable: the code (not a model)
decides which URLs exist and which pages were really read.
"""

import os

import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from tavily import TavilyClient

load_dotenv()

MAX_PAGE_CHARS = int(os.getenv("MAX_PAGE_CHARS", "6000"))  # per page
MIN_PAGE_CHARS = 200  # shorter than this = probably a menu / paywall / error page
REQUEST_TIMEOUT = 8
USER_AGENT = "Mozilla/5.0 (compatible; ThinkMeshBot/1.0)"

_tavily_client = None


def _get_tavily() -> TavilyClient:
    """Create the Tavily client on first use (so imports never fail without a key)."""
    global _tavily_client
    if _tavily_client is None:
        api_key = os.getenv("TAVILY_API_KEY")
        if not api_key:
            raise ValueError("TAVILY_API_KEY is not set in the environment")
        _tavily_client = TavilyClient(api_key=api_key)
    return _tavily_client


def search_web(query: str, max_results: int = 5) -> list[dict]:
    """Search the web and return a clean list: [{title, url, snippet}, ...].

    Duplicate URLs are removed. The raw list is returned as data, so no URL
    can be lost or invented later in the pipeline.
    """
    response = _get_tavily().search(query=query, max_results=max_results)

    results, seen = [], set()
    for item in response.get("results", []):
        url = item.get("url")
        if not url or url in seen:
            continue
        seen.add(url)
        results.append(
            {
                "title": item.get("title") or url,
                "url": url,
                "snippet": item.get("content") or "",
            }
        )
    return results


def fetch_page(url: str, max_chars: int = MAX_PAGE_CHARS) -> str:
    """Download a page and return its readable text.

    Raises an exception on any problem (bad status, not a web page, too
    little text) so the caller can decide what to do instead of silently
    getting an error string back.
    """
    resp = requests.get(
        url, timeout=REQUEST_TIMEOUT, headers={"User-Agent": USER_AGENT}
    )
    resp.raise_for_status()

    content_type = resp.headers.get("Content-Type", "").lower()
    if "html" not in content_type and "text" not in content_type:
        raise ValueError(f"Not a readable web page ({content_type or 'unknown type'})")

    soup = BeautifulSoup(resp.text, "html.parser")
    for tag in soup(
        ["script", "style", "nav", "footer", "header", "aside", "noscript", "form"]
    ):
        tag.decompose()

    text = " ".join(soup.get_text(separator=" ", strip=True).split())
    if len(text) < MIN_PAGE_CHARS:
        raise ValueError("Page had too little readable text")

    return text[:max_chars]
