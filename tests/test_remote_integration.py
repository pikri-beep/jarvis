"""Unit and Integration Tests for PocketDesk Remote <-> JARVIS integration."""

import base64
import io
import json
import urllib.request
import numpy as np
import pytest
from unittest.mock import MagicMock, patch

from app.core.router import CommandRouter, RouteType
from app.core.handlers.fast_command_handler import handle_fast_command
from app.core.remote_gateway import (
    audio_to_wav_base64,
    start_remote_gateway,
    stop_remote_gateway,
    is_gateway_running,
)
from app.tools.remote_server import (
    get_local_ip,
    is_remote_server_running,
    get_remote_server_status,
)


class TestRemoteServerTools:
    """Tests for app/tools/remote_server.py"""

    def test_get_local_ip(self):
        ip = get_local_ip()
        assert isinstance(ip, str)
        assert len(ip.split(".")) == 4

    def test_get_remote_server_status(self):
        status = get_remote_server_status()
        assert isinstance(status, dict)
        assert "running" in status
        assert "port" in status
        assert "local_ip" in status
        assert "url" in status
        assert status["port"] == 8000


class TestRemoteRouterIntegration:
    """Tests for routing 'nyalakan remote', 'matikan remote', and 'status remote'."""

    @pytest.fixture
    def router(self):
        return CommandRouter()

    def test_route_start_remote(self, router):
        queries = [
            "nyalakan remote",
            "start remote",
            "aktifkan remote server",
            "jalankan remote",
            "buka remote",
        ]
        for q in queries:
            route = router.route(q)
            assert route.route_type == RouteType.FAST_COMMAND, f"Failed for {q}"
            assert route.action == "start_remote_server", f"Failed action for {q}"

    def test_route_stop_remote(self, router):
        queries = [
            "matikan remote",
            "stop remote",
            "hentikan remote server",
            "tutup remote",
        ]
        for q in queries:
            route = router.route(q)
            assert route.route_type == RouteType.FAST_COMMAND, f"Failed for {q}"
            assert route.action == "stop_remote_server", f"Failed action for {q}"

    def test_route_status_remote(self, router):
        queries = [
            "status remote",
            "cek remote",
            "apakah remote aktif",
        ]
        for q in queries:
            route = router.route(q)
            assert route.route_type == RouteType.FAST_COMMAND, f"Failed for {q}"
            assert route.action == "get_remote_server_status", f"Failed action for {q}"


class TestRemoteFastCommandHandler:
    """Tests for executing remote server fast commands."""

    def test_execute_status_command(self):
        orch = MagicMock()
        route = MagicMock()
        route.action = "get_remote_server_status"
        route.args = {}
        _, gen = handle_fast_command(orch, route, "status remote", "id", True)
        result = "".join(list(gen))
        assert "PocketDesk Remote" in result

    @patch("app.tools.remote_server.start_remote_server")
    def test_execute_start_command(self, mock_start):
        mock_start.return_value = (
            True,
            "http://192.168.1.10:8000/remote",
            "Server PocketDesk Remote berhasil diaktifkan di http://192.168.1.10:8000/remote, sir.",
        )
        orch = MagicMock()
        route = MagicMock()
        route.action = "start_remote_server"
        route.args = {}
        _, gen = handle_fast_command(orch, route, "nyalakan remote", "id", True)
        result = "".join(list(gen))
        assert "PocketDesk Remote" in result
        assert "http://192.168.1.10:8000/remote" in result

    @patch("app.tools.remote_server.stop_remote_server")
    def test_execute_stop_command(self, mock_stop):
        mock_stop.return_value = (
            True,
            "Server PocketDesk Remote telah dinonaktifkan, sir.",
        )
        orch = MagicMock()
        route = MagicMock()
        route.action = "stop_remote_server"
        route.args = {}
        _, gen = handle_fast_command(orch, route, "matikan remote", "id", True)
        result = "".join(list(gen))
        assert "telah dinonaktifkan" in result


