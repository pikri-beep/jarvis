"""JARVIS - Terminal Conversation Interface (Phase 1-4 Entry Point)."""

import argparse
import queue
import sys
import threading
import time
from pathlib import Path
from typing import Any, Dict, Optional

import numpy as np

# Ensure project root is in sys.path when running app/main.py directly
_PROJECT_ROOT = str(Path(__file__).resolve().parent.parent)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

# Auto-switch to project virtual environment if invoked with global Python
_venv_python = Path(_PROJECT_ROOT) / ".venv" / "Scripts" / "python.exe"
if _venv_python.exists():
    try:
        if Path(sys.executable).resolve() != _venv_python.resolve():
            import subprocess
            sys.exit(subprocess.call([str(_venv_python)] + sys.argv))
    except Exception:
        pass

# Ensure UTF-8 output on Windows console
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except AttributeError:
        pass

from app.core.config import get_settings
from app.core.logger import setup_logger
from app.core.orchestrator import Orchestrator
from app.core.router import RouteType
from app.voice.audio_recorder import PushToTalkRecorder
from app.voice.wake_word import WakeWordDetector, WakeWordState

logger = setup_logger("jarvis.main", log_to_console=False)


def print_banner(orchestrator: Orchestrator, wake_active: bool, ptt_active: bool) -> None:
    """Displays startup welcome banner and system diagnostics."""
    status = orchestrator.get_system_status()
    llm_enabled = orchestrator.settings.llm_enabled
    if llm_enabled:
        ollama_status = "Connected" if status["ollama_connected"] else "Offline"
        model_status = "Available" if status["model_ready"] else "Not Found"
        model_display = f"{status['model']} [{model_status}]"
        ollama_display = f"{status['ollama_url']} [{ollama_status}]"
    else:
        model_display = "Desktop Automation Engine [Deterministic Zero-LLM Routing]"
        ollama_display = "Disabled / Isolated (Routine Actions Bypassed)"
    
    wake_status = (
        f"Active [Model: {status.get('wake_word_model', 'hey_jarvis_v0.1.onnx')} | Trigger: 'Hey Jarvis']"
        if wake_active
        else "Standby (type '/wake' to activate)"
    )
    voice_status = f"Active [Model: {status['stt_model']}]" if ptt_active else "Standby (type '/ptt' to activate)"
    tts_status = f"Active [Model: {status['tts_model']}]" if status.get("tts_enabled") else "Disabled (type '/tts' to toggle)"

    print("=" * 66)
    print(f"        {status['name'].upper()} - Local AI Personal Assistant")
    print("=" * 66)
    print(f" Engine:        {model_display}")
    print(f" LLM Status:    {ollama_display}")
    print(f" Wake Word:     {wake_status}")
    print(f" Voice (PTT):   {voice_status}")
    print(f" Speech (TTS):  {tts_status}")
    print(" Commands:      '/wake' wake word | '/ptt' voice | '/tts' audio | '/exit' quit")
    print("-" * 66)

    if llm_enabled:
        if not status["ollama_connected"]:
            print("\n[WARNING] Could not connect to local Ollama server.")
            print("Please start Ollama using 'ollama serve' or the Windows app.\n")
        elif not status["model_ready"]:
            print(f"\n[WARNING] Model '{status['model']}' not found in Ollama.")
            print(f"Please run 'ollama pull {status['model']}' to install it.\n")


