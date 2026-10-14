"""Browser and URL management tools for Windows 11.

Follows AGENTS.md security guidelines:
- Strictly explicit function calls (no arbitrary shell=True commands).
- Deterministic HTTPS website resolution for known web services.
- Opens URLs in Google Chrome when installed, with verified fallback to default browser.
- Verifies process launch success before reporting.
- Reports failures honestly.
"""

import difflib
import os
import re
import subprocess
import urllib.parse
import webbrowser
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from app.core.logger import setup_logger
from app.tools.apps import find_application_executable

logger = setup_logger("jarvis.tools.browser")


@dataclass
class WebsiteDefinition:
    """Definition for a registered website or web service."""
    canonical_name: str
    display_name: str
    url: str
    aliases: List[str] = field(default_factory=list)


class WebsiteRegistry:
    """Registry managing website mappings and aliases."""

    def __init__(self):
        self._sites: Dict[str, WebsiteDefinition] = {}
        self._alias_map: Dict[str, str] = {}
        self._register_default_websites()

    def register(self, site: WebsiteDefinition) -> None:
        """Registers a website definition and indexes all its aliases."""
        self._sites[site.canonical_name] = site
        self._alias_map[site.canonical_name.lower()] = site.canonical_name
        self._alias_map[site.display_name.lower()] = site.canonical_name
        for alias in site.aliases:
            self._alias_map[alias.strip().lower()] = site.canonical_name

    def register_alias(self, alias: str, canonical_name: str) -> bool:
        """Dynamically registers an alias for an existing canonical website."""
        clean_alias = alias.strip().lower()
        clean_canon = canonical_name.strip().lower()
        if not clean_alias or clean_canon not in self._sites:
            return False
        self._alias_map[clean_alias] = clean_canon
        site = self._sites[clean_canon]
        if clean_alias not in [a.lower() for a in site.aliases]:
            site.aliases.append(clean_alias)
        logger.info("Registered dynamic website alias '%s' -> '%s'", clean_alias, clean_canon)
        return True

    def find_fuzzy_matches(self, query: str, cutoff: float = 0.55) -> List[Tuple[str, str, float]]:
        """Finds closest registered website candidates based on string similarity.

        Returns:
            List of (canonical_name, display_name, score) sorted by score descending.
        """
        if not query:
            return []
        q = query.strip().lower()
        best_per_site: Dict[str, Tuple[str, float]] = {}

        for canonical, site in self._sites.items():
            candidates = [canonical, site.display_name.lower()] + [a.lower() for a in site.aliases]
            max_s = 0.0
            for cand in candidates:
                cand_lower = cand.strip().lower()
                is_sub = False
                if len(cand_lower) >= 4 and cand_lower in q:
                    is_sub = True
                elif len(q) >= 4 and q in cand_lower:
                    is_sub = True
                elif cand_lower in q.split() or q in cand_lower.split():
                    is_sub = True

                if is_sub:
                    sub_ratio = len(min(q, cand_lower, key=len)) / max(len(q), len(cand_lower), 1)
                    s = max(difflib.SequenceMatcher(None, q, cand_lower).ratio(), 0.6 + 0.35 * sub_ratio)
                else:
                    s = difflib.SequenceMatcher(None, q, cand_lower).ratio()
                if s > max_s:
                    max_s = s
            if max_s >= cutoff:
                best_per_site[canonical] = (site.display_name, max_s)

        results = [(can, name, score) for can, (name, score) in best_per_site.items()]
        results.sort(key=lambda x: x[2], reverse=True)
        return results

    def get(self, name: str) -> Optional[WebsiteDefinition]:
        """Retrieves a website definition by canonical name or alias."""
        canonical = self.resolve_canonical_name(name)
        return self._sites.get(canonical)

    def resolve_canonical_name(self, raw_name: str) -> str:
        """Resolves raw spoken or typed name to canonical identifier."""
        if not raw_name:
            return ""
        cleaned = raw_name.strip().lower()
        return self._alias_map.get(cleaned, cleaned)

    def is_registered(self, name: str) -> bool:
        """Checks if a name or alias matches a registered website."""
        canonical = self.resolve_canonical_name(name)
        return canonical in self._sites

    def _register_default_websites(self) -> None:
        """Initializes standard website mappings with explicit HTTPS URLs."""
        # 1. YouTube
        self.register(
            WebsiteDefinition(
                canonical_name="youtube",
                display_name="YouTube",
                url="https://www.youtube.com",
                aliases=[
                    "youtube", "you tube", "yutup", "yt", "situs youtube",
                    "web youtube", "website youtube", "laman youtube"
                ],
            )
        )

        # 2. Google
        self.register(
            WebsiteDefinition(
                canonical_name="google",
                display_name="Google",
                url="https://www.google.com",
                aliases=[
                    "google", "gugel", "google search", "pencarian google",
                    "mesin pencari", "search engine", "google.com", "situs google", "web google"
                ],
            )
        )

        # 3. Gmail
        self.register(
            WebsiteDefinition(
                canonical_name="gmail",
                display_name="Gmail",
                url="https://mail.google.com",
                aliases=[
                    "gmail", "gmai", "email google", "google mail", "surel google",
                    "inbox gmail", "kotak masuk gmail", "webmail google", "situs gmail"
                ],
            )
        )

        # 4. ChatGPT
        self.register(
            WebsiteDefinition(
                canonical_name="chatgpt",
                display_name="ChatGPT",
                url="https://chatgpt.com",
                aliases=[
                    "chatgpt", "chat gpt", "openai chat", "chat openai",
                    "chatgpt.com", "situs chatgpt", "web chatgpt"
                ],
            )
        )

        # 5. Instagram
        self.register(
            WebsiteDefinition(
                canonical_name="instagram",
                display_name="Instagram",
                url="https://www.instagram.com",
                aliases=[
                    "instagram", "ig", "insta", "instagram.com", "situs instagram",
                    "web instagram", "website instagram", "halaman instagram"
                ],
            )
        )

        # 6. Gemini
        self.register(
            WebsiteDefinition(
                canonical_name="gemini",
                display_name="Google Gemini",
                url="https://gemini.google.com",
                aliases=[
                    "gemini", "google gemini", "gemini ai", "gemini.google.com",
                    "gemini google", "aplikasi gemini", "situs gemini", "web gemini"
                ],
            )
        )

        # 7. Claude
        self.register(
            WebsiteDefinition(
                canonical_name="claude",
                display_name="Anthropic Claude",
                url="https://claude.ai",
                aliases=[
                    "claude", "claude ai", "anthropic claude", "claude.ai", "situs claude"
                ],
            )
        )

        # 8. GitHub
        self.register(
            WebsiteDefinition(
                canonical_name="github",
                display_name="GitHub",
                url="https://github.com",
                aliases=["github", "git hub", "github.com", "situs github"],
            )
        )

        # 9. WhatsApp Web
        self.register(
            WebsiteDefinition(
                canonical_name="whatsapp_web",
                display_name="WhatsApp Web",
                url="https://web.whatsapp.com",
                aliases=["whatsapp web", "wa web", "web whatsapp", "web wa"],
            )
        )


