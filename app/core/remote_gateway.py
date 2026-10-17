"""Local IPC Gateway for JARVIS <-> PocketDesk Remote integration.

Exposes a lightweight, thread-safe HTTP server on 127.0.0.1:8765 enabling
the PocketDesk Remote web application to query status, submit commands,
stream audio responses, and transcribe mobile audio recordings.
"""

import base64
import io
import json
import socket
import threading
import time
import wave
from http.server import BaseHTTPRequestHandler, HTTPServer
from socketserver import ThreadingMixIn
from typing import Any, Optional

import numpy as np
import scipy.io.wavfile

from app.core.logger import setup_logger

logger = setup_logger("jarvis.core.remote_gateway")

GATEWAY_PORT = 8765
_SERVER_INSTANCE: Optional["ThreadingGatewayServer"] = None
_SERVER_THREAD: Optional[threading.Thread] = None


def audio_to_wav_base64(audio_int16: np.ndarray, sample_rate: int) -> str:
    """Encodes int16 NumPy audio array into a base64-encoded WAV string."""
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)  # 16-bit
        wf.setframerate(sample_rate)
        wf.writeframes(audio_int16.tobytes())
    return base64.b64encode(buf.getvalue()).decode("utf-8")


class ThreadingGatewayServer(ThreadingMixIn, HTTPServer):
    """Multi-threaded local HTTP server for JARVIS remote IPC."""
    daemon_threads = True

    def __init__(self, server_address, RequestHandlerClass, orchestrator: Any):
        super().__init__(server_address, RequestHandlerClass)
        self.orchestrator = orchestrator


class GatewayRequestHandler(BaseHTTPRequestHandler):
    """Handles IPC requests from PocketDesk Remote."""

    def log_message(self, format, *args):
        # Quiet standard HTTP access logging to keep console clean
        logger.debug("[GATEWAY-IPC] %s", format % args)

    def _send_json(self, status_code: int, data: dict):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self):
        orch = getattr(self.server, "orchestrator", None)
        if self.path == "/api/status":
            model_name = getattr(orch.settings, "model", "qwen3:8b") if orch else "unknown"
            lang = getattr(getattr(orch, "state", None), "conversation_language", "id") if orch else "id"
            self._send_json(200, {
                "online": True,
                "name": "JARVIS",
                "version": "2.5",
                "model": model_name,
                "language": lang,
            })
        else:
            self._send_json(404, {"error": "Endpoint not found"})

    def do_POST(self):
        orch = getattr(self.server, "orchestrator", None)
        if not orch:
            self._send_json(503, {"error": "JARVIS Orchestrator not ready"})
            return

        content_length = int(self.headers.get("Content-Length", 0))

        if self.path == "/api/process":
            try:
                body = self.rfile.read(content_length)
                req_data = json.loads(body.decode("utf-8"))
                user_text = req_data.get("text", "").strip()
                audio_target = req_data.get("audio_target", "laptop").lower()

                if not user_text:
                    self._send_json(400, {"error": "Empty text prompt"})
                    return

                logger.info('[GATEWAY-IPC] Processing command: "%s" (audio_target=%s)', user_text, audio_target)

                # Execute command via JARVIS Orchestrator
                t0 = time.time()
                route, gen = orch.process_command(user_text)
                reply_chunks = list(gen)
                full_reply = "".join(reply_chunks).strip()
                elapsed = time.time() - t0

                audio_b64 = ""
                sr = 0

                # Synthesize audio to stream back to phone if audio_target == "phone"
                if audio_target == "phone" and full_reply:
                    try:
                        tts = orch.get_tts()
                        if tts:
                            audio_arr, sr = tts.synthesize(full_reply)
                            if audio_arr is not None and len(audio_arr) > 0:
                                audio_b64 = audio_to_wav_base64(audio_arr, sr)
                    except Exception as e:
                        logger.warning("[GATEWAY-IPC] Failed synthesizing mobile audio: %s", e)

                self._send_json(200, {
                    "success": True,
                    "reply": full_reply,
                    "action": getattr(route, "action", "chat"),
                    "route_type": getattr(route.route_type, "name", str(route.route_type)),
                    "audio_base64": audio_b64,
                    "sample_rate": sr,
                    "elapsed_ms": round(elapsed * 1000, 1),
                })
            except Exception as exc:
                logger.error("[GATEWAY-IPC] Process error: %s", exc, exc_info=True)
                self._send_json(500, {"error": str(exc)})

        elif self.path == "/api/transcribe":
            try:
                raw_bytes = self.rfile.read(content_length)
                if not raw_bytes:
                    self._send_json(400, {"error": "Empty audio payload"})
                    return

                # Decode audio from in-memory WAV buffer
                try:
                    sr, audio_arr = scipy.io.wavfile.read(io.BytesIO(raw_bytes))
                except Exception as wav_exc:
                    logger.warning("[GATEWAY-IPC] Failed reading WAV stream: %s", wav_exc)
                    self._send_json(400, {"error": f"Invalid WAV format: {wav_exc}"})
                    return

                if audio_arr.ndim > 1:
                    audio_arr = np.mean(audio_arr, axis=1)

                stt = orch.get_stt()
                if not stt:
                    self._send_json(503, {"error": "STT engine not available"})
                    return

                transcription, _ = stt.transcribe(audio_arr, sample_rate=sr)
                logger.info('[GATEWAY-IPC] Audio transcribed: "%s"', transcription)
                self._send_json(200, {
                    "success": True,
                    "transcription": transcription,
                })
            except Exception as exc:
                logger.error("[GATEWAY-IPC] Transcribe error: %s", exc, exc_info=True)
                self._send_json(500, {"error": str(exc)})

        else:
            self._send_json(404, {"error": "Endpoint not found"})


def is_gateway_running(port: int = GATEWAY_PORT) -> bool:
    """Checks if the local gateway server is actively listening."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(0.5)
            return s.connect_ex(("127.0.0.1", port)) == 0
    except Exception:
        return False


def start_remote_gateway(orchestrator: Any, port: int = GATEWAY_PORT) -> bool:
    """Starts the background IPC gateway server if not already running."""
    global _SERVER_INSTANCE, _SERVER_THREAD

    if is_gateway_running(port):
        logger.info("Remote gateway is already running on port %d", port)
        return True

    try:
        _SERVER_INSTANCE = ThreadingGatewayServer(("127.0.0.1", port), GatewayRequestHandler, orchestrator)
        _SERVER_THREAD = threading.Thread(target=_SERVER_INSTANCE.serve_forever, daemon=True, name="JarvisRemoteGateway")
        _SERVER_THREAD.start()
        logger.info("JARVIS Remote IPC Gateway started on http://127.0.0.1:%d", port)
        return True
    except Exception as exc:
        logger.error("Failed to start JARVIS Remote Gateway: %s", exc)
        return False


def stop_remote_gateway() -> None:
    """Shuts down the background IPC gateway server."""
    global _SERVER_INSTANCE, _SERVER_THREAD
    if _SERVER_INSTANCE:
        try:
            _SERVER_INSTANCE.shutdown()
            _SERVER_INSTANCE.server_close()
        except Exception:
            pass
        _SERVER_INSTANCE = None
    _SERVER_THREAD = None
    logger.info("JARVIS Remote IPC Gateway stopped.")
