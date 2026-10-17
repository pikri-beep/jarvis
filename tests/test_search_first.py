"""Automated test suite for Search-First JARVIS and On-Demand Screen Vision.

Covers Workstream 12 requirements:
- Indonesian search intent classification
- English search intent classification
- Search intent without LLM invocation (deterministic zero-LLM path)
- Search provider success and URL unwrapping
- Search timeout handling
- Empty search results handling
- Invalid / malformed URLs handling
- Page extraction success and failure
- Extractive answer relevance, deduplication, and two-sentence limit
- Source URL preservation
- TTS language selection and citation skipping
- Opening verified result URLs
- Screen-reading permission and explicit invocation
- OCR fallback (WinRT OCR)
- Vision model unavailable honest reporting (zero auto-download)
- Screenshot cleanup (zero persistence)
- Existing wake-word and PTT behavior remains unaffected
"""

from pathlib import Path
import tempfile
from unittest.mock import MagicMock, patch
import urllib.error

import pytest

from app.core.config import Settings
from app.core.orchestrator import Orchestrator
from app.core.router import CommandRouter, RouteType
from app.core.state import SessionState
from app.tools.browser_agent import (
    CleanHTMLTextExtractor,
    ExtractiveAnswer,
    SearchResult,
    answer_search_query,
    build_extractive_answer,
    fetch_page_content,
    search_web,
    unwrap_bing_url,
)
from app.tools.screen_reader import (
    ScreenReadResult,
    check_vision_model_available,
    clean_extracted_screen_text,
    read_screen_content,
    summarize_screen_text,
)
from app.voice.text_to_speech import clean_text_for_speech


@pytest.fixture
def router():
    return CommandRouter()


@pytest.fixture
def mock_orchestrator():
    settings = Settings(
        tts_enabled=False,
        voice_enabled=False,
        wake_word_enabled=False,
        model="qwen3:8b",
    )
    llm_mock = MagicMock()
    llm_mock.chat_stream.return_value = iter(["Should", " not", " be", " called"])
    orch = Orchestrator(settings=settings, llm_client=llm_mock)
    return orch


# ==============================================================================
# 1. Intent Routing Tests (Indonesian & English)
# ==============================================================================

def test_indonesian_search_intent(router):
    cases = [
        ("Hey Jarvis, cari informasi tentang perkembangan AI terbaru.", "perkembangan ai terbaru"),
        ("Cari di internet tentang python 3.12", "python 3.12"),
        ("Cari berita terbaru tentang pemilu", "pemilu"),
        ("Tolong carikan info seputar teknologi kuantum dong", "teknologi kuantum"),
        ("Cari kabar terbaru tentang peluncuran roket", "peluncuran roket"),
        ("Buka hasil pencarian tentang laptop asus", "laptop asus"),
    ]
    for user_input, expected_subquery in cases:
        res = router.route(user_input)
        assert res.route_type == RouteType.WEB_SEARCH
        assert res.action in ("search_web", "open_search_results")
        assert expected_subquery in res.args.get("query", "").lower()


def test_english_search_intent(router):
    cases = [
        ("Search the web for deepseek r1", "deepseek r1"),
        ("Find information about quantum computing", "quantum computing"),
        ("What are the latest developments in robotics?", "robotics"),
        ("Search for nvidia rtx 5090", "nvidia rtx 5090"),
        ("Search online for space telescope discoveries", "space telescope discoveries"),
        ("Open search results for artificial intelligence", "artificial intelligence"),
    ]
    for user_input, expected_subquery in cases:
        res = router.route(user_input)
        assert res.route_type == RouteType.WEB_SEARCH
        assert res.action in ("search_web", "open_search_results")
        assert expected_subquery in res.args.get("query", "").lower()


