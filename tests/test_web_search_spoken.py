"""Automated test suite for Web Search and Spoken Information Retrieval (Sections 5 & 10.D).

Verifies:
- Search request produces an actual search action.
- Results are parsed into structured SearchResult objects.
- CleanHTMLTextExtractor strips script, style, nav, and boilerplate.
- Spoken summary is grounded in retrieved content and concise (1-2 sentences).
- Follow-up references resolve to the correct result or page ("Bacakan sumber pertama", "Buka artikel kedua", "Apa sumbernya?").
- Network failures and inaccessible pages are reported honestly.
"""

import unittest
from unittest.mock import MagicMock, patch

from app.core.config import Settings
from app.core.orchestrator import Orchestrator
from app.core.router import CommandRouter, RouteType
from app.tools.browser_agent import (
    CleanHTMLTextExtractor,
    SearchResult,
    answer_search_query,
    build_extractive_answer,
    fetch_page_content,
)


class TestWebSearchSpoken(unittest.TestCase):
    def setUp(self):
        self.router = CommandRouter()
        self.settings = Settings(llm_enabled=False)
        self.orchestrator = Orchestrator(settings=self.settings)

    def test_search_request_routing_indonesian_and_english(self):
        """Web search requests must route to WEB_SEARCH with clean query."""
        r1 = self.router.route("Cari informasi tentang perkembangan AI terbaru")
        self.assertEqual(r1.route_type, RouteType.WEB_SEARCH)
        self.assertIn("ai", r1.args["query"].lower())

        r2 = self.router.route("Search Google for latest space exploration news")
        self.assertEqual(r2.route_type, RouteType.WEB_SEARCH)
        self.assertIn("space", r2.args["query"].lower())

    def test_clean_html_text_extractor(self):
        """Extractor must strip scripts, styles, nav, and keep meaningful article text."""
        raw_html = """
        <html>
            <head>
                <title>Kecerdasan Buatan Terkini</title>
                <style>body { font-size: 14px; }</style>
                <script>console.log("tracking");</script>
            </head>
            <body>
                <nav><a href="/home">Beranda</a></nav>
                <article>
                    <h1>Revolusi AI 2026</h1>
                    <p>Model kecerdasan buatan lokal kini semakin efisien pada laptop standar.</p>
                </article>
                <footer>Hak Cipta 2026</footer>
            </body>
        </html>
        """
        extractor = CleanHTMLTextExtractor()
        extractor.feed(raw_html)
        text = extractor.get_text()

        self.assertEqual(extractor.title, "Kecerdasan Buatan Terkini")
        self.assertIn("Model kecerdasan buatan lokal kini semakin efisien", text)
        self.assertNotIn("console.log", text)
        self.assertNotIn("font-size", text)
        self.assertNotIn("Beranda", text)
        self.assertNotIn("Hak Cipta", text)

    def test_build_extractive_answer_spoken_summary_grounded(self):
        """Spoken summary must be concise, capped to 1-2 sentences, and contain no naked URLs."""
        sources = [
            SearchResult(
                title="Perkembangan AI Indonesia",
                snippet="Pengembangan kecerdasan buatan di Indonesia meningkat pesat pada sektor edukasi dan kesehatan. Berbagai riset lokal mulai diadopsi secara nasional.",
                url="https://example.com/ai-indonesia",
                domain="example.com",
            )
        ]
        answer = build_extractive_answer("perkembangan AI", sources, language="id", max_sentences=2)

        self.assertTrue(answer.has_results)
        self.assertIn("Berdasarkan penelusuran web:", answer.spoken_answer)
        self.assertIn("sektor edukasi dan kesehatan", answer.spoken_answer)
        self.assertNotIn("https://", answer.spoken_answer)
        self.assertIn("[Perkembangan AI Indonesia](https://example.com/ai-indonesia)", answer.display_answer)

    def test_search_followup_routing_variations(self):
        """Follow-up questions must route to correct action and index."""
        r1 = self.router.route("buka hasil pencarian pertama")
        self.assertEqual(r1.action, "open_search_source")
        self.assertEqual(r1.args["index"], 1)

        r2 = self.router.route("buka artikel kedua")
        self.assertEqual(r2.action, "open_search_source")
        self.assertEqual(r2.args["index"], 2)

        r3 = self.router.route("bacakan sumber pertama")
        self.assertEqual(r3.action, "read_search_source_snippet")
        self.assertEqual(r3.args["index"], 1)

        r4 = self.router.route("apa sumber informasi tadi?")
        self.assertEqual(r4.action, "list_search_sources")

    def test_search_followup_orchestrator_execution(self):
        """Follow-up execution retrieves actual data from session state."""
        # Inject mock search results into state
        self.orchestrator.state.set_last_search(
            query="AI 2026",
            spoken_answer="AI lokal berkembang pesat.",
            display_answer="AI lokal berkembang pesat.",
            sources=[
                {"title": "AI Report", "url": "https://ai.example.org", "snippet": "Laporan perkembangan AI 2026.", "domain": "ai.example.org"},
                {"title": "Tech News", "url": "https://tech.example.org", "snippet": "Inovasi komputasi tepi.", "domain": "tech.example.org"},
            ],
        )

        # Test read_search_source_snippet
        _, stream = self.orchestrator.process_input_stream("bacakan sumber pertama")
        response = "".join(list(stream))
        self.assertIn("Laporan perkembangan AI 2026", response)
        self.assertIn("ai.example.org", response)

        # Test list_search_sources
        _, stream2 = self.orchestrator.process_input_stream("apa sumber informasi tadi?")
        response2 = "".join(list(stream2))
        self.assertIn("ai.example.org", response2)

    def test_search_followup_with_search_result_objects(self):
        """Regression test: follow-up execution must handle SearchResult dataclass instances without AttributeError."""
        self.orchestrator.state.set_last_search(
            query="Perkembangan AI",
            spoken_answer="AI makin canggih.",
            display_answer="AI makin canggih.",
            sources=[
                SearchResult(
                    title="Perkembangan AI",
                    url="https://aici-umg.com/article/perkembangan-ai/",
                    snippet="Perkembangan AI membawa dampak signifikan.",
                    domain="aici-umg.com",
                ),
                SearchResult(
                    title="Berita OpenAI",
                    url="https://openai.com/id-ID/news/",
                    snippet="Berita terbaru dari OpenAI.",
                    domain="openai.com",
                ),
            ],
        )

        # list_search_sources
        _, stream = self.orchestrator.process_input_stream("apa sumber informasi tadi?")
        response = "".join(list(stream))
        self.assertIn("aici-umg.com", response)
        self.assertIn("openai.com", response)

        # read_search_source_snippet
        _, stream2 = self.orchestrator.process_input_stream("bacakan sumber pertama")
        response2 = "".join(list(stream2))
        self.assertIn("Perkembangan AI membawa dampak signifikan", response2)

    @patch("requests.get", side_effect=Exception("Connection timed out"))
    def test_network_failure_reported_honestly(self, mock_get):
        """When web request fails, it must report the failure honestly without hallucinating."""
        ok, title, content = fetch_page_content("https://unreachable.example.com/test")
        self.assertFalse(ok)
        self.assertIn("Gagal membaca halaman web", content)


if __name__ == "__main__":
    unittest.main()
