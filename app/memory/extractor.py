"""Universal Memory Extractor for JARVIS.

Extracts structured identities, preferences, habits, and custom rules
from natural language text using Groq Cloud API (sub-second) with offline regex fallback.
"""

import json
import os
import re
import time
from typing import Any, Dict, List, Optional

from app.core.config import Settings, get_settings
from app.core.logger import setup_logger
from app.memory.schemas import MemoryItem

logger = setup_logger("jarvis.memory.extractor")

SYSTEM_EXTRACTOR_PROMPT = """Anda adalah Memory Extraction Engine untuk personal AI assistant JARVIS.
Tugas Anda adalah membaca kalimat pengguna (dalam Bahasa Indonesia atau Inggris), lalu mengekstrak semua fakta, identitas, kebiasaan, preferensi aplikasi, dan aturan perilaku menjadi entitas terstruktur.

Format JSON Output yang WAJIB dipatuhi:
{
  "memories": [
    {
      "key": "nama_kunci_standar",
      "value": "nilai_fakta_atau_preferensi",
      "category": "identity | preference | habit | rule | project | general",
      "description": "Deskripsi singkat dan jelas tentang memori ini dalam Bahasa Indonesia",
      "applies_to": "prompt | router | tts | general"
    }
  ]
}

Panduan Standarisasi Kunci (key):
- Nama pengguna -> "user_name" (category: identity, applies_to: prompt)
- Panggilan kesukaan pengguna (misal 'bos', 'sir', 'bro', 'kak', 'alex') -> "honorific" (category: identity, applies_to: tts)
- Peran/Profesi pengguna -> "profession" (category: identity, applies_to: prompt)
- Peramban favorit -> "preferred_browser" (category: preference, applies_to: router)
- Editor kode favorit -> "preferred_code_editor" (category: preference, applies_to: router)
- Pemutar musik / genre musik -> "preferred_music" (category: preference, applies_to: router)
- Bahasa pemrograman utama -> "preferred_language" atau "code_language_priority" (category: rule, applies_to: prompt)
- Jam ngoding / jadwal -> "coding_schedule" atau "daily_routine" (category: habit, applies_to: prompt)
- Folder proyek -> "default_workspace" (category: project, applies_to: router)
- Aturan instruksi khusus (misal: selalu ringkas, jangan buka edge, utamakan python) -> key deskriptif (category: rule, applies_to: prompt)

Hanya kembalikan objek JSON murni tanpa markdown pembungkus tambahan."""