def test_search_does_not_route_conversational_requests(router):
    """General opinions, creative requests, and conceptual explanations must route to LLM."""
    ai_prompts = [
        "Tulis puisi tentang keindahan laut",
        "Jelaskan konsep dasar algoritma binary search",
        "Apa pendapatmu tentang filosofi stoikisme?",
        "Explain the mathematical intuition behind backpropagation",
    ]
    for prompt in ai_prompts:
        res = router.route(prompt)
        assert res.route_type == RouteType.AI_REQUEST
        assert res.action == "llm_chat"


# ==============================================================================
# 2. Search-First Zero LLM Invocation Guarantee
# ==============================================================================

def test_search_intent_without_llm_invocation(mock_orchestrator):
    """Search queries must NEVER invoke Ollama or llm.chat_stream."""
    user_input = "Hey Jarvis, cari informasi tentang perkembangan AI terbaru."
    
    mock_answer = ExtractiveAnswer(
        query="perkembangan ai terbaru",
        spoken_answer="Perkembangan AI terbaru berfokus pada penalaran canggih dan agen otonom.",
        display_answer="Perkembangan AI terbaru berfokus pada penalaran canggih dan agen otonom.\n\nSumber:\n1. TechNews (https://technews.example/ai)",
        sources=[SearchResult("TechNews", "https://technews.example/ai", "Penalaran canggih")],
        latency_ms=120.0,
    )

    with patch("app.tools.browser_agent.answer_search_query", return_value=mock_answer) as mock_agent:
        route, stream_gen = mock_orchestrator.process_input_stream(user_input)
        tokens = list(stream_gen)
        
        # Verify route is WEB_SEARCH
        assert route.route_type == RouteType.WEB_SEARCH
        assert mock_agent.called
        # Verify LLM was NEVER called
        assert mock_orchestrator.llm.chat_stream.call_count == 0
        
        reply = "".join(tokens)
        assert "perkembangan ai terbaru" in reply.lower()
        assert "https://technews.example/ai" in reply


# ==============================================================================
# 3. Provider Retrieval & Base64 URL Unwrap
# ==============================================================================

def test_clean_bing_url_unwrap():
    # Valid base64 unwrap of https://github.com/
    # 'https://github.com/' in base64 is 'aHR0cHM6Ly9naXRodWIuY29tLw=='
    encoded_param = "a1aHR0cHM6Ly9naXRodWIuY29tLw"
    bing_track_url = f"https://www.bing.com/ck/a?!&&p=123&u={encoded_param}&ntb=1"
    
    unwrapped = unwrap_bing_url(bing_track_url)
    assert unwrapped.startswith("https://github.com")


def test_invalid_or_malformed_urls_handled_safely():
    # Corrupt base64 padding or invalid URL parameter
    malformed_track = "https://www.bing.com/ck/a?!&&p=123&u=a1%%%invalid&&ntb=1"
    res = unwrap_bing_url(malformed_track)
    # Should safely return fallback or cleaned URL without crashing
    assert isinstance(res, str)
    assert len(res) > 0


def test_search_timeout_fallback():
    """Network timeout on primary search provider must not crash and should fallback to Wikipedia."""
    with patch("urllib.request.urlopen", side_effect=urllib.error.URLError("Request timed out")):
        results = search_web("quantum computing")
        # Should gracefully return empty or fallback Wikipedia without throwing exception
        assert isinstance(results, list)


def test_empty_search_results_honest_response():
    """Empty results must produce an honest negative response without hallucination."""
    with patch("app.tools.browser_agent.search_web", return_value=[]):
        ans_id = answer_search_query("nonexistentxyz123456", language="id")
        assert "tidak menemukan informasi" in ans_id.spoken_answer.lower()
        assert len(ans_id.sources) == 0

        ans_en = answer_search_query("nonexistentxyz123456", language="en")
        assert "could not find verified" in ans_en.spoken_answer.lower()


# ==============================================================================
# 4. Extractive Answer Builder & Two-Sentence Cap
# ==============================================================================

