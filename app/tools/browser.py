"""Browser and URL management tools for Windows 11.

Follows AGENTS.md security guidelines:
- Strictly explicit function calls (no arbitrary shell=True commands).
- Deterministic HTTPS website resolution for known web services.
- Opens URLs in Google Chrome when installed, with verified fallback to default browser.
- Verifies process launch success before reporting.
- Reports failures honestly.
"""

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


# Global singleton registry
website_registry = WebsiteRegistry()


def is_known_website(raw_name: str) -> bool:
    """Checks if raw name matches a registered website or direct URL."""
    if not raw_name:
        return False
    cleaned = re.sub(r"^(?:situs|website|web|laman|halaman)\s+", "", raw_name.strip(), flags=re.IGNORECASE)
    cleaned = re.sub(r"\s+(?:site|website|web)$", "", cleaned.strip(), flags=re.IGNORECASE)
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
            if proc.pid and proc.poll() is None:
                logger.info("Successfully opened website '%s' (%s) in Chrome (PID %d)", display_name, target_url, proc.pid)
                return True, display_name, target_url, f"Berhasil membuka {display_name} di Google Chrome."
            else:
                logger.warning("Chrome process exited immediately (code %s) for '%s'", proc.returncode, target_url)
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