class TestRemoteGatewayIPC:
    """Tests for the local IPC gateway server (app/core/remote_gateway.py)."""

    def test_audio_to_wav_base64(self):
        # Generate 0.1s synthetic audio
        sr = 16000
        samples = (np.sin(2 * np.pi * 440 * np.linspace(0, 0.1, 1600)) * 30000).astype(np.int16)
        b64_str = audio_to_wav_base64(samples, sr)
        assert isinstance(b64_str, str)
        wav_bytes = base64.b64decode(b64_str)
        assert wav_bytes.startswith(b"RIFF")
        assert b"WAVE" in wav_bytes

    def test_gateway_server_lifecycle_and_endpoints(self):
        # Create mock orchestrator
        mock_orch = MagicMock()
        mock_orch.settings.model = "qwen3:8b"
        mock_orch.state.conversation_language = "id"

        route_mock = MagicMock()
        route_mock.action = "chat"
        route_mock.route_type.name = "AI"
        mock_orch.process_command.side_effect = lambda text: (
            route_mock,
            iter(["Halo ", "sir, ", "ada yang bisa saya bantu?"]),
        )

        # Mock STT
        mock_stt = MagicMock()
        mock_stt.transcribe.return_value = ("buka chrome", {})
        mock_orch.get_stt.return_value = mock_stt

        # Mock TTS
        mock_tts = MagicMock()
        fake_audio = np.zeros(1600, dtype=np.int16)
        mock_tts.synthesize.return_value = (fake_audio, 16000)
        mock_orch.get_tts.return_value = mock_tts

        test_port = 8799
        started = start_remote_gateway(mock_orch, port=test_port)
        assert started is True
        assert is_gateway_running(test_port) is True

        try:
            # 1. Test GET /api/status
            req = urllib.request.Request(f"http://127.0.0.1:{test_port}/api/status")
            with urllib.request.urlopen(req, timeout=2.0) as resp:
                assert resp.status == 200
                data = json.loads(resp.read().decode("utf-8"))
                assert data["online"] is True
                assert data["name"] == "JARVIS"
                assert data["model"] == "qwen3:8b"

            # 2. Test POST /api/process (Laptop audio target)
            proc_payload = json.dumps({"text": "halo jarvis", "audio_target": "laptop"}).encode("utf-8")
            req = urllib.request.Request(
                f"http://127.0.0.1:{test_port}/api/process",
                data=proc_payload,
                headers={"Content-Type": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=2.0) as resp:
                assert resp.status == 200
                data = json.loads(resp.read().decode("utf-8"))
                assert data["success"] is True
                assert "Halo sir" in data["reply"]
                assert data["audio_base64"] == ""  # Not requested for laptop

            # 3. Test POST /api/process (Phone audio target -> synthesizes WAV)
            proc_phone_payload = json.dumps({"text": "halo jarvis", "audio_target": "phone"}).encode("utf-8")
            req = urllib.request.Request(
                f"http://127.0.0.1:{test_port}/api/process",
                data=proc_phone_payload,
                headers={"Content-Type": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=2.0) as resp:
                assert resp.status == 200
                data = json.loads(resp.read().decode("utf-8"))
                assert data["success"] is True
                assert len(data["audio_base64"]) > 0

            # 4. Test POST /api/transcribe
            import scipy.io.wavfile
            wav_buf = io.BytesIO()
            scipy.io.wavfile.write(wav_buf, 16000, fake_audio)
            wav_bytes = wav_buf.getvalue()

            req = urllib.request.Request(
                f"http://127.0.0.1:{test_port}/api/transcribe",
                data=wav_bytes,
                headers={"Content-Type": "audio/wav"},
            )
            with urllib.request.urlopen(req, timeout=2.0) as resp:
                assert resp.status == 200
                data = json.loads(resp.read().decode("utf-8"))
                assert data["success"] is True
                assert data["transcription"] == "buka chrome"

        finally:
            stop_remote_gateway()