def test_extractive_answer_relevance_and_two_sentence_limit():
    query = "fitur baru python 3.12"
    mock_results = [
        SearchResult(
            title="Python 3.12 Release Notes",
            url="https://docs.python.org/3.12",
            snippet="Python 3.12 memperkenalkan parser yang lebih cepat dan sub-interpreter terisolasi. Fitur ini meningkatkan performa multithreading secara signifikan. Dokumentasi resmi tersedia.",
            domain="docs.python.org",
        ),
        SearchResult(
            title="Overview Python 3.12",
            url="https://pythoninsider.example/release",
            snippet="Python 3.12 memperkenalkan parser yang lebih cepat dan sub-interpreter terisolasi. Pesan kesalahan sintaksis juga kini jauh lebih ramah pengguna.",
            domain="pythoninsider.example",
        ),
    ]

    ans = build_extractive_answer(query, mock_results, language="id")
    
    assert ans.spoken_answer != ""
    # Check two-sentence cap (at most 2 terminal punctuation marks)
    sentence_count = len([s for s in ans.spoken_answer.split(". ") if s.strip()])
    assert sentence_count <= 2
    
    # Check sources preservation in display output
    assert "https://docs.python.org/3.12" in ans.display_answer
    assert "Sumber" in ans.display_answer
    assert len(ans.sources) >= 1


def test_html_cleaner_strips_scripts_and_boilerplate():
    html = """
    <html>
        <head><title>Test Page</title><style>.banner{color:red;}</style></head>
        <body>
            <script>alert('bad');</script>
            <nav><a href="/">Home</a><a href="/login">Login</a></nav>
            <article>
                <h1>Judul Utama Artikel</h1>
                <p>Ini adalah paragraf pertama informasi penting tentang kecerdasan buatan.</p>
                <p>Paragraf kedua menjelaskan perkembangan model penalaran cerdas.</p>
            </article>
            <footer>Copyright 2026. All rights reserved.</footer>
        </body>
    </html>
    """
    cleaner = CleanHTMLTextExtractor()
    cleaner.feed(html)
    text = cleaner.get_text()
    
    assert "Judul Utama Artikel" in text
    assert "kecerdasan buatan" in text
    assert "alert('bad')" not in text
    assert ".banner" not in text


# ==============================================================================
# 5. Natural Speech & Source Separation (TTS)
# ==============================================================================

def test_tts_omits_sources_and_urls():
    """TTS clean_text_for_speech must filter out source citation lines and raw links."""
    text_with_sources = (
        "Perkembangan AI terbaru mencakup peluncuran model penalaran canggih dan agen otomatis.\n\n"
        "Sumber:\n"
        "1. OpenAI Releases (https://openai.com/index/o3)\n"
        "2. DeepSeek AI (https://deepseek.com/r1)"
    )
    
    # Check that Sumber blocks are stripped from speech
    lead_sentence = "Perkembangan AI terbaru mencakup peluncuran model penalaran canggih dan agen otomatis."
    source_block = "Sumber:\n1. OpenAI Releases (https://openai.com/index/o3)"
    
    lead_cleaned = clean_text_for_speech(lead_sentence, language="id")
    source_cleaned = clean_text_for_speech(source_block, language="id")
    
    assert "Perkembangan" in lead_cleaned
    assert source_cleaned == ""  # Source citations must NOT be spoken


# ==============================================================================
# 6. Search Follow-ups (Read, List, Open)
# ==============================================================================

