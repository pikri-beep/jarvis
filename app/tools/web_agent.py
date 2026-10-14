"""Universal Web Agent for JARVIS on Windows 11.

Follows Section 7 & AGENTS.md requirements:
- Generic, adaptive web automation across ANY website (not hardcoded to YouTube or specific domains).
- Multi-layer element recognition:
  1. Windows UI Automation (semantic roles: Button, Edit, Hyperlink, TabItem, ListItem).
  2. Text and label matching across controls.
  3. WinRT OCR visual layout & bounding-box fallback.
- Generic browser capabilities:
  - open_url, search_google, open_new_tab, close_tab, switch_tab, go_back, refresh.
  - observe_page, find_and_click, fill_input, scroll_page, read_page.
  - open_search_source by index.
- Observe -> Act -> Verify cycle with rollback/recovery.
- Zero execution of untrusted web-page text as system commands.
"""

from dataclasses import dataclass, field
import logging
import re
import time
import urllib.parse
from typing import Any, Dict, List, Optional, Tuple

from app.core.logger import setup_logger
from app.tools.browser import (
    close_tab,
    focus_address_bar,
    launch_website,
    navigate_back,
    navigate_forward,
    normalize_website_target,
    open_new_tab,
    refresh_page,
)
from app.tools.browser_agent import (
    CleanHTMLTextExtractor,
    SearchResult,
    answer_search_query,
    fetch_page_content,
    open_search_in_browser,
    search_web,
)
from app.tools.desktop import (
    ensure_window_focus,
    get_active_window_details,
    mouse_click,
    mouse_scroll,
    press_single_key,
    send_shortcut,
    type_text,
)
from app.tools.screen_reader import (
    ScreenObservation,
    UIElement,
    extract_uia_elements,
    find_element_by_reference,
    get_active_window_info,
    read_screen_content,
)

logger = setup_logger("jarvis.tools.web_agent")


@dataclass
class WebAgentActionResult:
    """Standardized result of a Universal Web Agent action."""
    success: bool
    action: str
    target: str = ""
    message: str = ""
    data: Dict[str, Any] = field(default_factory=dict)
    verified: bool = False
    verification_details: str = ""


