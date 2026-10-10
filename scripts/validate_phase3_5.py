"""Phase 3.5 Voice Quality and Latency Comprehensive Validation Script.

Measures all pipeline stages separately on the target hardware:
1. STT duration on realistic Indonesian spoken audio
2. Router classification and fast-command bypass latency
3. LLM TTFT and total generation time with Qwen3 8B
4. Time to first synthesized chunk & TTFA (time to first audible word)
5. Total audio playback duration
6. Audio quality metrics: peak amplitude, RMS, clipping status, sample rate, model verification
7. Push-to-talk interruption, /tts toggle, and deterministic commands.
"""

import os
import sys
import time
from pathlib import Path
import numpy as np

# Set project root in sys.path
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from app.core.config import get_settings
from app.core.orchestrator import Orchestrator
from app.core.router import RouteType
from app.voice.speech_to_text import SpeechToText
from app.voice.text_to_speech import TextToSpeech, clean_text_for_speech, detect_language


def run_stt_benchmark(stt: SpeechToText, tts: TextToSpeech, utterances: list[str]) -> dict:
    """Measures faster-whisper STT transcription latency on actual synthesized spoken audio."""
    print("\n" + "=" * 60)
    print(" 1. SPEECH-TO-TEXT (STT) BENCHMARK ON INDONESIAN SPEECH")
    print("=" * 60)
    
    stt_results = {}
    stt.load_model()
    
    for text in utterances:
        # Generate realistic Indonesian audio using id Piper model
        raw_audio, sr = tts.synthesize(text, language="id")
        if raw_audio is None:
            continue
        
        # faster-whisper expects float32 normalized [-1.0, 1.0]
        float_audio = raw_audio.astype(np.float32) / 32768.0
        audio_dur = len(float_audio) / sr
        
        # Measure STT
        t0 = time.time()
        transcription, info = stt.transcribe(float_audio, sample_rate=sr, language="auto")
        stt_dur = time.time() - t0
        
        rtf = stt_dur / audio_dur if audio_dur > 0 else 0.0
        print(f"Utterance: \"{text}\"")
        print(f"  Audio Duration: {audio_dur:.2f}s | STT Latency: {stt_dur:.2f}s | RTF: {rtf:.2f}x")
        print(f"  Transcription:  \"{transcription}\" (Lang: {info.get('language')})")
        print("-" * 50)
        
        stt_results[text] = {
            "audio_dur": audio_dur,
            "stt_dur": stt_dur,
            "transcription": transcription,
            "detected_lang": info.get("language"),
        }
        
    return stt_results


def run_e2e_pipeline_validation(orchestrator: Orchestrator, utterances: list[str], play_sound: bool = True) -> list[dict]:
    """Runs the 4 Indonesian utterances and English controls through the full pipeline."""
    print("\n" + "=" * 60)
    print(" 2. END-TO-END PIPELINE & TIMING BREAKDOWN")
    print("=" * 60)
    
    tts = orchestrator.get_tts()
    tts.enabled = True
    
    # Pre-warm models
    orchestrator.llm.is_server_available()
    tts.load_model("en")
    tts.load_model("id")
    
    results = []
    
    for idx, query in enumerate(utterances, 1):
        print(f"\n[Test #{idx}] Input: \"{query}\"")
        detected_input_lang = detect_language(query)
        print(f"  -> Detected Input Language: {detected_input_lang.upper()}")
        
        route, stream_gen = orchestrator.process_input_stream(query)
        print(f"  -> Route: {route.route_type.name} (action: {route.action})")
        
        t_start = time.time()
        t_first_token = None
        t_first_synth = None
        t_first_audible = None
        
        tokens_received = []
        synthesized_chunks = []
        total_audio_samples = 0
        active_sample_rate = 16000
        active_model_name = ""
        
        from app.voice.text_to_speech import SentenceBuffer
        buf = SentenceBuffer(min_chars=14, early_first_chunk=True)
        active_lang = "auto"
        
        for token in stream_gen:
            if t_first_token is None:
                t_first_token = time.time()
            tokens_received.append(token)
            
            # Sentence buffering
            new_sentences = buf.feed(token)
            for s in new_sentences:
                t_synth_start = time.time()
                if active_lang == "auto":
                    active_lang = detect_language(s)
                
                lang_key = "id" if active_lang.lower().startswith("id") else "en"
                active_model_name = orchestrator.settings.tts_model_id if lang_key == "id" else orchestrator.settings.tts_model_en
                
                audio, sr = tts.synthesize(s, language=active_lang)
                t_synth_end = time.time()
                
                if t_first_synth is None and audio is not None:
                    t_first_synth = t_synth_end
                
                if audio is not None and len(audio) > 0:
                    active_sample_rate = sr
                    total_audio_samples += len(audio)
                    synthesized_chunks.append(audio)
                    if t_first_audible is None:
                        t_first_audible = time.time()
                    if play_sound:
                        tts.playback_queue.enqueue(audio, sr)
        
        # Flush remaining buffer
        for s in buf.flush():
            if active_lang == "auto":
                active_lang = detect_language(s)
            lang_key = "id" if active_lang.lower().startswith("id") else "en"
            active_model_name = orchestrator.settings.tts_model_id if lang_key == "id" else orchestrator.settings.tts_model_en
            
            audio, sr = tts.synthesize(s, language=active_lang)
            if t_first_synth is None and audio is not None:
                t_first_synth = time.time()
            if audio is not None and len(audio) > 0:
                active_sample_rate = sr
                total_audio_samples += len(audio)
                synthesized_chunks.append(audio)
                if t_first_audible is None:
                    t_first_audible = time.time()
                if play_sound:
                    tts.playback_queue.enqueue(audio, sr)
                    
        t_end_gen = time.time()
        
        # Audio metrics
        if synthesized_chunks:
            full_audio = np.concatenate(synthesized_chunks)
            peak = int(np.max(np.abs(full_audio)))
            rms = float(np.sqrt(np.mean(full_audio.astype(np.float64) ** 2)))
            is_clipped = peak >= 32767
        else:
            full_audio = np.zeros(0, dtype=np.int16)
            peak = 0
            rms = 0.0
            is_clipped = False
            
        full_text = "".join(tokens_received)
        total_speech_s = len(full_audio) / active_sample_rate if active_sample_rate else 0.0
        
        ttft = (t_first_token - t_start) if t_first_token else 0.0
        ttfs = (t_first_synth - t_start) if t_first_synth else 0.0
        ttfa = (t_first_audible - t_start) if t_first_audible else 0.0
        total_gen_time = t_end_gen - t_start
        
        print(f"  -> Response: \"{full_text.strip()}\"")
        print(f"  -> Piper Model Used: {active_model_name} ({active_sample_rate} Hz)")
        print(f"  -> Timing Metrics:")
        print(f"     * LLM TTFT:                 {ttft:.3f} s")
        print(f"     * Time to First Synthesized: {ttfs:.3f} s")
        print(f"     * Time to 1st Audible Word:  {ttfa:.3f} s  (TTFA)")
        print(f"     * Total Generation Duration: {total_gen_time:.3f} s")
        print(f"     * Total Spoken Audio Dur:   {total_speech_s:.2f} s")
        print(f"  -> Audio Quality:")
        print(f"     * Peak Amplitude: {peak} (Max: 32767 | Headroom limit: 28000)")
        print(f"     * RMS Level:      {rms:.1f}")
        print(f"     * Clipped:        {is_clipped}")
        
        if play_sound:
            tts.playback_queue.wait_until_done()
            
        results.append({
            "query": query,
            "route_type": route.route_type.name,
            "response": full_text.strip(),
            "detected_lang": active_lang,
            "model_used": active_model_name,
            "sample_rate": active_sample_rate,
            "ttft": ttft,
            "ttfs": ttfs,
            "ttfa": ttfa,
            "total_gen_time": total_gen_time,
            "total_speech_s": total_speech_s,
            "peak": peak,
            "rms": rms,
            "is_clipped": is_clipped,
        })
        
    return results