# Global singleton registry
website_registry = WebsiteRegistry()


def is_known_website(raw_name: str) -> bool:
    """Checks if raw name matches a registered website or direct URL."""
    if not raw_name:
        return False
    cleaned = re.sub(r"^(?:situs|website|web|laman|halaman)\s+", "", raw_name.strip(), flags=re.IGNORECASE)
    cleaned = re.sub(r"\s+(?:site|website|web)$", "", cleaned.strip(), flags=re.IGNORECASE)
    cleaned = re.sub(r"\s+(?:di|in|pada)\s+(?:google\s+)?(?:chrome|krom|browser|peramban|edge)$", "", cleaned.strip(), flags=re.IGNORECASE)
    if website_registry.is_registered(cleaned):
        return True
    # Direct URL check (e.g. https://..., http://..., domain.com, or sub.domain.com)
    if re.match(r"^(?:https?://)?(?:[a-zA-Z0-9_\-]+\.)+[a-zA-Z]{2,}(?:/\S*)?$", cleaned):
        return True
    return False


def normalize_website_target(raw_name: str) -> Tuple[str, str, str]:
    """Resolves raw website query into (canonical_name, display_name, url)."""
    cleaned = re.sub(r"^(?:situs|website|web|laman|halaman)\s+", "", raw_name.strip(), flags=re.IGNORECASE)
    cleaned = re.sub(r"\s+(?:site|website|web)$", "", cleaned.strip(), flags=re.IGNORECASE)
    cleaned = re.sub(r"\s+(?:di|in|pada)\s+(?:google\s+)?(?:chrome|krom|browser|peramban|edge)$", "", cleaned.strip(), flags=re.IGNORECASE)

    site = website_registry.get(cleaned)
    if site:
        return site.canonical_name, site.display_name, site.url

    # Check if raw target is a direct URL or domain
    if re.match(r"^(?:[a-zA-Z0-9_\-]+\.)+[a-zA-Z]{2,}(?:/\S*)?$", cleaned):
        url = f"https://{cleaned}"
        return cleaned, cleaned, url
    elif cleaned.startswith(("http://", "https://")):
        parsed = urllib.parse.urlparse(cleaned)
        display = parsed.netloc or cleaned
        return display, display, cleaned

    return cleaned, cleaned.capitalize(), f"https://www.google.com/search?q={urllib.parse.quote(cleaned)}"


