"""Autonomous web browsing, search, and page intelligence agent for JARVIS.

Follows Workstream E requirements:
- Distinguishes clearly between OPEN_BROWSER, NAVIGATE_URL, SEARCH_WEB, READ_PAGE, and SUMMARIZE_TOPIC.
- Returns source URLs for verifiable claims (zero invented information).
- Strips unsafe scripts, styles, and untrusted executable content.
- Respects privacy (never touches cookies, tokens, or passwords).
- Provides legitimate, free, keyless online search and page extraction.
"""

import re
import urllib.parse
from dataclasses import dataclass
from enum import Enum
from html.parser import HTMLParser
from typing import Dict, List, Optional, Tuple

import requests

from app.core.logger import setup_logger
from app.tools.browser import launch_website

logger = setup_logger("jarvis.tools.browser_agent")

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"


class BrowserActionType(Enum):
    OPEN_BROWSER = "OPEN_BROWSER"
    NAVIGATE_URL = "NAVIGATE_URL"
    SEARCH_WEB = "SEARCH_WEB"
    READ_PAGE = "READ_PAGE"
    SUMMARIZE_TOPIC = "SUMMARIZE_TOPIC"


@dataclass
class SearchResult:
    """Structured online search result item."""
    title: str
    snippet: str
    url: str


class CleanHTMLTextExtractor(HTMLParser):
    """Safe, lightweight HTML parser that extracts text while filtering scripts and styles."""

    def __init__(self):
        super().__init__()
        self.title: str = ""
        self._in_title = False
        self._ignore = False
        self._text_parts: List[str] = []

    def handle_starttag(self, tag, attrs):
        tag_lower = tag.lower()
        if tag_lower in ("script", "style", "noscript", "svg", "nav", "footer", "header"):
            self._ignore = True
        elif tag_lower == "title":
            self._in_title = True

    def handle_endtag(self, tag):
        tag_lower = tag.lower()
        if tag_lower in ("script", "style", "noscript", "svg", "nav", "footer", "header"):
            self._ignore = False
        elif tag_lower == "title":
            self._in_title = False
        elif tag_lower in ("p", "div", "h1", "h2", "h3", "h4", "li", "br"):
            self._text_parts.append("\n")

    def handle_data(self, data):
        if self._in_title:
            self.title += data.strip()
        elif not self._ignore:
            cleaned = data.strip()
            if cleaned:
                self._text_parts.append(cleaned)

    def get_text(self) -> str:
        raw = " ".join(self._text_parts)
        # Normalize multiple newlines and spaces
        raw = re.sub(r"[ \t]+", " ", raw)
        raw = re.sub(r"\n\s*\n+", "\n\n", raw)
        return raw.strip()


def search_web(query: str, language: str = "id", max_results: int = 3) -> List[SearchResult]:
    """Performs online knowledge search and returns structured search results with URLs."""
    results: List[SearchResult] = []
    clean_q = query.strip()
    if not clean_q:
        return results

    lang_code = "id" if language.lower().startswith("id") else "en"

    # Primary keyless provider: Wikipedia OpenSearch & Summary API
    try:
        url = f"https://{lang_code}.wikipedia.org/w/api.php"
        params = {
            "action": "opensearch",
            "search": clean_q,
            "limit": max_results,
            "namespace": 0,
            "format": "json",
        }
        resp = requests.get(url, params=params, headers={"User-Agent": USER_AGENT}, timeout=6)
        if resp.status_code == 200:
            data = resp.json()
            titles = data[1] if len(data) > 1 else []
            snippets = data[2] if len(data) > 2 else []
            links = data[3] if len(data) > 3 else []
            for t, s, l in zip(titles, snippets, links):
                results.append(SearchResult(title=t, snippet=s, url=l))
    except Exception as e:
        logger.warning("Error performing Wikipedia search for %r: %s", clean_q, e)

    # Fallback to English Wikipedia if Indonesian returned 0 results
    if not results and lang_code == "id":
        try:
            url_en = "https://en.wikipedia.org/w/api.php"
            params_en = {
                "action": "opensearch",
                "search": clean_q,
                "limit": max_results,
                "namespace": 0,
                "format": "json",
            }
            resp_en = requests.get(url_en, params=params_en, headers={"User-Agent": USER_AGENT}, timeout=6)
            if resp_en.status_code == 200:
                data_en = resp_en.json()
                titles = data_en[1] if len(data_en) > 1 else []
                snippets = data_en[2] if len(data_en) > 2 else []
                links = data_en[3] if len(data_en) > 3 else []
                for t, s, l in zip(titles, snippets, links):
                    results.append(SearchResult(title=t, snippet=s, url=l))
        except Exception as e:
            logger.warning("Error performing fallback English search for %r: %s", clean_q, e)

    return results


