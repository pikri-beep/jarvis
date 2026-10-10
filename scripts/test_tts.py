"""Test and verification script for Piper Text-to-Speech (TTS)."""

import sys
import time
from pathlib import Path

# Ensure project root is in sys.path
_PROJECT_ROOT = str(Path(__file__).resolve().parent.parent)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from app.core.config import get_settings
from app.voice.text_to_speech import TextToSpeech, clean_text_for_speech


def run_tts_tests():
    print("=" * 64)
    print("      JARVIS LOCAL TEXT-TO-SPEECH (TTS) TEST SUITE")
    print("=" * 64)

    settings = get_settings()
    tts = TextToSpeech(settings=settings)

    # 1. Test clean_text_for_speech
    print("\n--- Test 1: Markdown and Formatting Cleaning ---")
    dirty = "### Heading\n**Hello** `world`! Visit https://example.com for info. > Quote\n```code snippet```"
    cleaned = clean_text_for_speech(dirty)
    print(f"Original:\n{dirty}")
    print(f"Cleaned:\n\"{cleaned}\"")
    assert "code snippet" not in cleaned
    assert "https://" not in cleaned
    print("Clean text test PASSED.")

    # 2. Test Empty and Punctuation-Only Synthesis
    print("\n--- Test 2: Edge Cases (Empty, Whitespace, Punctuation) ---")
    edge_cases = ["", "   ", "...", "---", "!?!", "###", "   \n\n\t  "]
    for ec in edge_cases:
        audio, sr = tts.synthesize(ec)
        assert audio is None, f"Expected None for {ec!r}, got audio array"
    print("Edge cases (empty/punctuation) PASSED - returned None gracefully.")

    # 3. Test English Synthesis
    print("\n--- Test 3: Short English Synthesis ---")
    en_text = "Good evening, sir. All systems are operational."
    t0 = time.time()
    audio_en, sr_en = tts.synthesize(en_text, language="en")
    synth_time_en = time.time() - t0
    assert audio_en is not None and len(audio_en) > 0
    dur_en = len(audio_en) / sr_en
    print(f"Text: \"{en_text}\"")
    print(f"Audio: {dur_en:.2f}s generated in {synth_time_en:.3f}s (Rate: {sr_en} Hz, RTF: {synth_time_en/dur_en:.2f}x)")
    print("English synthesis PASSED.")

    # 4. Test Indonesian Synthesis
    print("\n--- Test 4: Short Indonesian Synthesis ---")
    id_text = "Selamat malam, sir. Sistem JARVIS siap membantu Anda."
    t0 = time.time()
    audio_id, sr_id = tts.synthesize(id_text, language="id")
    synth_time_id = time.time() - t0
    assert audio_id is not None and len(audio_id) > 0
    dur_id = len(audio_id) / sr_id
    print(f"Text: \"{id_text}\"")
    print(f"Audio: {dur_id:.2f}s generated in {synth_time_id:.3f}s (Rate: {sr_id} Hz, RTF: {synth_time_id/dur_id:.2f}x)")
    print("Indonesian synthesis PASSED.")

    # 5. Test Sentence-Buffered Streaming Simulation
    print("\n--- Test 5: Sentence-Buffered Streaming Simulation ---")
    simulated_tokens = [
        "Certainly, ", "sir. ", "Here ", "is ", "the ", "requested ", "information. ",
        "The ", "JARVIS ", "system ", "is ", "fully ", "operational."
    ]

    def _token_gen():
        for tok in simulated_tokens:
            time.sleep(0.04)  # Simulate token generation pacing (~25 tok/s)
            yield tok

    printed_tokens = []
    t_stream_0 = time.time()
    stats = tts.speak_stream(
        _token_gen(),
        language="en",
        on_token=lambda tok: printed_tokens.append(tok),
    )
    stream_elapsed = time.time() - t_stream_0
    print(f"Tokens streamed: {''.join(printed_tokens)}")
    print(f"Time to First Audio (TTFA): {stats['ttfa']:.3f}s")
    print(f"Total Speech Duration:      {stats['total_speech_s']:.2f}s")
    print(f"Sentences Synthesized:      {stats['sentences_count']}")
    print(f"Streaming Process Time:     {stream_elapsed:.3f}s")
    print("Sentence-buffered streaming PASSED.")

    # Drain queue
    tts.stop()
    print("\n" + "=" * 64)
    print("ALL TTS UNIT AND FUNCTIONAL TESTS PASSED!")
    print("=" * 64)


if __name__ == "__main__":
    run_tts_tests()
