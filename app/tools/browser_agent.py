"""Autonomous web browsing, search, and extractive answer intelligence for JARVIS.

Follows Workstream A, B, C, D, and F requirements:
- Search-First without invoking LLM (extractive sentence ranking, deduplication, 1-2 sentence spoken cap).
- Real web search across the internet (with real URL unwrapping, domains, clean snippets) + Wikipedia fallback.
- Strictly separates spoken text (concise, no URLs) from display text (full citations & markdown links).
- Supports search follow-ups ("bacakan hasilnya", "sebutkan sumbernya", "buka sumber pertama").
- Page reading with script, style, and navigation stripping.
- Preserves Chrome profiles and user privacy (zero external credential/cookie access).
"""

import base64
import html
import re
import time
import urllib.parse
from dataclasses import dataclass, field
from enum import Enum
from html.parser import HTMLParser
from typing import Any, Dict, List, Optional, Tuple

import requests

from app.core.logger import setup_logger
from app.tools.browser import launch_website

logger = setup_logger("jarvis.tools.browser_agent")

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)


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
    domain: str = ""
    source_type: str = "web"
    date: str = ""


@dataclass
class ExtractiveAnswer:
    """Structured result of Search-First extractive synthesis without LLM."""
    query: str
    spoken_answer: str
    display_answer: str
    sources: List[SearchResult] = field(default_factory=list)
    confidence: float = 1.0
    latency_ms: float = 0.0
    has_results: bool = True


class CleanHTMLTextExtractor(HTMLParser):
    """Safe, lightweight HTML parser that extracts readable text while filtering scripts and styles."""

    def __init__(self):
        super().__init__()
        self.title: str = ""
        self._in_title = False
        self._ignore = False
        self._text_parts: List[str] = []

    def handle_starttag(self, tag, attrs):
        tag_lower = tag.lower()
        if tag_lower in ("script", "style", "noscript", "svg", "nav", "footer", "header", "aside"):
            self._ignore = True
        elif tag_lower == "title":
            self._in_title = True

    def handle_endtag(self, tag):
        tag_lower = tag.lower()
        if tag_lower in ("script", "style", "noscript", "svg", "nav", "footer", "header", "aside"):
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


def extract_domain(url: str) -> str:
    """Extracts clean host domain from a URL."""
    try:
        parsed = urllib.parse.urlparse(url)
        netloc = parsed.netloc.lower()
        if netloc.startswith("www."):
            netloc = netloc[4:]
        return netloc or url
    except Exception:
        return ""


def unwrap_bing_url(url: str) -> str:
    """Decodes Bing redirect tracking URL to retrieve the actual destination URL."""
    m = re.search(r"[?&]u=a1([a-zA-Z0-9_\-]+)", url)
    if m:
        b64 = m.group(1).replace("-", "+").replace("_", "/")
        b64 += "=" * ((4 - len(b64) % 4) % 4)
        try:
            decoded = base64.b64decode(b64).decode("utf-8", errors="ignore")
            if decoded.startswith(("http://", "https://")):
                return decoded
        except Exception:
            pass
    return url