def execute_turn(
    orchestrator: Orchestrator,
    user_input: str,
    voice_metrics: dict = None,
    wake_detector: Optional[WakeWordDetector] = None,
) -> bool:
    """Processes a single conversational turn with streaming output and TTS playback.

    Returns:
        bool: True if the conversation should continue, False if exit was requested.
    """
    t_start = time.time()
    route, stream_gen = orchestrator.process_input_stream(user_input)

    ttft = None
    print(f"\n{orchestrator.settings.jarvis_name} > ", end="", flush=True)

    def _handle_token(token: str) -> None:
        nonlocal ttft
        if ttft is None:
            ttft = time.time() - t_start
        print(token, end="", flush=True)

    tts_stats = None
    tts_engine = orchestrator.get_tts() if orchestrator.settings.tts_enabled else None

    # Route to streaming TTS if speech output is enabled
    if tts_engine and tts_engine.enabled and route.route_type != RouteType.TERMINAL_COMMAND:
        if wake_detector:
            wake_detector.set_state(WakeWordState.SPEAKING)
        tts_lang = (
            orchestrator.settings.tts_language_mode
            if orchestrator.settings.tts_language_mode != "auto"
            else orchestrator.state.conversation_language
        )
        tts_stats = tts_engine.speak_stream(
            stream_gen,
            language=tts_lang,
            on_token=_handle_token,
        )
    else:
        for token in stream_gen:
            _handle_token(token)

    t_end = time.time()
    print()

    # Block until spoken response audio finishes playing
    if tts_engine and tts_engine.enabled:
        tts_engine.wait_until_done()

    # Output latency metrics breakdown if voice input or audio output was used
    if voice_metrics or (tts_stats and tts_stats.get("total_speech_s", 0) > 0):
        rec_dur = voice_metrics.get("rec_duration", 0.0) if voice_metrics else 0.0
        stt_dur = voice_metrics.get("stt_time", 0.0) if voice_metrics else 0.0
        gen_duration = max(0.0, t_end - t_start - (ttft or 0))
        ttft_val = ttft if ttft is not None else 0.0
        ttfa_val = tts_stats.get("ttfa", 0.0) if tts_stats else 0.0
        speech_dur = tts_stats.get("total_speech_s", 0.0) if tts_stats else 0.0
        e2e_total = stt_dur + (t_end - t_start)
        print(f"  [⏱️ Pipeline: Rec: {rec_dur:.1f}s | STT: {stt_dur:.2f}s | TTFT: {ttft_val:.2f}s | TTFA: {ttfa_val:.2f}s | Gen: {gen_duration:.2f}s | Audio: {speech_dur:.1f}s | E2E: {e2e_total:.2f}s]")

    logger.info("[TURN] Completed turn for: \"%s\" (route=%s, action=%s, duration=%.2fs)", user_input, route.route, route.action, t_end - t_start)

    if route.action == "exit":
        if orchestrator.settings.tts_enabled:
            orchestrator.get_tts().stop()
        return False

    return True