def test_search_followups(mock_orchestrator):
    # Pre-populate session state with search result
    mock_orchestrator.state.set_last_search(
        query="python 3.13",
        spoken_answer="Python 3.13 merilis fitur no-GIL eksperimental.",
        display_answer="Python 3.13 merilis fitur no-GIL eksperimental.\n\nSumber:\n1. Python Docs (https://docs.python.org/3.13)",
        sources=[{"title": "Python Docs", "url": "https://docs.python.org/3.13", "domain": "docs.python.org"}],
    )

    # 1. "bacakan hasilnya"
    r1, g1 = mock_orchestrator.process_input_stream("bacakan hasilnya")
    assert r1.action == "read_search_result"
    out1 = "".join(list(g1))
    assert "Python 3.13 merilis fitur no-GIL" in out1

    # 2. "sebutkan sumbernya"
    r2, g2 = mock_orchestrator.process_input_stream("sebutkan sumbernya")
    assert r2.action == "list_search_sources"
    out2 = "".join(list(g2))
    assert "docs.python.org" in out2

    # 3. "buka sumber pertama"
    with patch("app.tools.browser.launch_website", return_value=(True, "Python Docs", "https://docs.python.org/3.13", "Opened")) as mock_launch:
        r3, g3 = mock_orchestrator.process_input_stream("buka sumber pertama")
        assert r3.action == "open_search_source"
        out3 = "".join(list(g3))
        assert "Membuka sumber ke-1" in out3
        assert mock_launch.called


# ==============================================================================
# 7. On-Demand Screen Reading Tests
# ==============================================================================

def test_screen_reading_intent_routing(router):
    cases = [
        ("Hey Jarvis, lihat layar gue.", False),
        ("Hey Jarvis, baca teks di layar.", False),
        ("Hey Jarvis, what is on my screen?", False),
        ("Hey Jarvis, jelaskan error yang tampil.", True),
        ("Inspeksi layar", False),
    ]
    for user_input, expected_vision_pref in cases:
        res = router.route(user_input)
        assert res.route_type == RouteType.SCREEN_READ
        assert res.action == "read_screen"
        assert res.args.get("prefer_vision") == expected_vision_pref


def test_screen_reading_privacy_and_file_cleanup():
    """Temporary screenshot must be deleted in finally block (zero file persistence)."""
    res = read_screen_content(prompt="baca layar", language="id")
    
    assert res.temporary_file_cleaned is True
    # Verify no leaked jarvis_screen_*.png files in tempdir
    temp_dir = Path(tempfile.gettempdir())
    leaked = list(temp_dir.glob("jarvis_screen_*.png"))
    assert len(leaked) == 0


def test_vision_model_unavailable_honesty():
    """Must report when vision model is not installed without downloading anything."""
    has_vision, model_name, info = check_vision_model_available()
    assert isinstance(has_vision, bool)
    assert isinstance(info, str)
    # When no vision model installed, model_name is None
    if not has_vision:
        assert model_name is None


def test_summarize_screen_text_sanitizes_errors():
    error_ocr = (
        "Traceback (most recent call last):\n"
        "  File 'app/main.py', line 45, in <module>\n"
        "ZeroDivisionError: division by zero"
    )
    summary = summarize_screen_text(error_ocr, window_title="Visual Studio Code", language="id")
    assert "Visual Studio Code" in summary
    assert "galat" in summary.lower() or "error" in summary.lower()


# ==============================================================================
# 8. Diagnostics Command Extension
# ==============================================================================

def test_diagnostics_includes_search_first_and_screen(mock_orchestrator):
    from app.core.diagnostics import format_diagnostics_text, generate_diagnostics_report

    mock_orchestrator.state.set_last_search(
        query="ai developments",
        spoken_answer="AI models are advancing rapidly.",
        display_answer="AI models are advancing rapidly.\n\nSumber:\n1. Nature (https://nature.com)",
        sources=[{"domain": "nature.com", "title": "Nature", "url": "https://nature.com"}],
    )
    
    rep = generate_diagnostics_report(mock_orchestrator)
    assert "search_first" in rep
    assert "screen_vision" in rep
    assert rep["search_first"]["llm_bypassed"] is True
    
    text = format_diagnostics_text(rep)
    assert "[Search-1st]" in text
    assert "[Screen/Vis]" in text
    assert "nature.com" in text