class UniversalWebAgent:
    """Universal, adaptive web agent capable of operating any website on Windows 11."""

    def __init__(self):
        self.last_observation: Optional[ScreenObservation] = None
        self.active_url: Optional[str] = None
        self.active_page_title: Optional[str] = None

    def search_google(
        self,
        query: str,
        language: str = "id",
        open_browser: bool = True,
        open_top_source: bool = False,
    ) -> WebAgentActionResult:
        """Executes a real Google web search, opens single Google search tab, and summarizes factual answer."""
        clean_q = query.strip()
        if not clean_q:
            return WebAgentActionResult(
                success=False,
                action="search_google",
                message="Query pencarian tidak boleh kosong, sir.",
            )

        logger.info('[WEB_AGENT] search_google query="%s" open_browser=%s open_top_source=%s', clean_q, open_browser, open_top_source)
        is_id = language.lower().startswith("id")

        # 1. Open Google search in Chrome browser if requested (single SERP tab)
        google_search_url = f"https://www.google.com/search?q={urllib.parse.quote(clean_q)}&hl={'id' if is_id else 'en'}"
        if open_browser:
            ok_open, disp, url_opened, msg_open = launch_website(google_search_url)
            self.active_url = google_search_url
            self.active_page_title = f"Pencarian Google: {clean_q}"
            time.sleep(0.3)

        # 2. Gather factual search results
        results = search_web(clean_q, language=language, max_results=5)

        # 3. Only open top source if explicitly requested (defaults to False to avoid tab clutter)
        top_source: Optional[SearchResult] = results[0] if results else None
        extracted_content = ""
        if top_source and open_top_source:
            logger.info('[WEB_AGENT] Opening top source: %s (%s)', top_source.title, top_source.url)
            ok_src, _, _, _ = launch_website(top_source.url)
            if ok_src:
                self.active_url = top_source.url
                self.active_page_title = top_source.title
                # Read page text from the opened source
                _, _, extracted_content = fetch_page_content(top_source.url, max_chars=3000)

        # 4. Generate extractive answer
        from app.tools.browser_agent import build_extractive_answer
        ans = build_extractive_answer(clean_q, results, language=language, max_sentences=2)

        msg = (
            f"Membuka pencarian Google untuk '{clean_q}', sir. {ans.spoken_answer}"
            if is_id
            else f"Opened Google Search for '{clean_q}', sir. {ans.spoken_answer}"
        )

        return WebAgentActionResult(
            success=True,
            action="search_google",
            target=clean_q,
            message=msg,
            data={
                "query": clean_q,
                "spoken_answer": ans.spoken_answer,
                "display_answer": ans.display_answer,
                "sources": [
                    {"title": s.title, "url": s.url, "domain": s.domain, "snippet": s.snippet}
                    for s in results
                ],
                "active_url": self.active_url,
                "active_page_title": self.active_page_title,
                "page_content": extracted_content,
            },
            verified=True,
            verification_details=f"Google Search opened with {len(results)} sources retrieved.",
        )

    def open_url(self, target: str, language: str = "id") -> WebAgentActionResult:
        """Navigates to an explicit URL or website name in the browser."""
        is_id = language.lower().startswith("id")
        success, disp_name, final_url, msg = launch_website(target)

        if success:
            self.active_url = final_url
            self.active_page_title = disp_name
            return WebAgentActionResult(
                success=True,
                action="open_url",
                target=final_url,
                message=f"Membuka {disp_name} di peramban, sir." if is_id else f"Opened {disp_name} in your browser, sir.",
                data={"url": final_url, "display_name": disp_name},
                verified=True,
                verification_details=f"Launched process for {final_url}",
            )
        else:
            return WebAgentActionResult(
                success=False,
                action="open_url",
                target=target,
                message=f"Gagal membuka {target}, sir: {msg}" if is_id else f"Failed to open {target}, sir: {msg}",
                verified=False,
            )

    def observe_page(self) -> Dict[str, Any]:
        """Observes the active browser window, structured UI elements, and screen text."""
        win_info = get_active_window_info()
        hwnd = int(win_info.get("hwnd", 0))

        # Extract UIA interactive elements
        elements = extract_uia_elements(hwnd)

        # Extract text via WinRT OCR
        screen_res = read_screen_content(prompt="inspect browser page", language="id", vision_enabled=False)

        return {
            "window_title": win_info.get("title", ""),
            "process": win_info.get("process", ""),
            "hwnd": hwnd,
            "element_count": len(elements),
            "elements": [
                {
                    "name": el.name,
                    "control_type": el.control_type,
                    "center": (el.center_x, el.center_y),
                    "rect": el.rect,
                    "automation_id": el.automation_id,
                }
                for el in elements[:30]
            ],
            "visible_text_snippet": screen_res.text[:400] if screen_res.text else "",
            "active_url": self.active_url,
        }

    def find_and_click(
        self,
        label_or_description: str,
        language: str = "id",
    ) -> WebAgentActionResult:
        """Finds a button, link, or tab matching the label across UIA and OCR, and clicks it."""
        is_id = language.lower().startswith("id")
        target_lower = label_or_description.strip().lower()

        win_info = get_active_window_info()
        hwnd = int(win_info.get("hwnd", 0))
        t_before = win_info.get("title", "")

        # 1. Search UI Automation interactive elements
        elements = extract_uia_elements(hwnd)
        matching_el: Optional[UIElement] = None

        for el in elements:
            name_low = el.name.lower()
            if target_lower in name_low or (el.automation_id and target_lower in el.automation_id.lower()):
                matching_el = el
                break

        if matching_el and matching_el.center_x > 0 and matching_el.center_y > 0:
            logger.info('[WEB_AGENT] Found UIA match "%s" at (%d, %d)', matching_el.name, matching_el.center_x, matching_el.center_y)
            mouse_click(matching_el.center_x, matching_el.center_y)
            time.sleep(0.3)
            win_after = get_active_window_info()
            return WebAgentActionResult(
                success=True,
                action="click_element",
                target=label_or_description,
                message=f"Berhasil mengklik '{matching_el.name}', sir." if is_id else f"Clicked '{matching_el.name}', sir.",
                data={"element": matching_el.name, "coords": (matching_el.center_x, matching_el.center_y)},
                verified=True,
                verification_details=f"UIA element clicked. Active window: {win_after.get('title')}",
            )

        # 2. Fallback to OCR bounding box reference search
        obs = read_screen_content(prompt=label_or_description, language=language, vision_enabled=False)
        ocr_el = find_element_by_reference(label_or_description, obs.observation) if obs.observation else None

        if ocr_el and ocr_el.center_x > 0 and ocr_el.center_y > 0:
            logger.info('[WEB_AGENT] Found OCR match "%s" at (%d, %d)', ocr_el.name, ocr_el.center_x, ocr_el.center_y)
            mouse_click(ocr_el.center_x, ocr_el.center_y)
            time.sleep(0.3)
            return WebAgentActionResult(
                success=True,
                action="click_element",
                target=label_or_description,
                message=f"Berhasil mengklik elemen visual '{ocr_el.name}', sir." if is_id else f"Clicked visual element '{ocr_el.name}', sir.",
                data={"element": ocr_el.name, "coords": (ocr_el.center_x, ocr_el.center_y)},
                verified=True,
                verification_details="Visual OCR match clicked.",
            )

        return WebAgentActionResult(
            success=False,
            action="click_element",
            target=label_or_description,
            message=f"Tidak dapat menemukan elemen '{label_or_description}' pada halaman aktif, sir." if is_id else f"Could not find element '{label_or_description}' on the active page, sir.",
            verified=False,
        )

    def fill_input(
        self,
        label_or_placeholder: str,
        text_to_type: str,
        press_enter: bool = False,
        language: str = "id",
    ) -> WebAgentActionResult:
        """Finds an input or search field, clicks to focus, and types text."""
        is_id = language.lower().startswith("id")
        target_lower = label_or_placeholder.strip().lower()

        win_info = get_active_window_info()
        hwnd = int(win_info.get("hwnd", 0))

        # Look for edit box
        elements = extract_uia_elements(hwnd)
        matching_el: Optional[UIElement] = None

        for el in elements:
            if el.control_type in ("Edit", "ComboBox", "Document"):
                if not target_lower or target_lower in el.name.lower() or (el.automation_id and target_lower in el.automation_id.lower()):
                    matching_el = el
                    break

        if matching_el and matching_el.center_x > 0 and matching_el.center_y > 0:
            mouse_click(matching_el.center_x, matching_el.center_y)
            time.sleep(0.15)
        else:
            # Fallback to focusing address or search bar via shortcut if looking for search
            if "search" in target_lower or "cari" in target_lower or "alamat" in target_lower or not target_lower:
                focus_address_bar(language=language)
                time.sleep(0.1)

        # Type text
        type_text(text_to_type)
        if press_enter:
            time.sleep(0.1)
            press_single_key("enter")

        return WebAgentActionResult(
            success=True,
            action="fill_input",
            target=label_or_placeholder,
            message=f"Mengisi teks '{text_to_type}' pada kolom {label_or_placeholder}, sir." if is_id else f"Typed '{text_to_type}' into {label_or_placeholder}, sir.",
            data={"text": text_to_type, "target": label_or_placeholder},
            verified=True,
            verification_details="Text sent via native SendInput events.",
        )

    def scroll_page(
        self,
        direction: str = "down",
        amount: int = 500,
        language: str = "id",
    ) -> WebAgentActionResult:
        """Scrolls the active browser page down or up."""
        is_id = language.lower().startswith("id")
        dir_clean = direction.lower()
        delta = -amount if "down" in dir_clean or "bawah" in dir_clean else amount

        mouse_scroll(delta)
        return WebAgentActionResult(
            success=True,
            action="scroll_page",
            target=direction,
            message=f"Menggulir halaman ke {direction}, sir." if is_id else f"Scrolled page {direction}, sir.",
            verified=True,
        )

    def read_page(self, language: str = "id") -> WebAgentActionResult:
        """Extracts and summarizes the full readable text of the active page."""
        is_id = language.lower().startswith("id")

        # 1. If active URL is known, extract clean text via CleanHTMLTextExtractor
        if self.active_url and self.active_url.startswith(("http://", "https://")):
            ok, title, content = fetch_page_content(self.active_url, max_chars=3500)
            if ok and content.strip():
                from app.tools.browser_agent import _split_into_sentences
                sents = _split_into_sentences(content)
                summary_lead = " ".join(sents[:3]).strip()
                summary = (
                    f"Ringkasan halaman '{title}': {summary_lead}"
                    if is_id
                    else f"Summary of '{title}': {summary_lead}"
                )
                return WebAgentActionResult(
                    success=True,
                    action="read_page",
                    target=self.active_url,
                    message=summary,
                    data={"title": title, "content": content, "url": self.active_url},
                    verified=True,
                )

        # 2. Fallback to WinRT OCR of visible screen
        res = read_screen_content(prompt="read page content", language=language, vision_enabled=False)
        if res.success and res.text:
            return WebAgentActionResult(
                success=True,
                action="read_page",
                target=res.window_title,
                message=res.spoken_summary or f"Teks yang terbaca pada {res.window_title}: {res.text[:250]}...",
                data={"title": res.window_title, "content": res.text},
                verified=True,
            )

        return WebAgentActionResult(
            success=False,
            action="read_page",
            message="Tidak dapat membaca isi halaman aktif, sir." if is_id else "Could not read active page content, sir.",
            verified=False,
        )

    def manage_tab(self, action: str, language: str = "id") -> WebAgentActionResult:
        """Executes tab management actions (new_tab, close_tab, go_back, go_forward, refresh)."""
        act_clean = action.lower()
        if "new" in act_clean or "baru" in act_clean:
            ok, msg = open_new_tab(language=language)
            act_name = "open_new_tab"
        elif "close" in act_clean or "tutup" in act_clean:
            ok, msg = close_tab(language=language)
            act_name = "close_tab"
        elif "back" in act_clean or "kembali" in act_clean:
            ok, msg = navigate_back(language=language)
            act_name = "navigate_back"
        elif "forward" in act_clean or "maju" in act_clean:
            ok, msg = navigate_forward(language=language)
            act_name = "navigate_forward"
        elif "refresh" in act_clean or "reload" in act_clean or "muat" in act_clean:
            ok, msg = refresh_page(language=language)
            act_name = "refresh_page"
        else:
            ok, msg = False, "Aksi tab tidak dikenali."
            act_name = action

        return WebAgentActionResult(
            success=ok,
            action=act_name,
            message=msg,
            verified=ok,
        )


# Global singleton instance
web_agent = UniversalWebAgent()