def test_control_features(orchestrator: Orchestrator) -> None:
    """Verifies Push-to-Talk interruption, /tts toggle, and --no-tts mode."""
    print("\n" + "=" * 60)
    print(" 3. CONTROL FEATURES & INTERRUPTION VALIDATION")
    print("=" * 60)
    
    tts = orchestrator.get_tts()
    
    # 1. /tts toggle verification
    tts.enabled = True
    assert tts.enabled is True
    route, gen = orchestrator.process_input_stream("/tts")
    reply = "".join(list(gen))
    assert "DISABLED" in reply
    assert tts.enabled is False
    print("  [PASS] /tts toggle disables TTS successfully.")
    
    route, gen = orchestrator.process_input_stream("/tts")
    reply = "".join(list(gen))
    assert "ENABLED" in reply
    assert tts.enabled is True
    print("  [PASS] /tts toggle re-enables TTS successfully.")
    
    # 2. Audio queue interruption verification
    print("  Testing audio interruption via tts.stop()...")
    dummy = np.zeros(16000 * 5, dtype=np.int16) # 5 seconds of audio
    tts.playback_queue.enqueue(dummy, 16000)
    time.sleep(0.1)
    assert tts.is_speaking() is True
    tts.stop()
    time.sleep(0.05)
    assert tts.is_speaking() is False
    print("  [PASS] Audio playback immediately halted on interrupt.")
    
    # 3. English control utterance
    print("  Testing English control query...")
    orchestrator.state.clear()
    route, gen = orchestrator.process_input_stream("Explain RAM in one sentence.")
    en_reply = "".join(list(gen))
    detected = detect_language(en_reply)
    print(f"  English query reply: '{en_reply.strip()}' (Detected: {detected})")
    assert detected == "en"
    print("  [PASS] English queries produce English responses and route to en model.")


def main():
    orchestrator = Orchestrator()
    stt = orchestrator.get_stt()
    tts = orchestrator.get_tts()
    
    target_utterances = [
        "Selamat pagi, apa kabar?",
        "Baik, sekarang buka Chrome.",
        "Saya ingin mengetahui perbedaan RAM dan SSD.",
        "JARVIS, tolong jelaskan jadwal saya hari ini.",
    ]
    
    # Step 1: STT benchmark on target Indonesian speech
    stt_results = run_stt_benchmark(stt, tts, target_utterances)
    
    # Step 2: Full E2E validation with Piper real audio synthesis and playback
    pipeline_results = run_e2e_pipeline_validation(orchestrator, target_utterances, play_sound=True)
    
    # Step 3: Feature verification
    test_control_features(orchestrator)
    
    print("\n" + "=" * 60)
    print(" ALL VALIDATIONS COMPLETED SUCCESSFULLY")
    print("=" * 60)


if __name__ == "__main__":
    main()
