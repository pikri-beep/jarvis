"""Unit tests for the local LLM client and streaming processor."""

import json
from unittest.mock import MagicMock, patch
import pytest
import requests

from app.ai.llm import LLMError, OllamaClient, OllamaConnectionError, OllamaModelNotFoundError
from app.ai.streaming import StreamProcessor


def test_stream_processor_normal():
    processor = StreamProcessor(strip_thinking=True)
    out1 = processor.process_chunk("Hello, ")
    out2 = processor.process_chunk("sir!")
    out3 = processor.flush()
    assert (out1 + out2 + out3) == "Hello, sir!"


def test_stream_processor_filters_thinking():
    processor = StreamProcessor(strip_thinking=True)
    text_chunks = [
        "<think>",
        "The user is asking for assistance. ",
        "I should be polite.",
        "</think>",
        "Good evening, sir. How may I assist you?",
    ]
    result = "".join(processor.process_chunk(c) for c in text_chunks) + processor.flush()
    assert "<think>" not in result
    assert "I should be polite" not in result
    assert result == "Good evening, sir. How may I assist you?"


def test_ollama_client_health_check_true():
    client = OllamaClient()
    with patch("requests.get") as mock_get:
        mock_get.return_value.status_code = 200
        assert client.is_server_available() is True


def test_ollama_client_health_check_false():
    client = OllamaClient()
    with patch("requests.get", side_effect=requests.ConnectionError):
        assert client.is_server_available() is False


def test_ollama_client_list_models():
    client = OllamaClient()
    with patch("requests.get") as mock_get:
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = {
            "models": [{"name": "qwen3:8b"}, {"name": "llama3:latest"}]
        }
        models = client.list_models()
        assert "qwen3:8b" in models
        assert client.is_model_available("qwen3:8b") is True
        assert client.is_model_available("unknown:model") is False


def test_ollama_client_payload_includes_think():
    client = OllamaClient(think_mode=False)
    with patch("requests.post") as mock_post:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.iter_lines.return_value = [b'{"message": {"content": "ok"}, "done": true}']
        mock_post.return_value = mock_resp

        tokens = list(client.chat_stream([{"role": "user", "content": "hi"}]))
        assert tokens == ["ok"]
        _, kwargs = mock_post.call_args
        assert kwargs["json"]["think"] is False


def test_ollama_client_connection_error():
    client = OllamaClient()
    with patch("requests.post", side_effect=requests.ConnectionError):
        with pytest.raises(OllamaConnectionError):
            list(client.chat_stream([{"role": "user", "content": "hi"}]))


def test_ollama_client_model_not_found():
    client = OllamaClient(model="nonexistent_model")
    with patch("requests.post") as mock_post:
        mock_post.return_value.status_code = 404
        with pytest.raises(OllamaModelNotFoundError):
            list(client.chat_stream([{"role": "user", "content": "hi"}]))
