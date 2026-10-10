"""Unit and integration tests for multi-turn conversation context and router guardrails."""

from unittest.mock import MagicMock, patch
import numpy as np
import pytest

from app.core.orchestrator import Orchestrator
from app.core.router import CommandRouter, RouteType
from app.core.state import Message, SessionState


def test_session_state_sliding_window():
    state = SessionState(max_history_messages=6)
    for i in range(10):
        state.add_message("user", f"query {i}")
        state.add_message("assistant", f"answer {i}")

    # Should only keep the last 6 messages
    assert len(state.history) == 6
    assert state.history[0].content == "query 7"
    assert state.history[-1].content == "answer 9"


def test_session_state_last_action_context():
    state = SessionState()
    state.set_last_action("open_application", "chrome", "Google Chrome", True)
    assert state.get_last_action_target() == "chrome"
    assert state.get_last_action_display_name() == "Google Chrome"

    state.clear()
    assert state.get_last_action_target() is None


def test_router_prevents_accidental_app_launch_in_conversation():
    router = CommandRouter()

    # Negation: user explicitly asks NOT to open
    res_neg1 = router.route("Jangan buka Chrome")
    assert res_neg1.route_type == RouteType.AI_REQUEST

    res_neg2 = router.route("Don't open WhatsApp")
    assert res_neg2.route_type == RouteType.AI_REQUEST

    res_neg3 = router.route("Tidak usah buka notepad")
    assert res_neg3.route_type == RouteType.AI_REQUEST

    # Questions / how-to / explanatory inquiries mentioning apps
    res_q1 = router.route("Bagaimana cara buka WhatsApp di PC?")
    assert res_q1.route_type == RouteType.AI_REQUEST

    res_q2 = router.route("How to open Chrome in incognito mode?")
    assert res_q2.route_type == RouteType.AI_REQUEST

    res_q3 = router.route("Kenapa Chrome memakan banyak RAM?")
    assert res_q3.route_type == RouteType.AI_REQUEST

    res_q4 = router.route("Apa perbedaan antara Chrome dan Edge?")
    assert res_q4.route_type == RouteType.AI_REQUEST

    # Non-application uses of 'buka' or 'open'
    res_topic = router.route("Buka diskusi tentang kecerdasan buatan")
    assert res_topic.route_type == RouteType.AI_REQUEST

    res_debate = router.route("Open a new debate on philosophy")
    assert res_debate.route_type == RouteType.AI_REQUEST

    res_door = router.route("Buka pintu dan jendela")
    assert res_door.route_type == RouteType.AI_REQUEST

    # Genuine commands MUST still trigger FAST_COMMAND
    res_cmd1 = router.route("Buka Chrome")
    assert res_cmd1.route_type == RouteType.FAST_COMMAND
    assert res_cmd1.args.get("target") == "chrome"

    res_cmd2 = router.route("Tolong buka WhatsApp")
    assert res_cmd2.route_type == RouteType.FAST_COMMAND
    assert res_cmd2.args.get("target") == "whatsapp"

    res_cmd3 = router.route("Open Settings")
    assert res_cmd3.route_type == RouteType.FAST_COMMAND
    assert res_cmd3.args.get("target") == "settings"


def test_orchestrator_fast_command_records_turn_in_context():
    orchestrator = Orchestrator()
    with patch("app.tools.apps.launch_application", return_value=(True, "Google Chrome", "Berhasil")):
        route, stream = orchestrator.process_input_stream("Open Chrome")
        list(stream)

        # Fast command must be recorded into session history
        assert len(orchestrator.state.history) == 2
        assert orchestrator.state.history[0].role == "user"
        assert orchestrator.state.history[0].content == "Open Chrome"
        assert orchestrator.state.history[1].role == "assistant"
        assert "Opening Google Chrome, sir." in orchestrator.state.history[1].content
        assert orchestrator.state.get_last_action_target() == "chrome"


def test_orchestrator_follow_up_pronoun_close_resolution():
    orchestrator = Orchestrator()
    with patch("app.tools.apps.launch_application", return_value=(True, "Google Chrome", "Berhasil")), \
         patch("app.tools.apps.close_application", return_value=(True, "Google Chrome", "Berhasil menutup")):

        # Turn 1: Open Chrome
        route1, stream1 = orchestrator.process_input_stream("Buka Chrome")
        list(stream1)
        assert orchestrator.state.get_last_action_target() == "chrome"

        # Turn 2: Follow-up command "Tutup aplikasinya" should resolve to chrome
        route2, stream2 = orchestrator.process_input_stream("Tutup aplikasinya")
        output2 = "".join(list(stream2))
        assert "Menutup Google Chrome, sir." in output2


def test_orchestrator_multi_turn_llm_context():
    orchestrator = Orchestrator()
    mock_llm = MagicMock()
    mock_llm.chat_stream.side_effect = [
        iter(["RAM ", "is ", "memory."]),
        iter(["SSD ", "is ", "storage."]),
    ]
    orchestrator.llm = mock_llm

    # Turn 1
    _, stream1 = orchestrator.process_input_stream("Explain RAM")
    reply1 = "".join(list(stream1))
    assert reply1 == "RAM is memory."

    # Turn 2: Follow-up
    _, stream2 = orchestrator.process_input_stream("Now explain SSD")
    reply2 = "".join(list(stream2))
    assert reply2 == "SSD is storage."

    # Verify LLM received accumulated history on second call
    call_args_second = mock_llm.chat_stream.call_args_list[1][0][0]
    messages = [m for m in call_args_second if m.get("role") != "system"]
    assert len(messages) == 3
    assert messages[0] == {"role": "user", "content": "Explain RAM"}
    assert messages[1] == {"role": "assistant", "content": "RAM is memory."}
    assert messages[2] == {"role": "user", "content": "Now explain SSD"}