def launch_website(raw_target: str) -> Tuple[bool, str, str, str]:
    """Safely launches a website in Google Chrome with verified fallback to default browser.

    Args:
        raw_target: Spoken or typed website name or URL (e.g. 'YouTube', 'Buka Gmail', 'https://...').

    Returns:
        Tuple of (success_bool, display_name, url, message).
    """
    if not raw_target or not raw_target.strip():
        return False, "", "", "Target website tidak boleh kosong."

    canonical, display_name, target_url = normalize_website_target(raw_target)

    # Basic URL validation: must be an http or https URL
    if not target_url.startswith(("http://", "https://")):
        target_url = f"https://{target_url}"

    # Step 1: Prefer Google Chrome if installed
    chrome_exe = find_application_executable("chrome")
    if chrome_exe is not None and Path(chrome_exe).exists():
        try:
            cmd = [str(chrome_exe), target_url]
            proc = subprocess.Popen(
                cmd,
                close_fds=True,
                creationflags=subprocess.DETACHED_PROCESS if hasattr(subprocess, "DETACHED_PROCESS") else 0,
            )
            if proc.pid and (proc.poll() is None or proc.poll() == 0):
                logger.info("Successfully opened website '%s' (%s) in Chrome (PID %d)", display_name, target_url, proc.pid)
                return True, display_name, target_url, f"Berhasil membuka {display_name} di Google Chrome."
            else:
                logger.warning("Chrome process exited with error (code %s) for '%s'", proc.returncode, target_url)
        except Exception as e:
            logger.warning("Failed to launch Chrome with URL '%s': %s. Falling back to default browser.", target_url, e)

    # Step 2: Fallback to default browser via os.startfile on Windows
    try:
        if hasattr(os, "startfile"):
            os.startfile(target_url)
            logger.info("Successfully opened website '%s' (%s) via os.startfile", display_name, target_url)
            return True, display_name, target_url, f"Berhasil membuka {display_name} di peramban sistem."
        else:
            opened = webbrowser.open(target_url)
            if opened:
                logger.info("Successfully opened website '%s' (%s) via webbrowser", display_name, target_url)
                return True, display_name, target_url, f"Berhasil membuka {display_name}."
            else:
                logger.error("webbrowser.open failed for URL: %s", target_url)
                return False, display_name, target_url, f"Gagal membuka {display_name} di peramban."
    except Exception as e:
        logger.error("Error launching website '%s' (%s): %s", display_name, target_url, e)
        return False, display_name, target_url, f"Gagal membuka {display_name}: {e}"


def open_new_tab(language: str = "id") -> Tuple[bool, str]:
    """Opens a new browser tab via Ctrl+T shortcut."""
    from app.tools.desktop import send_shortcut
    ok, _ = send_shortcut("ctrl+t", language=language)
    is_id = language.lower().startswith("id")
    msg = "Tab baru telah dibuka di browser, sir." if is_id else "New tab opened in browser, sir."
    return ok, msg if ok else ("Gagal membuka tab baru." if is_id else "Failed to open new tab.")


def close_tab(language: str = "id") -> Tuple[bool, str]:
    """Closes the current browser tab via Ctrl+W shortcut."""
    from app.tools.desktop import send_shortcut
    ok, _ = send_shortcut("ctrl+w", language=language)
    is_id = language.lower().startswith("id")
    msg = "Tab saat ini telah ditutup, sir." if is_id else "Current tab closed, sir."
    return ok, msg if ok else ("Gagal menutup tab." if is_id else "Failed to close tab.")


def refresh_page(language: str = "id") -> Tuple[bool, str]:
    """Reloads the active browser page via Ctrl+R shortcut."""
    from app.tools.desktop import send_shortcut
    ok, _ = send_shortcut("ctrl+r", language=language)
    is_id = language.lower().startswith("id")
    msg = "Halaman browser telah dimuat ulang, sir." if is_id else "Page reloaded, sir."
    return ok, msg if ok else ("Gagal memuat ulang halaman." if is_id else "Failed to refresh page.")


def navigate_back(language: str = "id") -> Tuple[bool, str]:
    """Navigates back to the previous page via Alt+Left shortcut."""
    from app.tools.desktop import send_shortcut
    ok, _ = send_shortcut("alt+left", language=language)
    is_id = language.lower().startswith("id")
    msg = "Kembali ke halaman sebelumnya, sir." if is_id else "Navigated back, sir."
    return ok, msg if ok else ("Gagal kembali ke halaman sebelumnya." if is_id else "Failed to go back.")


def navigate_forward(language: str = "id") -> Tuple[bool, str]:
    """Navigates forward to the next page via Alt+Right shortcut."""
    from app.tools.desktop import send_shortcut
    ok, _ = send_shortcut("alt+right", language=language)
    is_id = language.lower().startswith("id")
    msg = "Maju ke halaman berikutnya, sir." if is_id else "Navigated forward, sir."
    return ok, msg if ok else ("Gagal maju ke halaman berikutnya." if is_id else "Failed to go forward.")


def focus_address_bar(language: str = "id") -> Tuple[bool, str]:
    """Focuses the browser address bar via Ctrl+L shortcut."""
    from app.tools.desktop import send_shortcut
    ok, _ = send_shortcut("ctrl+l", language=language)
    is_id = language.lower().startswith("id")
    msg = "Kolom alamat browser telah difokuskan, sir." if is_id else "Address bar focused, sir."
    return ok, msg if ok else ("Gagal memfokuskan kolom alamat." if is_id else "Failed to focus address bar.")