def run_repl(
    orchestrator: Orchestrator,
    voice_enabled: bool = False,
    wake_enabled: bool = False,
) -> None:
    """Runs the interactive conversation loop supporting Text, Push-to-Talk, and Always-Listening Wake Word."""
    mode = "wake" if wake_enabled else ("ptt" if voice_enabled else "text")
    recorder: Optional[PushToTalkRecorder] = None
    wake_detector: Optional[WakeWordDetector] = None

    # Pre-warm TTS and STT in background if voice features enabled
    if orchestrator.settings.tts_enabled:
        threading.Thread(target=orchestrator.get_tts().load_model, daemon=True).start()
    if voice_enabled or wake_enabled:
        threading.Thread(target=orchestrator.get_stt().load_model, daemon=True).start()

    # Event queue for decoupling microphone wake events and console input
    event_queue: queue.Queue = queue.Queue()
    stop_event = threading.Event()

    def _on_wake_detected(score: float):
        print(f"\n  🔔 [WAKE WORD DETECTED: 'Jarvis' (confidence: {score:.2f})] Listening for command...", flush=True)

    def _on_barge_in():
        print(f"\n\r{' '*75}\r  ⚡ [BARGE-IN / STOP DETECTED] Interrupting speech...", flush=True)
        if orchestrator.settings.tts_enabled:
            orchestrator.get_tts().stop()

    def _on_silence_timeout():
        print(f"\r{' '*75}\r  [!] No speech detected. Returning to standby.\n", flush=True)
        _print_prompt()

    def _on_command_captured(audio: Any):
        event_queue.put(("voice", audio))

    # Initialize wake-word detector if starting in wake mode
    if mode == "wake":
        try:
            print("[Wake Word] Initializing offline detector for 'Jarvis'...")
            wake_detector = orchestrator.get_wake_word()
            wake_detector.on_wake_word = _on_wake_detected
            wake_detector.on_barge_in = _on_barge_in
            wake_detector.on_silence_timeout = _on_silence_timeout
            wake_detector.on_command_captured = _on_command_captured
            wake_detector.start()
            print("[Wake Word] Always-listening active! Speak 'Jarvis' or 'Hey Jarvis' anytime.\n")
        except Exception as e:
            print(f"[Wake Word Warning] Failed to start wake-word detector: {e}")
            mode = "ptt" if voice_enabled else "text"

    # Background thread reading user console input without blocking wake-word processing
    def _console_input_worker():
        while not stop_event.is_set():
            try:
                line = sys.stdin.readline()
                if not line:
                    event_queue.put(("eof", None))
                    break
                event_queue.put(("keyboard", line.strip()))
            except Exception:
                break

    input_thread = threading.Thread(target=_console_input_worker, name="ConsoleInputWorker", daemon=True)
    input_thread.start()

    print_banner(orchestrator, wake_active=(mode == "wake"), ptt_active=(mode == "ptt"))

    auto_listen_cancel = threading.Event()

    def _trigger_auto_listen_if_needed() -> None:
        """Starts a 6-second non-blocking auto-listen window if a task or clarification is awaiting user input."""
        needs_listen = (
            orchestrator.state.pending_vision_task is not None
            or orchestrator.state.pending_action is not None
        )
        if needs_listen and (mode in ("wake", "ptt") or orchestrator.settings.voice_enabled):
            auto_listen_cancel.clear()
            print("\n  [🎙️ Auto-listening 6s for your response, or type answer below] > ", end="", flush=True)

            def _timed_worker():
                try:
                    if wake_detector and mode == "wake":
                        wake_detector.pause(release_device=True)
                    timed_recorder = PushToTalkRecorder(device_index=orchestrator.settings.audio_device)
                    aud = timed_recorder.record_timed(max_duration=6.0, cancel_event=auto_listen_cancel)
                    if len(aud) > 0 and not auto_listen_cancel.is_set():
                        event_queue.put(("auto_voice", aud))
                    elif not auto_listen_cancel.is_set():
                        print(f"\r{' '*75}\r  [Waktu mendengarkan selesai. Silakan ketik atau bicara kapan saja.]\n", flush=True)
                        _print_prompt()
                except Exception as e:
                    logger.debug("Auto-listen worker error: %s", e)
                finally:
                    if wake_detector and mode == "wake":
                        wake_detector.resume()

            t = threading.Thread(target=_timed_worker, name="AutoListenWorker", daemon=True)
            t.start()

    def _print_prompt():
        if mode == "wake":
            print("\nYou [🎙️ Listening for 'Hey Jarvis', or type command] > ", end="", flush=True)
        elif mode == "ptt":
            print("\nYou [🎙️ Press ENTER to speak, or type command] > ", end="", flush=True)
        else:
            print("\nYou > ", end="", flush=True)

    _print_prompt()

    try:
        while orchestrator.state.is_running and not stop_event.is_set():
            try:
                event_type, event_data = event_queue.get(timeout=0.1)
            except queue.Empty:
                continue

            if event_type == "eof":
                print("\n\nExiting JARVIS. Goodbye, sir.")
                break

            # EVENT 0: AUTO-LISTEN VOICE RESPONSE (Dual Mode 6s window)
            if event_type == "auto_voice":
                audio_data = event_data
                if len(audio_data) > 0:
                    transcription, info = orchestrator.transcribe_audio(audio_data)
                    if transcription:
                        lang_detected = info.get("language", "id")
                        print(f"\r{' '*75}\r  [🎙️ Voice Input ({lang_detected.upper()})]: \"{transcription}\"")
                        should_continue = execute_turn(orchestrator, transcription, wake_detector=wake_detector)
                        if not should_continue:
                            break
                        if orchestrator.state.pending_vision_task or orchestrator.state.pending_action:
                            _trigger_auto_listen_if_needed()
                        else:
                            _print_prompt()
                        continue
                _print_prompt()
                continue

            # EVENT A: VOICE COMMAND (Captured via Always-Listening Wake Word)
            if event_type == "voice":
                audio_data = event_data
                duration_s = len(audio_data) / 16000.0 if len(audio_data) > 0 else 0.0

                if len(audio_data) == 0:
                    if wake_detector:
                        wake_detector.resume()
                    _print_prompt()
                    continue

                print("\r  ■ [TRANSCRIBING...] Processing voice command...", end="", flush=True)
                if wake_detector and mode == "wake":
                    wake_detector.set_state(WakeWordState.TRANSCRIBING)
                t_stt_0 = time.time()
                transcription, info = orchestrator.transcribe_audio(audio_data)
                stt_time = time.time() - t_stt_0
                lang_detected = info.get("language", "id")

                if not transcription:
                    print(f"\r{' '*65}\r  [!] No speech detected. Returning to standby.\n")
                    if wake_detector:
                        wake_detector.resume()
                    _print_prompt()
                    continue

                peak = float(np.max(np.abs(audio_data))) if len(audio_data) > 0 else 0.0
                rms = float(np.sqrt(np.mean(audio_data ** 2))) if len(audio_data) > 0 else 0.0
                print(f"\r{' '*65}\r  [🎙️ Voice Input ({lang_detected.upper()})]: \"{transcription}\" (took {stt_time:.2f}s | Peak: {peak:.3f} | RMS: {rms:.3f})")

                metrics = {"rec_duration": duration_s, "stt_time": stt_time}
                try:
                    if wake_detector and mode == "wake":
                        wake_detector.set_state(WakeWordState.INTERPRETING)
                    should_continue = execute_turn(orchestrator, transcription, voice_metrics=metrics, wake_detector=wake_detector)
                finally:
                    # Guarantee resume of wake-word detection after spoken response completes or on error,
                    # unless barge-in has already transitioned to capturing the new user command
                    if wake_detector and mode == "wake":
                        if wake_detector.state not in (WakeWordState.WAITING_FOR_SPEECH, WakeWordState.RECORDING):
                            wake_detector.resume()

                if not should_continue:
                    break

                if orchestrator.state.pending_vision_task or orchestrator.state.pending_action:
                    _trigger_auto_listen_if_needed()
                else:
                    _print_prompt()
                continue

            # EVENT B: KEYBOARD INPUT
            elif event_type == "keyboard":
                auto_listen_cancel.set()
                user_input = event_data

                # Empty input in PTT mode -> Trigger microphone recording
                if not user_input and mode == "ptt":
                    if orchestrator.settings.tts_enabled:
                        orchestrator.get_tts().stop()

                    if recorder is None:
                        recorder = PushToTalkRecorder(device_index=orchestrator.settings.audio_device)

                    print("  ● [RECORDING...] Speak now. (Press ENTER when done) ", end="", flush=True)
                    recorder.start_recording()

                    # Wait for next ENTER in console queue
                    while True:
                        try:
                            ev_t, _ = event_queue.get(timeout=0.1)
                            if ev_t == "keyboard":
                                break
                            elif ev_t == "eof":
                                break
                        except queue.Empty:
                            continue

                    print("  ■ [TRANSCRIBING...] Processing audio...", end="", flush=True)
                    audio_data = recorder.stop_recording()
                    ptt_metrics = recorder.get_last_audio_metrics()
                    rec_duration = ptt_metrics.get("duration_s", 0.0)

                    if len(audio_data) == 0:
                        print(f"\r  [!] No audio captured. Type '/mic' to check devices.")
                        _print_prompt()
                        continue

                    peak_val = ptt_metrics.get("peak", 0.0)
                    rms_val = ptt_metrics.get("rms", 0.0)
                    if peak_val < 0.005 or rms_val < 0.001:
                        print(f"\r{' '*65}\r  [!] Audio level too low (Peak: {peak_val:.4f}, RMS: {rms_val:.4f}). Speak closer to microphone.")
                        _print_prompt()
                        continue

                    transcription, info = orchestrator.transcribe_audio(audio_data)
                    stt_time = info.get("transcription_time", 0.0)
                    lang_detected = info.get("language", "id")

                    if not transcription:
                        print(f"\r{' '*65}\r  [!] No speech detected. Please try again.")
                        _print_prompt()
                        continue

                    print(f"\r{' '*65}\r  [🎙️ Voice Input ({lang_detected.upper()})]: \"{transcription}\" (took {stt_time:.2f}s | Peak: {peak_val:.3f} | RMS: {rms_val:.3f})")
                    metrics = {"rec_duration": rec_duration, "stt_time": stt_time}
                    should_continue = execute_turn(orchestrator, transcription, voice_metrics=metrics)
                    if not should_continue:
                        break
                    if orchestrator.state.pending_vision_task or orchestrator.state.pending_action:
                        _trigger_auto_listen_if_needed()
                    else:
                        _print_prompt()
                    continue

                elif not user_input:
                    _print_prompt()
                    continue

                # Mode Toggle Commands
                low = user_input.lower()
                if low in ("/wake", "wake", "/wakeword", "wakeword"):
                    if mode == "wake":
                        if wake_detector:
                            wake_detector.stop()
                        mode = "text"
                        print("\n[Wake Word] Always-listening DISABLED. Switched to keyboard mode.")
                    else:
                        if recorder and recorder.is_recording:
                            recorder.stop_recording()
                        if wake_detector is None:
                            wake_detector = orchestrator.get_wake_word()
                            wake_detector.on_wake_word = _on_wake_detected
                            wake_detector.on_silence_timeout = _on_silence_timeout
                            wake_detector.on_command_captured = _on_command_captured
                        else:
                            wake_detector.on_silence_timeout = _on_silence_timeout
                        wake_detector.start()
                        mode = "wake"
                        print("\n[Wake Word] Always-listening ENABLED ('Hey Jarvis'). Speak anytime.")
                    _print_prompt()
                    continue

                if low in ("/voice", "/ptt", "voice", "ptt"):
                    if mode == "ptt":
                        mode = "text"
                        print("\n[Voice] Push-to-Talk mode DISABLED. Switched to keyboard-only mode.")
                    else:
                        if wake_detector:
                            wake_detector.stop()  # Release exclusive microphone hardware
                        if recorder is None:
                            recorder = PushToTalkRecorder(device_index=orchestrator.settings.audio_device)
                        orchestrator.get_stt().load_model()
                        mode = "ptt"
                        print("\n[Voice] Push-to-Talk mode ENABLED. Press ENTER on empty prompt to speak.")
                    _print_prompt()
                    continue

                # Standard text turn
                should_continue = execute_turn(orchestrator, user_input, wake_detector=wake_detector)
                if not should_continue:
                    break
                if orchestrator.state.pending_vision_task or orchestrator.state.pending_action:
                    _trigger_auto_listen_if_needed()
                else:
                    _print_prompt()
    except KeyboardInterrupt:
        print("\n\nOperation cancelled. Exiting JARVIS, sir.")
    finally:
        # Guaranteed cleanup upon exit or any exception
        stop_event.set()
        if recorder and getattr(recorder, "is_recording", False):
            try:
                recorder.stop_recording()
            except Exception:
                pass
        if wake_detector:
            wake_detector.cleanup()