def test_language_consistency_and_hysteresis():
    orchestrator = Orchestrator()
    orchestrator.state.conversation_language = "id"

    # Turn 1: Indonesian with technical loanwords stays Indonesian
    route1, gen1 = orchestrator.process_input_stream("Bagaimana cara kerja RAM dan SSD di Windows 11?")
    assert orchestrator.state.conversation_language == "id"

    # Turn 2: Short follow-up query maintains Indonesian language
    route2, gen2 = orchestrator.process_input_stream("Berapa kecepatannya?")
    assert orchestrator.state.conversation_language == "id"

    # Turn 3: Single app mention or loanword doesn't flip language
    route3, gen3 = orchestrator.process_input_stream("Chrome")
    assert orchestrator.state.conversation_language == "id"

    # Turn 4: Explicit conversational switch to English
    route4, gen4 = orchestrator.process_input_stream("Switch to English, please.")
    assert orchestrator.state.conversation_language == "en"

    # Turn 5: English follow-up remains in English
    route5, gen5 = orchestrator.process_input_stream("Explain CPU cache briefly.")
    assert orchestrator.state.conversation_language == "en"

    # Turn 6: Explicit conversational switch back to Indonesian
    route6, gen6 = orchestrator.process_input_stream("Bicara bahasa Indonesia sekarang.")
    assert orchestrator.state.conversation_language == "id"


def test_voice_selection_strictly_matches_language():
    from app.voice.text_to_speech import TextToSpeech
    tts = TextToSpeech()

    mock_voice_en = MagicMock()
    mock_voice_en.config.sample_rate = 22050
    mock_chunk_en = MagicMock()
    mock_chunk_en.audio_int16_array = np.zeros(2205, dtype=np.int16)
    mock_voice_en.synthesize.return_value = [mock_chunk_en]

    mock_voice_id = MagicMock()
    mock_voice_id.config.sample_rate = 16000
    mock_chunk_id = MagicMock()
    mock_chunk_id.audio_int16_array = np.zeros(1600, dtype=np.int16)
    mock_voice_id.synthesize.return_value = [mock_chunk_id]

    tts._voices["en"] = mock_voice_en
    tts._voices["id"] = mock_voice_id

    # Indonesian text must synthesize via Indonesian voice
    tts.synthesize("Membuka Google Chrome, sir.", language="auto")
    mock_voice_id.synthesize.assert_called()

    # English text must synthesize via English voice
    tts.synthesize("Opening Google Chrome, sir.", language="auto")
    mock_voice_en.synthesize.assert_called()


def test_sensitive_action_confirmation_lifecycle():
    orchestrator = Orchestrator()
    with patch("app.tools.apps.launch_application") as mock_launch:
        mock_launch.return_value = (True, "WhatsApp", "Berhasil")

        # 1. Trigger sensitive WhatsApp launch -> Must ask for confirmation
        route1, gen1 = orchestrator.process_input_stream("Buka WhatsApp")
        out1 = "".join(list(gen1))
        assert "Apakah Anda yakin" in out1
        mock_launch.assert_not_called()
        assert orchestrator.state.pending_action is not None
        assert orchestrator.state.pending_action.target == "whatsapp"

        # 2. Confirm -> Action executed
        route2, gen2 = orchestrator.process_input_stream("Ya, lanjutkan")
        out2 = "".join(list(gen2))
        assert "Membuka WhatsApp, sir." in out2
        mock_launch.assert_called_with("whatsapp")
        assert orchestrator.state.pending_action is None

        # 3. Trigger sensitive WhatsApp launch again in English
        route3, gen3 = orchestrator.process_input_stream("Open WhatsApp")
        out3 = "".join(list(gen3))
        assert "access your personal messages" in out3 or "Membuka WhatsApp" in out3
        assert orchestrator.state.pending_action is not None

        # 4. Deny / Cancel -> Action cancelled
        route4, gen4 = orchestrator.process_input_stream("No, cancel")
        out4 = "".join(list(gen4))
        assert "cancelled" in out4.lower() or "dibatalkan" in out4.lower()
        assert orchestrator.state.pending_action is None


def test_deterministic_commands_bypass_llm():
    mock_llm = MagicMock()
    orchestrator = Orchestrator(llm_client=mock_llm)

    with patch("app.tools.apps.launch_application", return_value=(True, "Calculator", "Berhasil")):
        # Application command
        route_app, gen_app = orchestrator.process_input_stream("buka kalkulator")
        list(gen_app)
        assert route_app.route_type == RouteType.FAST_COMMAND
        mock_llm.chat_stream.assert_not_called()

        # System time command
        route_time, gen_time = orchestrator.process_input_stream("jam berapa sekarang?")
        list(gen_time)
        assert route_time.route_type == RouteType.FAST_COMMAND
        mock_llm.chat_stream.assert_not_called()
