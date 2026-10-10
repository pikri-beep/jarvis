"""Phase 3.8 Latency & Sentence-Buffered TTS Benchmarking Script.

Measures independently:
1. LLM TTFT (Time to First Token)
2. Generation Time
3. TTFA (Time to First Audio synthesized and queued for playback)
4. Full Response End-to-End Latency
5. Output Token count and tok/s throughput
6. Sentence-buffered streaming concurrency (first sentence speech vs remaining generation)
"""

import sys
import time
from pathlib import Path

# Ensure project root is in sys.path
_PROJECT_ROOT = str(Path(__file__).resolve().parent.parent)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from app.core.config import get_settings
from app.core.orchestrator import Orchestrator
from app.voice.text_to_speech import SentenceBuffer


def run_benchmark():
    settings = get_settings()
    orchestrator = Orchestrator(settings=settings)

    print(f"Connecting to Ollama model '{settings.model}'...")
    if not orchestrator.llm.is_server_available():
        print("[ERROR] Ollama server is not running at", settings.ollama_url)
        return
    if not orchestrator.llm.is_model_available():
        print(f"[ERROR] Model '{settings.model}' not found in Ollama.")
        return

    # Pre-warm TTS model
    tts = orchestrator.get_tts()
    tts.load_model("id")
    tts.load_model("en")
    print("Piper TTS models loaded.\n")

    test_queries = [
        # Query 1: Standard Conversational Greeting / Status (Indonesian)
        {
            "category": "Conversational Greeting (ID)",
            "query": "Selamat pagi Jarvis, apa kabar?",
            "lang": "id",
        },
        # Query 2: Technical Explanation (Indonesian)
        {
            "category": "Technical Explanation (ID)",
            "query": "Jelaskan perbedaan utama RAM dan SSD dalam komputer.",
            "lang": "id",
        },
        # Query 3: Multi-point Tips (English)
        {
            "category": "Productivity Tips (EN)",
            "query": "Give me three productivity tips for Windows 11.",
            "lang": "en",
        },
        # Query 4: Follow-up reasoning (English)
        {
            "category": "Follow-up Query (EN)",
            "query": "Which of those tips is the easiest to set up?",
            "lang": "en",
        },
    ]

    results = []

    for item in test_queries:
        query = item["query"]
        category = item["category"]
        print("=" * 70)
        print(f"Benchmark: {category}")
        print(f"Query: \"{query}\"")
        print("-" * 70)

        t_start = time.time()
        ttft = None
        ttfa = None
        tokens = []
        sentences_emitted = []
        sentence_timings = []

        route, token_gen = orchestrator.process_input_stream(query)

        buf = SentenceBuffer(min_chars=14, early_first_chunk=True)
        active_lang = orchestrator.state.conversation_language

        for token in token_gen:
            t_tok = time.time()
            if ttft is None:
                ttft = t_tok - t_start

            tokens.append(token)
            print(token, end="", flush=True)

            new_sents = buf.feed(token)
            for s in new_sents:
                t_sent = time.time() - t_start
                sentences_emitted.append(s)
                # Synthesize first sentence to measure TTFA
                t_synth_start = time.time()
                audio, sr = tts.synthesize(s, language=active_lang)
                t_synth_dur = time.time() - t_synth_start
                if ttfa is None and audio is not None and len(audio) > 0:
                    ttfa = time.time() - t_start
                sentence_timings.append((s, t_sent, t_synth_dur))

        # Flush trailing fragment
        remaining = buf.flush()
        for s in remaining:
            t_sent = time.time() - t_start
            sentences_emitted.append(s)
            t_synth_start = time.time()
            audio, sr = tts.synthesize(s, language=active_lang)
            t_synth_dur = time.time() - t_synth_start
            sentence_timings.append((s, t_sent, t_synth_dur))

        t_end = time.time()
        print("\n")

        total_latency = t_end - t_start
        gen_duration = max(0.0, total_latency - (ttft or 0))
        num_tokens = len(tokens)
        throughput = (num_tokens / gen_duration) if gen_duration > 0 else 0.0

        res = {
            "category": category,
            "query": query,
            "ttft": ttft or 0.0,
            "generation_time": gen_duration,
            "ttfa": ttfa or 0.0,
            "total_latency": total_latency,
            "num_tokens": num_tokens,
            "throughput": throughput,
            "response": "".join(tokens),
            "sentences": sentence_timings,
        }
        results.append(res)

        print(f"Metrics:")
        print(f"  TTFT (First Token):    {res['ttft']:.3f} s")
        print(f"  Generation Time:       {res['generation_time']:.3f} s")
        print(f"  TTFA (First Audio):    {res['ttfa']:.3f} s")
        print(f"  Total Latency:         {res['total_latency']:.3f} s")
        print(f"  Output Tokens:         {res['num_tokens']} tokens ({res['throughput']:.2f} tok/s)")
        print(f"  Sentence 1 vs End Gap: {res['total_latency'] - res['ttfa']:.3f} s (Audio plays while LLM still generates!)")
        print()

    print("=" * 70)
    print("PHASE 3.8 BENCHMARK SUMMARY")
    print("=" * 70)
    for r in results:
        print(f"- {r['category']}:")
        print(f"    TTFT: {r['ttft']:.2f}s | TTFA: {r['ttfa']:.2f}s | Gen: {r['generation_time']:.2f}s | Total: {r['total_latency']:.2f}s | Tokens: {r['num_tokens']}")


if __name__ == "__main__":
    run_benchmark()