def run_single_query(orchestrator: Orchestrator, query: str) -> None:
    """Runs a single query in non-interactive mode and prints the result."""
    _, stream_gen = orchestrator.process_input_stream(query)
    for token in stream_gen:
        print(token, end="", flush=True)
    print()


def main() -> None:
    """Main application entry point."""
    parser = argparse.ArgumentParser(description="JARVIS Local AI Personal Assistant")
    parser.add_argument(
        "--query", "-q",
        type=str,
        help="Run a single query non-interactively and exit.",
    )
    parser.add_argument(
        "--wake", "--always-listening",
        action="store_true",
        help="Launch directly in Always-Listening Wake-Word mode ('Hey Jarvis').",
    )
    parser.add_argument(
        "--voice", "--ptt",
        action="store_true",
        help="Launch directly in Push-to-Talk voice mode.",
    )
    parser.add_argument(
        "--no-tts",
        action="store_true",
        help="Disable spoken Text-to-Speech output.",
    )
    parser.add_argument(
        "--cli", "--terminal",
        action="store_true",
        help="Launch in terminal CLI / REPL mode instead of GUI.",
    )
    parser.add_argument(
        "--gui",
        action="store_true",
        help="Launch in Desktop GUI mode (default behavior).",
    )
    args = parser.parse_args()

    orchestrator = Orchestrator()
    from app.core.remote_gateway import start_remote_gateway
    start_remote_gateway(orchestrator)

    wake_enabled = args.wake or orchestrator.settings.wake_word_enabled
    voice_enabled = args.voice or orchestrator.settings.voice_enabled

    if args.no_tts:
        orchestrator.get_tts().enabled = False

    if args.query:
        run_single_query(orchestrator, args.query)
    elif args.cli:
        run_repl(orchestrator, voice_enabled=voice_enabled, wake_enabled=wake_enabled)
    else:
        try:
            from app.ui import run_gui
            sys.exit(run_gui(orchestrator))
        except Exception as e:
            logger.warning("Failed to start Desktop GUI (%s); falling back to terminal REPL", e)
            print(f"[NOTE] Falling back to terminal REPL mode: {e}")
            run_repl(orchestrator, voice_enabled=voice_enabled, wake_enabled=wake_enabled)


if __name__ == "__main__":
    main()