def search_web(
    query: str,
    language: str = "id",
    max_results: int = 5,
) -> List[SearchResult]:
    """Performs real web search across the internet, returning structured SearchResult items.

    Primary: General web search engine.
    Secondary / Fallback: Wikipedia OpenSearch & Summary API.
    """
    clean_q = query.strip()
    if not clean_q:
        return []

    results: List[SearchResult] = []
    seen_urls = set()

    # Provider A: General Live Web Search (Bing endpoint with unwrapped URLs)
    try:
        headers = {
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "id,en;q=0.9" if language.lower().startswith("id") else "en,id;q=0.8",
        }
        resp = requests.get(
            "https://www.bing.com/search",
            params={"q": clean_q},
            headers=headers,
            timeout=5,
        )
        if resp.status_code == 200:
            blocks = re.findall(r'<li class="b_algo"[\s\S]*?</li>', resp.text)
            for b in blocks:
                m_h2 = re.search(r'<h2>\s*<a\s+[^>]*href="([^"]+)"[^>]*>([\s\S]*?)</a>\s*</h2>', b)
                m_p = re.search(r'<div class="b_caption">[\s\S]*?<p[^>]*>([\s\S]*?)</p>', b)
                if m_h2:
                    raw_url = html.unescape(m_h2.group(1))
                    real_url = unwrap_bing_url(raw_url)
                    if real_url in seen_urls:
                        continue
                    seen_urls.add(real_url)

                    title = html.unescape(re.sub(r"<[^>]+>", "", m_h2.group(2))).strip()
                    snip = ""
                    if m_p:
                        # Clean date stamp prefixes like "Nov 24, 2025 · " or "3 days ago · "
                        raw_snip = html.unescape(re.sub(r"<[^>]+>", "", m_p.group(1))).strip()
                        raw_snip = re.sub(r"^[A-Z][a-z]{2}\s+\d{1,2},\s+\d{4}\s*[\·\-\–\—\•]\s*", "", raw_snip)
                        raw_snip = re.sub(r"^\d+\s+(?:days?|hours?|mins?|hari|jam|menit)\s+ago\s*[\·\-\–\—\•]\s*", "", raw_snip, flags=re.IGNORECASE)
                        snip = raw_snip

                    domain = extract_domain(real_url)
                    results.append(SearchResult(
                        title=title,
                        snippet=snip,
                        url=real_url,
                        domain=domain,
                        source_type="web",
                    ))
                    if len(results) >= max_results:
                        break
    except Exception as e:
        logger.debug("Live web search error for %r: %s", clean_q, e)

    # Provider B: Wikipedia OpenSearch API (Factual encyclopedic backing)
    lang_code = "id" if language.lower().startswith("id") else "en"
    try:
        wiki_url = f"https://{lang_code}.wikipedia.org/w/api.php"
        params = {
            "action": "opensearch",
            "search": clean_q,
            "limit": 3,
            "namespace": 0,
            "format": "json",
        }
        w_resp = requests.get(wiki_url, params=params, headers={"User-Agent": USER_AGENT}, timeout=4)
        if w_resp.status_code == 200:
            w_data = w_resp.json()
            titles = w_data[1] if len(w_data) > 1 else []
            snippets = w_data[2] if len(w_data) > 2 else []
            links = w_data[3] if len(w_data) > 3 else []
            for t, s, l in zip(titles, snippets, links):
                if l and l not in seen_urls:
                    seen_urls.add(l)
                    results.append(SearchResult(
                        title=t,
                        snippet=s,
                        url=l,
                        domain=f"{lang_code}.wikipedia.org",
                        source_type="encyclopedia",
                    ))
    except Exception as e:
        logger.debug("Wikipedia search error for %r: %s", clean_q, e)

    return results


def fetch_page_content(url: str, max_chars: int = 3000) -> Tuple[bool, str, str]:
    """Fetches readable text from a URL, extracting title and content while sanitizing scripts.

    Returns:
        Tuple of (success, title, content_text)
    """
    if not url.startswith(("http://", "https://")):
        return False, "", "URL tidak valid. Harus diawali dengan http:// atau https://"

    try:
        resp = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=6)
        resp.raise_for_status()
        parser = CleanHTMLTextExtractor()
        parser.feed(resp.text)
        title = parser.title or url
        content = parser.get_text()[:max_chars]
        logger.info("Successfully read page '%s' (%d chars)", title, len(content))
        return True, title, content
    except Exception as e:
        logger.error("Error reading web page %s: %s", url, e)
        return False, "", f"Gagal membaca halaman web: {e}"


read_web_page = fetch_page_content


def _split_into_sentences(text: str) -> List[str]:
    """Splits text into clean individual sentences."""
    if not text:
        return []
    # Replace newlines with spaces
    t = re.sub(r"\s+", " ", text).strip()
    # Split on sentence boundaries
    raw_sents = re.split(r"(?<=[.!?])\s+", t)
    cleaned = []
    for s in raw_sents:
        s_clean = s.strip()
        # Filter very short fragments or ellipsis
        if len(s_clean) >= 15 and not s_clean.startswith("...") and not s_clean.endswith("..."):
            cleaned.append(s_clean)
        elif len(s_clean) >= 20:
            cleaned.append(s_clean.rstrip(". ") + ".")
    return cleaned


def _score_sentence(sentence: str, query_tokens: set) -> float:
    """Scores sentence relevance based on query keywords and informative density."""
    s_lower = sentence.lower()
    words = set(re.findall(r"\b[a-z0-9_]{3,}\b", s_lower))

    if not words:
        return 0.0

    match_count = len(words & query_tokens)
    if match_count == 0:
        return 0.0

    score = match_count * 2.5

    # Density bonus
    density = match_count / len(words)
    score += density * 3.0

    # Definitional / informative terms bonus
    info_markers = {
        "adalah", "merupakan", "meliputi", "terdiri", "adanya", "sebagai",
        "is", "are", "refers", "defined", "includes", "features", "developed", "introduced"
    }
    if words & info_markers:
        score += 1.5

    # Navigation / clickbait penalty
    penalties = {
        "baca", "selengkapnya", "klik", "disini", "subscribe", "halaman", "kumpulan",
        "read", "more", "click", "here", "copyright", "terms", "policy"
    }
    if words & penalties:
        score -= 2.0

    return score


