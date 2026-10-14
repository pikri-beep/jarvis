"""Unit tests for the Universal Memory Extractor."""

import json
from unittest.mock import MagicMock, patch
import pytest

from app.memory.extractor import MemoryExtractor
from app.memory.schemas import MemoryItem


def test_offline_extractor_heuristics():
    """Verifies that offline regex extractor correctly identifies key entities."""
    extractor = MemoryExtractor(provider="offline")

    text = "Namaku Alex, panggil aku bos, peramban favoritku Brave, dan editor kodenya VS Code"
    items = extractor._extract_offline_rules(text)

    item_dict = {item.key: item.value for item in items}
    assert item_dict.get("user_name") == "Alex"
    assert item_dict.get("honorific") == "bos"
    assert item_dict.get("preferred_browser") == "Brave"
    assert "vs code" in item_dict.get("preferred_code_editor", "").lower()


def test_offline_extractor_generic_fallback():
    """Verifies fallback for generic statements like 'ingat bahwa kopi favorit saya adalah espresso'."""
    extractor = MemoryExtractor(provider="offline")
    text = "ingat bahwa kopi favorit saya adalah espresso"
    items = extractor._extract_offline_rules(text)

    assert len(items) >= 1
    assert items[0].value.lower() == "espresso"


def test_groq_memory_extractor_mock():
    """Verifies parsing of structured JSON from Groq Cloud client."""
    mock_client = MagicMock()
    mock_resp = MagicMock()
    mock_choice = MagicMock()
    mock_choice.message.content = json.dumps({
        "memories": [
            {
                "key": "user_name",
                "value": "Rian",
                "category": "identity",
                "description": "Nama pengguna",
                "applies_to": "prompt"
            },
            {
                "key": "honorific",
                "value": "kak",
                "category": "identity",
                "description": "Panggilan pengguna",
                "applies_to": "tts"
            },
            {
                "key": "preferred_browser",
                "value": "Firefox",
                "category": "preference",
                "description": "Peramban utama",
                "applies_to": "router"
            }
        ]
    })
    mock_resp.choices = [mock_choice]
    mock_client.chat.completions.create.return_value = mock_resp

    extractor = MemoryExtractor(provider="groq")
    extractor._groq_client = mock_client

    items = extractor.extract("namaku Rian, panggil aku kak, perambanku Firefox")
    assert len(items) == 3

    assert items[0].key == "user_name"
    assert items[0].value == "Rian"
    assert items[1].key == "honorific"
    assert items[1].value == "kak"
    assert items[2].key == "preferred_browser"
    assert items[2].value == "Firefox"


def test_extractor_handles_empty_or_whitespace():
    """Empty strings should return an empty list without crashing."""
    extractor = MemoryExtractor(provider="offline")
    assert extractor.extract("") == []
    assert extractor.extract("   ") == []
    assert extractor.extract("/learn   ") == []
