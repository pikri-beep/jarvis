"""Test suite for Universal Web Agent and Google Search integration.

Covers:
- Section 5: Primary Google Search (no Bing fallback, open search & top source tabs, Indonesian spoken summaries).
- Section 6: Web search error handling without tracebacks or hiding bugs.
- Section 7: Universal Web Agent adaptive capabilities across any website:
  - open_url, search_google, open_new_tab, close_tab, switch_tab, go_back, refresh.
  - observe_page, find_and_click, fill_input, scroll_page, read_page.
"""

import unittest
from unittest.mock import MagicMock, patch

from app.tools.browser_agent import SearchResult, unwrap_google_url
from app.tools.web_agent import UniversalWebAgent, WebAgentActionResult


class TestUniversalWebAgent(unittest.TestCase):
    def setUp(self):
        self.agent = UniversalWebAgent()

    def test_search_google_execution_mocked(self):
        """Verifies search_google opens Google Search and extracts top source."""
        mock_results = [
            SearchResult(
                title="Perkembangan AI Terbaru di Indonesia",
                snippet="Kecerdasan buatan berkembang pesat di berbagai sektor industri.",
                url="https://teknologi.bisnis.com/ai-terbaru",
                domain="teknologi.bisnis.com",
                source_type="google",
            ),
            SearchResult(
                title="Riset AI 2026",
                snippet="Laporan riset model LLM dan agen cerdas terkini.",
                url="https://kompas.id/riset-ai",
                domain="kompas.id",
                source_type="google",
            ),
        ]

        with patch("app.tools.web_agent.launch_website", return_value=(True, "Google", "https://google.com", "OK")) as mock_launch, \
             patch("app.tools.web_agent.search_web", return_value=mock_results) as mock_search, \
             patch("app.tools.web_agent.fetch_page_content", return_value=(True, "Perkembangan AI", "Artikel lengkap tentang AI.")) as mock_fetch:

            res = self.agent.search_google(
                query="perkembangan AI terbaru",
                language="id",
                open_browser=True,
                open_top_source=True,
            )

            self.assertTrue(res.success)
            self.assertEqual(res.action, "search_google")
            self.assertIn("perkembangan AI", res.message)
            self.assertTrue(res.verified)
            self.assertIn("sources", res.data)
            self.assertEqual(len(res.data["sources"]), 2)
            # Verify Google URL was launched
            self.assertTrue(mock_launch.called)
            first_url_called = mock_launch.call_args_list[0][0][0]
            self.assertIn("google.com/search", first_url_called)
            self.assertNotIn("bing.com", first_url_called)

    def test_search_google_opens_only_single_serp_tab(self):
        """Verifies default search_google opens exactly 1 tab (Google SERP) and does NOT open top source tab."""
        mock_results = [
            SearchResult(
                title="Google Result Title",
                snippet="Snippet explanation.",
                url="https://example.com/source1",
                domain="example.com",
                source_type="google",
            )
        ]
        with patch("app.tools.web_agent.launch_website", return_value=(True, "Google", "https://google.com", "OK")) as mock_launch, \
             patch("app.tools.web_agent.search_web", return_value=mock_results):

            res = self.agent.search_google(
                query="perkembangan AI",
                language="id",
                open_browser=True,
                open_top_source=False,
            )
            self.assertTrue(res.success)
            # Verify launch_website called exactly once for Google SERP
            self.assertEqual(mock_launch.call_count, 1)
            called_url = mock_launch.call_args_list[0][0][0]
            self.assertIn("google.com/search", called_url)
            self.assertNotIn("example.com", called_url)

    def test_search_google_empty_query_handled_safely(self):
        """Verifies empty query returns safe error without crashing."""
        res = self.agent.search_google("   ")
        self.assertFalse(res.success)
        self.assertIn("tidak boleh kosong", res.message)

    def test_open_url_success(self):
        """Verifies opening a target website."""
        with patch("app.tools.web_agent.launch_website", return_value=(True, "GitHub", "https://github.com", "OK")):
            res = self.agent.open_url("github.com", language="id")
            self.assertTrue(res.success)
            self.assertEqual(res.action, "open_url")
            self.assertEqual(res.target, "https://github.com")
            self.assertTrue(res.verified)

    def test_open_url_failure_handled(self):
        """Verifies failure to open URL returns informative message."""
        with patch("app.tools.web_agent.launch_website", return_value=(False, "badurl", "badurl", "Browser error")):
            res = self.agent.open_url("invalid_url", language="id")
            self.assertFalse(res.success)
            self.assertIn("Gagal", res.message)

    def test_find_and_click_via_uia(self):
        """Verifies finding an element via UIA and clicking."""
        mock_el = MagicMock()
        mock_el.name = "Masuk"
        mock_el.control_type = "Button"
        mock_el.center_x = 500
        mock_el.center_y = 200
        mock_el.automation_id = "login-btn"

        with patch("app.tools.web_agent.get_active_window_info", return_value={"hwnd": 1234, "title": "Portal Kampus"}), \
             patch("app.tools.web_agent.extract_uia_elements", return_value=[mock_el]), \
             patch("app.tools.web_agent.mouse_click") as mock_click:

            res = self.agent.find_and_click("Masuk", language="id")
            self.assertTrue(res.success)
            self.assertEqual(res.action, "click_element")
            self.assertTrue(mock_click.called)
            mock_click.assert_called_with(500, 200)

    def test_fill_input_typing(self):
        """Verifies typing into an input field."""
        mock_el = MagicMock()
        mock_el.name = "Cari"
        mock_el.control_type = "Edit"
        mock_el.center_x = 400
        mock_el.center_y = 150
        mock_el.automation_id = "search_box"

        with patch("app.tools.web_agent.get_active_window_info", return_value={"hwnd": 1234, "title": "Google"}), \
             patch("app.tools.web_agent.extract_uia_elements", return_value=[mock_el]), \
             patch("app.tools.web_agent.mouse_click"), \
             patch("app.tools.web_agent.type_text") as mock_type:

            res = self.agent.fill_input("Cari", "beasiswa luar negeri", press_enter=False, language="id")
            self.assertTrue(res.success)
            self.assertEqual(res.action, "fill_input")
            mock_type.assert_called_with("beasiswa luar negeri")

    def test_scroll_page(self):
        """Verifies mouse scrolling down and up."""
        with patch("app.tools.web_agent.mouse_scroll") as mock_scroll:
            res_down = self.agent.scroll_page(direction="down", amount=500, language="id")
            self.assertTrue(res_down.success)
            mock_scroll.assert_called_with(-500)

            res_up = self.agent.scroll_page(direction="up", amount=400, language="id")
            self.assertTrue(res_up.success)
            mock_scroll.assert_called_with(400)

    def test_read_page_content_extraction(self):
        """Verifies reading and summarizing active page content."""
        self.agent.active_url = "https://example.com/article"

        with patch("app.tools.web_agent.fetch_page_content", return_value=(True, "Judul Berita", "Ini adalah paragraf pertama artikel. Ini kalimat kedua. Ini kalimat ketiga.")):
            res = self.agent.read_page(language="id")
            self.assertTrue(res.success)
            self.assertIn("Ringkasan halaman", res.message)
            self.assertIn("Judul Berita", res.message)

    def test_manage_tab_actions(self):
        """Verifies tab management operations."""
        with patch("app.tools.web_agent.open_new_tab", return_value=(True, "Tab baru dibuka.")), \
             patch("app.tools.web_agent.close_tab", return_value=(True, "Tab ditutup.")), \
             patch("app.tools.web_agent.navigate_back", return_value=(True, "Kembali ke halaman sebelumnya.")):

            r_new = self.agent.manage_tab("new_tab", language="id")
            self.assertTrue(r_new.success)

            r_close = self.agent.manage_tab("close_tab", language="id")
            self.assertTrue(r_close.success)

            r_back = self.agent.manage_tab("go_back", language="id")
            self.assertTrue(r_back.success)

    def test_unwrap_google_redirect_url(self):
        """Verifies Google redirect URLs are cleanly decoded to destination URLs."""
        g_url = "https://www.google.com/url?q=https://example.com/dest%3Fid%3D1&sa=U"
        unwrapped = unwrap_google_url(g_url)
        self.assertEqual(unwrapped, "https://example.com/dest?id=1")