def read_web_page(url: str, max_chars: int = 3000) -> Tuple[bool, str, str]:
    """Fetches readable text from a URL, extracting title and content while sanitizing scripts.

    Returns:
        (success, title, content_text)
    """
    if not url.startswith(("http://", "https://")):
        return False, "", "URL tidak valid. Harus diawali dengan http:// atau https://"

    try:
        resp = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=8)
        resp.raise_for_status()
        html = resp.text

        parser = CleanHTMLTextExtractor()
        parser.feed(html)
        title = parser.title or url
        content = parser.get_text()[:max_chars]

        logger.info("Successfully read page '%s' (%d chars)", title, len(content))
        return True, title, content
    except Exception as e:
        logger.error("Error reading web page %s: %s", url, e)
        return False, "", f"Gagal membaca halaman web: {e}"


def summarize_topic(
    query: str,
    language: str = "id",
    lang: Optional[str] = None,
) -> Tuple[str, str]:
    """Answers/summarizes a query by fetching verified online sources.

    Returns:
        Tuple of (summary_text, source_url). Empty strings if not found.
    """
    clean_q = query.strip()
    effective_lang = lang or language
    is_id = effective_lang.lower().startswith("id")
    lang_code = "id" if is_id else "en"

    # Step 1: Direct encyclopedia summary lookup
    try:
        encoded = urllib.parse.quote(clean_q)
        summary_url = f"https://{lang_code}.wikipedia.org/api/rest_v1/page/summary/{encoded}"
        resp = requests.get(summary_url, headers={"User-Agent": USER_AGENT}, timeout=6)
        if resp.status_code == 200:
            data = resp.json()
            extract = data.get("extract", "")
            page_url = data.get("content_urls", {}).get("desktop", {}).get("page", "")
            if extract:
                return extract, (page_url or "")
    except Exception as e:
        logger.debug("Direct summary lookup error for %s: %s", clean_q, e)

    # Step 2: Search and read top result
    search_items = search_web(clean_q, language=effective_lang, max_results=3)
    if search_items:
        top_item = search_items[0]
        # Try fetching summary for top title
        try:
            encoded_top = urllib.parse.quote(top_item.title)
            summary_url = f"https://{lang_code}.wikipedia.org/api/rest_v1/page/summary/{encoded_top}"
            resp = requests.get(summary_url, headers={"User-Agent": USER_AGENT}, timeout=6)
            if resp.status_code == 200:
                data = resp.json()
                extract = data.get("extract", "")
                if extract:
                    return extract, top_item.url
        except Exception:
            pass

        # Return snippet if summary unavailable
        if top_item.snippet:
            return f"{top_item.title}: {top_item.snippet}", top_item.url
        else:
            return f"Topik terkait: {top_item.title}", top_item.url

    return "", ""



def open_search_in_browser(query: str) -> Tuple[bool, str]:
    """Opens Google search for the query in Chrome or default browser."""
    encoded = urllib.parse.quote(query.strip())
    search_url = f"https://www.google.com/search?q={encoded}"
    success, display_name, url_opened, msg = launch_website(search_url)
    if success:
        logger.info("Opened Google search for %r in browser", query)
        return True, f"Membuka pencarian Google untuk '{query}', sir."

    else:
        return False, f"Gagal membuka browser untuk pencarian: {msg}"