class MemoryExtractor:
    """Extracts structured MemoryItem objects from unstructured natural language."""

    def __init__(
        self,
        settings: Optional[Settings] = None,
        provider: Optional[str] = None,
        model: Optional[str] = None,
        timeout: float = 3.5,
    ):
        self.settings = settings or get_settings()
        self.groq_model = model or getattr(self.settings, "groq_model", "qwen/qwen3.8-27b")
        self.timeout = timeout
        self.provider = (provider or getattr(self.settings, "interpreter_provider", "groq")).lower()
        self.groq_api_key = getattr(self.settings, "groq_api_key", None) or os.getenv("GROQ_API_KEY")
        self._groq_client = None

        if self.provider == "groq" and self.groq_api_key and self.groq_api_key.strip():
            try:
                from groq import Groq
                self._groq_client = Groq(api_key=self.groq_api_key.strip())
                logger.debug("MemoryExtractor initialized with Groq model '%s'", self.groq_model)
            except Exception as e:
                logger.warning("Failed to initialize Groq client for MemoryExtractor: %s", e)
                self._groq_client = None

    def extract(self, text: str) -> List[MemoryItem]:
        """Extracts MemoryItem list from user utterance."""
        cleaned = text.strip()
        if not cleaned:
            return []

        # Remove prefix if present, e.g. "/learn", "jarvis pelajari ini:", "ingat bahwa"
        cleaned = re.sub(r"^/learn\s*", "", cleaned, flags=re.I).strip()
        cleaned = re.sub(
            r"^(?:jarvis\s+)?(?:tolong\s+)?(?:pelajari\s+ini|pelajari\s+tentang\s+aku|pelajari|catat\s+ini|ingat\s+ini|ingat(?:\s+bahwa)?|remember(?:\s+that)?|catat(?:\s+bahwa)?)[:,\s]*",
            "",
            cleaned,
            flags=re.I,
        ).strip()

        if not cleaned:
            return []

        # 1. Try Groq Cloud Extraction (< 300ms)
        if self._groq_client is not None:
            try:
                t0 = time.perf_counter()
                resp = self._groq_client.chat.completions.create(
                    model=self.groq_model,
                    messages=[
                        {"role": "system", "content": SYSTEM_EXTRACTOR_PROMPT},
                        {"role": "user", "content": f'Teks Pengguna: "{cleaned}"\nJSON Output:'},
                    ],
                    response_format={"type": "json_object"},
                    temperature=0.1,
                    max_tokens=400,
                    timeout=self.timeout,
                )
                raw_json = resp.choices[0].message.content or ""
                items = self._parse_json_result(raw_json)
                elapsed_ms = (time.perf_counter() - t0) * 1000.0
                if items:
                    logger.info("Groq MemoryExtractor extracted %d items in %.1fms", len(items), elapsed_ms)
                    return items
            except Exception as e:
                logger.warning("Groq MemoryExtractor failed (%s); falling back to offline rule extractor", e)

        # 2. Offline Heuristic Fallback
        return self._extract_offline_rules(cleaned)

    def _parse_json_result(self, raw_json: str) -> List[MemoryItem]:
        """Parses LLM JSON output into validated MemoryItem list."""
        try:
            data = json.loads(raw_json)
            mem_list = data.get("memories") if isinstance(data, dict) else None
            if not isinstance(mem_list, list):
                return []

            results = []
            for m in mem_list:
                if not isinstance(m, dict):
                    continue
                k = str(m.get("key", "")).strip().lower().replace(" ", "_")
                v = str(m.get("value", "")).strip()
                if not k or not v:
                    continue

                cat = str(m.get("category", "general")).strip().lower()
                desc = str(m.get("description", "")).strip() or f"{k} = {v}"
                applies = str(m.get("applies_to", "general")).strip().lower()

                results.append(
                    MemoryItem(
                        key=k,
                        value=v,
                        category=cat,
                        description=desc,
                        applies_to=applies,
                        confidence=0.95,
                    )
                )
            return results
        except Exception as e:
            logger.warning("Error parsing extractor JSON (%s): %r", e, raw_json)
            return []

    def _extract_offline_rules(self, text: str) -> List[MemoryItem]:
        """Robust regex heuristics for offline extraction."""
        items: List[MemoryItem] = []
        lower = text.lower()

        # 1. User Name
        m_name = re.search(r"\b(?:nama(?:ku| saya)?|my name is)\s+(?:adalah\s+|=)?([a-z0-9_-]+)\b", lower)
        if m_name:
            val = m_name.group(1).title()
            items.append(MemoryItem(key="user_name", value=val, category="identity", description="Nama pengguna", applies_to="prompt"))

        # 2. Honorific / Panggilan
        m_hon = re.search(r"\bpanggil\s+(?:aku|saya)?\s*(?:dengan|sebagai)?\s*['\"]?([a-z0-9_-]+)['\"]?\b|\bcall me\s+([a-z0-9_-]+)\b", lower)
        if m_hon:
            val = (m_hon.group(1) or m_hon.group(2)).lower()
            items.append(MemoryItem(key="honorific", value=val, category="identity", description="Panggilan kesukaan pengguna", applies_to="tts"))

        # 3. Preferred Browser
        m_brow = re.search(r"\b(?:peramban|browser)(?:\s+(?:favorit(?:ku| saya)?|utama(?:ku| saya)?|ku|saya))?\s*(?:adalah|=|:)?\s*([a-z0-9_-]+)\b", lower)
        if m_brow:
            val = m_brow.group(1).title()
            if val.lower() not in ("ku", "saya", "favorit", "utama", "adalah"):
                items.append(MemoryItem(key="preferred_browser", value=val, category="preference", description="Peramban web utama", applies_to="router"))

        # 4. Preferred Code Editor
        m_edit = re.search(r"\b(?:editor|code editor)(?:\s+(?:favorit(?:ku| saya)?|utama(?:ku| saya)?|kodenya|kode|ku|saya))?\s*(?:adalah|=|:)?\s*([a-z0-9_\s-]+?)(?:,|$|\.|\blalu\b|\bdan\b)", lower)
        if m_edit:
            val = m_edit.group(1).strip().title()
            if val.lower() not in ("ku", "saya", "favorit", "utama", "adalah"):
                items.append(MemoryItem(key="preferred_code_editor", value=val, category="preference", description="Editor kode utama", applies_to="router"))

        # 5. Preferred Programming Language / Code Rule
        m_lang = re.search(r"\b(?:bahasa|kode|ngoding|prioritas(?:kan)?)\s*(?:kode|bahasa)?\s*(?:prioritaskan|favorit|pakai)?\s*([a-z0-9#+]+)\b", lower)
        if m_lang:
            val = m_lang.group(1).title()
            if val.lower() in ("python", "javascript", "typescript", "rust", "go", "java", "c++", "c#", "php"):
                items.append(MemoryItem(key="code_language_priority", value=val, category="rule", description=f"Prioritaskan bahasa {val} saat membuat kode", applies_to="prompt"))

        # 6. Favorite Food & Drink
        m_food = re.search(r"\b(?:makanan\s+(?:favorit|kesukaan)(?:ku| saya)?|favorite\s+food)\s*(?:adalah|=|:)?\s*([a-z0-9_\s-]+?)(?:,|$|\.|\bdan\b)", lower)
        if m_food:
            val = m_food.group(1).strip()
            items.append(MemoryItem(key="makanan_favorit", value=val, category="preference", description="Makanan favorit", applies_to="prompt"))

        m_drink = re.search(r"\b(?:minuman\s+(?:favorit|kesukaan)(?:ku| saya)?|favorite\s+drink)\s*(?:adalah|=|:)?\s*([a-z0-9_\s-]+?)(?:,|$|\.|\bdan\b)", lower)
        if m_drink:
            val = m_drink.group(1).strip()
            items.append(MemoryItem(key="minuman_favorit", value=val, category="preference", description="Minuman favorit", applies_to="prompt"))

        # 7. Location / City
        m_loc = re.search(r"\b(?:(?:saya|aku)\s+(?:tinggal\s+di|berada\s+di|domisili\s+di)|lokasi(?:ku| saya)?\s*(?:di|adalah)?)\s*([a-z0-9_\s-]+?)(?:,|$|\.)", lower)
        if m_loc:
            val = m_loc.group(1).strip().title()
            items.append(MemoryItem(key="location", value=val, category="identity", description="Lokasi pengguna", applies_to="prompt"))

        # 8. Fallback generic "ingat bahwa <key> adalah <value>" or "<key> adalah <value>"
        if not items:
            m_gen = re.search(r"(?:(?:ingat\s+bahwa|remember\s+that|catat\s+bahwa)\s+)?(.+?)\s+(?:adalah|is|=|merupakan)\s+(.+)", text, re.I)
            if m_gen:
                k = m_gen.group(1).strip().lower().replace(" ", "_")
                k = re.sub(r"^(?:bahwa|that)\s+", "", k).strip()
                v = m_gen.group(2).strip().rstrip(".")
                if k and v:
                    items.append(MemoryItem(key=k, value=v, category="general", description=f"{k} = {v}", applies_to="general"))

        return items

