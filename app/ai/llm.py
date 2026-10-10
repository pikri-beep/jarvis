"""Local LLM client for Ollama."""

import json
import logging
from typing import Dict, Generator, List, Optional, Union

import requests

from app.ai.streaming import StreamProcessor
from app.core.logger import setup_logger

logger = setup_logger("jarvis.ai.llm")


class LLMError(Exception):
    """Base exception for LLM operations."""
    pass


class OllamaConnectionError(LLMError):
    """Raised when unable to connect to the Ollama server."""
    pass


class OllamaModelNotFoundError(LLMError):
    """Raised when the requested model is not found in Ollama."""
    pass


class OllamaClient:
    """Client for local Ollama server."""

    def __init__(
        self,
        base_url: str = "http://localhost:11434",
        model: str = "qwen3:8b",
        keep_alive: str = "15m",
        think_mode: bool = False,
        temperature: float = 0.7,
        timeout: int = 120,
    ):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.keep_alive = keep_alive
        self.think_mode = think_mode
        self.temperature = temperature
        self.timeout = timeout

    def is_server_available(self) -> bool:
        """Checks if the local Ollama daemon is responsive."""
        try:
            resp = requests.get(f"{self.base_url}/api/tags", timeout=3)
            return resp.status_code == 200
        except requests.RequestException:
            return False

    def list_models(self) -> List[str]:
        """Lists available models installed locally in Ollama."""
        try:
            resp = requests.get(f"{self.base_url}/api/tags", timeout=5)
            resp.raise_for_status()
            data = resp.json()
            return [m.get("name", "") for m in data.get("models", [])]
        except requests.RequestException as e:
            logger.error("Failed to list Ollama models: %s", e)
            raise OllamaConnectionError(
                f"Could not connect to Ollama server at {self.base_url}. "
                "Please verify Ollama is running."
            ) from e

    def is_model_available(self, model_name: Optional[str] = None) -> bool:
        """Checks if the specified model is installed."""
        target = model_name or self.model
        try:
            models = self.list_models()
            # Check exact match or base match (e.g. qwen3:8b or qwen3)
            return any(m == target or m.split(":")[0] == target.split(":")[0] for m in models)
        except LLMError:
            return False

    def chat_stream(
        self,
        messages: List[Dict[str, str]],
        temperature: Optional[float] = None,
        think_mode: Optional[bool] = None,
    ) -> Generator[str, None, None]:
        """Streams chat response tokens from Ollama."""
        endpoint = f"{self.base_url}/api/chat"
        eff_think = think_mode if think_mode is not None else self.think_mode
        payload = {
            "model": self.model,
            "messages": messages,
            "stream": True,
            "keep_alive": self.keep_alive,
            "think": eff_think,
            "options": {
                "temperature": temperature if temperature is not None else self.temperature,
            },
        }

        try:
            resp = requests.post(
                endpoint,
                json=payload,
                stream=True,
                timeout=(5, self.timeout),
            )
        except requests.ConnectionError as e:
            logger.error("Connection failed to Ollama: %s", e)
            raise OllamaConnectionError(
                f"Cannot connect to Ollama at {self.base_url}. Is Ollama running?"
            ) from e
        except requests.Timeout as e:
            logger.error("Timeout connecting to Ollama: %s", e)
            raise LLMError("Ollama response timed out.") from e

        if resp.status_code == 404:
            raise OllamaModelNotFoundError(
                f"Model '{self.model}' not found in Ollama. Run 'ollama pull {self.model}'."
            )
        elif resp.status_code != 200:
            raise LLMError(f"Ollama returned HTTP error {resp.status_code}: {resp.text}")

        processor = StreamProcessor(strip_thinking=True)

        try:
            for line in resp.iter_lines(decode_unicode=True):
                if not line:
                    continue
                try:
                    chunk = json.loads(line)
                except json.JSONDecodeError:
                    continue

                if chunk.get("error"):
                    raise LLMError(chunk["error"])

                delta = chunk.get("message", {}).get("content", "")
                if delta:
                    filtered = processor.process_chunk(delta)
                    if filtered:
                        yield filtered

                if chunk.get("done", False):
                    break

            remaining = processor.flush()
            if remaining:
                yield remaining

        except requests.RequestException as e:
            logger.error("Error reading stream from Ollama: %s", e)
            raise LLMError(f"Error during streaming response: {e}") from e

    def chat(
        self,
        messages: List[Dict[str, str]],
        temperature: Optional[float] = None,
        think_mode: Optional[bool] = None,
    ) -> str:
        """Generates a complete response (blocking until finished)."""
        chunks = []
        for token in self.chat_stream(messages, temperature=temperature, think_mode=think_mode):
            chunks.append(token)
        return "".join(chunks)
