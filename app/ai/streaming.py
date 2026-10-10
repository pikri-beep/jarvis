"""Streaming response utilities for JARVIS."""

from typing import Generator, Iterator


class StreamProcessor:
    """Processes streamed text chunks from the LLM, managing buffering and thinking blocks."""

    def __init__(self, strip_thinking: bool = True):
        self.strip_thinking = strip_thinking
        self._in_think_block = False
        self._buffer = ""

    def process_chunk(self, chunk: str) -> str:
        """Processes an incoming text fragment and returns printable output.

        Filters out `<think>...</think>` tags if present.
        """
        if not self.strip_thinking:
            return chunk

        self._buffer += chunk
        output = []

        while self._buffer:
            if not self._in_think_block:
                if "<think>" in self._buffer:
                    before, _, after = self._buffer.partition("<think>")
                    output.append(before)
                    self._buffer = after
                    self._in_think_block = True
                else:
                    # Check if buffer ends with a prefix of '<think>'
                    if any("<think>".startswith(self._buffer[-i:]) for i in range(1, len("<think>"))):
                        # Hold the potentially matching tail in buffer
                        break
                    output.append(self._buffer)
                    self._buffer = ""
            else:
                if "</think>" in self._buffer:
                    _, _, after = self._buffer.partition("</think>")
                    self._buffer = after
                    self._in_think_block = False
                else:
                    # Still inside thinking block, discard buffer content
                    self._buffer = ""
                    break

        return "".join(output)

    def flush(self) -> str:
        """Flushes any remaining text in buffer."""
        if not self._in_think_block:
            remaining = self._buffer
            self._buffer = ""
            return remaining
        self._buffer = ""
        return ""