def build_extractive_answer(
    query: str,
    search_results: List[SearchResult],
    language: str = "id",
    max_sentences: int = 2,
) -> ExtractiveAnswer:
    """Constructs a deterministic, source-grounded answer WITHOUT calling an LLM.

    - Ranks candidate sentences by query relevance and information density.
    - Eliminates duplicate or near-duplicate claims.
    - Limits spoken output to 1-2 complete sentences.
    - Stores source titles and URLs separately for display.
    """
    is_id = language.lower().startswith("id")

    if not search_results:
        msg = (
            "Maaf sir, saya tidak menemukan informasi terverifikasi di web untuk topik tersebut."
            if is_id
            else "I could not find verified online information for that query, sir."
        )
        return ExtractiveAnswer(
            query=query,
            spoken_answer=msg,
            display_answer=msg,
            sources=[],
            confidence=0.0,
            has_results=False,
        )

    # Tokenize query keywords (exclude common stop words)
    q_words = set(re.findall(r"\b[a-z0-9_]{3,}\b", query.lower()))
    stopwords = {
        "cari", "informasi", "tentang", "internet", "web", "terbaru", "dong", "tolong",
        "search", "what", "latest", "news", "updates", "info", "find", "online", "about"
    }
    salient_tokens = q_words - stopwords or q_words

    # Gather candidate sentences from all snippets
    candidates: List[Tuple[float, str, SearchResult]] = []
    for res in search_results:
        sents = _split_into_sentences(res.snippet)
        for s in sents:
            score = _score_sentence(s, salient_tokens)
            if score > 0:
                candidates.append((score, s, res))

    # Sort descending by score
    candidates.sort(key=lambda x: x[0], reverse=True)

    selected_sentences: List[str] = []
    selected_sources: List[SearchResult] = []
    seen_words_sets: List[set] = []

    for score, sentence, res in candidates:
        s_words = set(sentence.lower().split())
        # Deduplication check (Jaccard similarity < 0.5 with existing selections)
        is_duplicate = False
        for existing_set in seen_words_sets:
            overlap = len(s_words & existing_set) / max(1, len(s_words | existing_set))
            if overlap > 0.5:
                is_duplicate = True
                break

        if not is_duplicate:
            selected_sentences.append(sentence)
            if res not in selected_sources:
                selected_sources.append(res)
            seen_words_sets.append(s_words)

        if len(selected_sentences) >= max_sentences:
            break

    # If no high-confidence sentences found, use top result snippet directly
    if not selected_sentences and search_results:
        top = search_results[0]
        if top.snippet:
            top_sents = _split_into_sentences(top.snippet)
            selected_sentences = top_sents[:max_sentences]
            selected_sources = [top]
        else:
            selected_sentences = [f"Informasi ditemukan di {top.title}." if is_id else f"Information found at {top.title}."]
            selected_sources = [top]

    # Build spoken answer (1-2 sentences only, strictly NO URLs spoken aloud)
    spoken_body = " ".join(selected_sentences).strip()
    # Clean trailing ellipses
    spoken_body = re.sub(r"[\s\.\·\-\–\—\…]+$", "", spoken_body) + "."
    if is_id:
        spoken_answer = f"Berdasarkan penelusuran web: {spoken_body}"
    else:
        spoken_answer = f"According to web results: {spoken_body}"

    # Build display answer with clickable source citations and domains
    display_lines = [spoken_answer, "", "Sumber Terkait:"]
    for idx, src in enumerate(selected_sources[:3], 1):
        domain_tag = f" ({src.domain})" if src.domain else ""
        display_lines.append(f"{idx}. [{src.title}]({src.url}){domain_tag}")

    display_answer = "\n".join(display_lines)

    return ExtractiveAnswer(
        query=query,
        spoken_answer=spoken_answer,
        display_answer=display_answer,
        sources=selected_sources,
        confidence=0.9 if candidates else 0.6,
        has_results=True,
    )


def answer_search_query(query: str, language: str = "id") -> ExtractiveAnswer:
    """Top-level Search-First entrypoint: searches web and synthesizes extractive answer without LLM."""
    t0 = time.perf_counter()
    results = search_web(query, language=language, max_results=5)
    answer = build_extractive_answer(query, results, language=language, max_sentences=2)
    answer.latency_ms = (time.perf_counter() - t0) * 1000.0
    logger.info(
        '[SEARCH_FIRST] query="%s" results=%d latency=%.1fms confidence=%.2f',
        query, len(results), answer.latency_ms, answer.confidence
    )
    return answer


def summarize_topic(
    query: str,
    language: str = "id",
    lang: Optional[str] = None,
) -> Tuple[str, str]:
    """Compatibility method for existing tests and encyclopedia lookups."""
    effective_lang = lang or language
    answer = answer_search_query(query, language=effective_lang)
    if answer.sources:
        return answer.spoken_answer, answer.sources[0].url
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
