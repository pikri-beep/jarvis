"""Comprehensive benchmark script comparing Ollama and JARVIS latency with and without thinking mode."""

import json
import sys
import time
from pathlib import Path
import requests

# Ensure project root in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.core.config import get_settings
from app.core.orchestrator import Orchestrator
from app.ai.prompts import get_system_prompt

sys.stdout.reconfigure(encoding="utf-8")

settings = get_settings()
OLLAMA_URL = settings.ollama_url
MODEL = settings.model


def benchmark_direct_ollama(prompt: str, think_mode: bool, system_prompt: str = ""):
    print(f"\n{'='*25} Direct Ollama (think={think_mode}) {'='*25}")
    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})

    t_connect_start = time.time()
    # Check connection
    c_resp = requests.get(f"{OLLAMA_URL}/api/tags", timeout=5)
    connection_time = time.time() - t_connect_start

    t_req_start = time.time()
    payload = {
        "model": MODEL,
        "messages": messages,
        "stream": True,
        "keep_alive": "15m",
        "think": think_mode,
    }

    resp = requests.post(
        f"{OLLAMA_URL}/api/chat",
        json=payload,
        stream=True,
        timeout=180,
    )

    first_token_time = None
    first_content_time = None
    chunks_count = 0
    content_pieces = []
    thinking_pieces = []
    done_payload = None

    for line in resp.iter_lines():
        if not line:
            continue
        chunks_count += 1
        now = time.time() - t_req_start
        data = json.loads(line)
        msg = data.get("message", {})
        c = msg.get("content", "")
        th = msg.get("thinking", "")

        if (c or th) and first_token_time is None:
            first_token_time = now
        if c:
            if first_content_time is None:
                first_content_time = now
            content_pieces.append(c)
        if th:
            thinking_pieces.append(th)
        if data.get("done"):
            done_payload = data

    total_time = time.time() - t_req_start
    content_text = "".join(content_pieces)
    thinking_text = "".join(thinking_pieces)

    # Detailed metrics
    load_duration = (done_payload.get("load_duration", 0) / 1e9) if done_payload else 0
    prompt_tokens = done_payload.get("prompt_eval_count", 0) if done_payload else 0
    prompt_duration = (done_payload.get("prompt_eval_duration", 0) / 1e9) if done_payload else 0
    gen_tokens = done_payload.get("eval_count", 0) if done_payload else 0
    gen_duration = (done_payload.get("eval_duration", 0) / 1e9) if done_payload else 0
    tok_per_sec = (gen_tokens / gen_duration) if gen_duration > 0 else 0

    print(f"Ollama Connection Time:        {connection_time*1000:.2f} ms")
    print(f"Model Load Duration:           {load_duration:.3f} s")
    print(f"Prompt Evaluation:             {prompt_tokens} tokens in {prompt_duration:.3f} s")
    print(f"Time to First Chunk (any):     {first_token_time if first_token_time else -1:.2f} s")
    print(f"Time to First Content Token:   {first_content_time if first_content_time else -1:.2f} s")
    print(f"Total Stream Chunks:           {chunks_count}")
    print(f"Thinking Tokens Generated:     {len(thinking_pieces)} chunks (~{len(thinking_text.split())} words)")
    print(f"Content Tokens Generated:      {len(content_pieces)} chunks (~{len(content_text.split())} words)")
    print(f"Total Eval Tokens:             {gen_tokens} tokens in {gen_duration:.3f} s ({tok_per_sec:.2f} tok/s)")
    print(f"Total Request Time:            {total_time:.2f} s")
    print(f"Response Excerpt:              {content_text[:120]!r}")

    return {
        "think_mode": think_mode,
        "connection_ms": connection_time * 1000,
        "load_s": load_duration,
        "prompt_tokens": prompt_tokens,
        "prompt_eval_s": prompt_duration,
        "first_token_s": first_token_time,
        "first_content_s": first_content_time,
        "gen_tokens": gen_tokens,
        "gen_duration_s": gen_duration,
        "tok_per_sec": tok_per_sec,
        "total_time_s": total_time,
        "thinking_chunks": len(thinking_pieces),
        "content_chunks": len(content_pieces),
    }


def benchmark_jarvis_orchestrator(prompt: str):
    print(f"\n{'='*25} Current JARVIS Orchestrator {'='*25}")
    orchestrator = Orchestrator()
    t0 = time.time()
    first_token_t = None
    tokens = []

    route, stream_gen = orchestrator.process_input_stream(prompt)
    for tok in stream_gen:
        if first_token_t is None:
            first_token_t = time.time() - t0
        tokens.append(tok)
    total_t = time.time() - t0

    full_resp = "".join(tokens)
    print(f"Route Type:                    {route.route_type.name}")
    print(f"Time to First Displayed Token: {first_token_t if first_token_t else -1:.2f} s")
    print(f"Total Time:                    {total_t:.2f} s")
    print(f"Tokens/Deltas Received:        {len(tokens)}")
    print(f"Response Excerpt:              {full_resp[:120]!r}")

    return {
        "first_token_s": first_token_t,
        "total_time_s": total_t,
        "tokens_count": len(tokens),
    }


if __name__ == "__main__":
    test_query = "Explain what you can do"
    sys_prompt = get_system_prompt()

    print("Running Benchmark with Query:", repr(test_query))
    
    # 1. Direct Ollama WITH thinking (default behavior)
    res_think = benchmark_direct_ollama(test_query, think_mode=True, system_prompt=sys_prompt)
    
    # 2. Direct Ollama WITHOUT thinking (think=False)
    res_nothink = benchmark_direct_ollama(test_query, think_mode=False, system_prompt=sys_prompt)
    
    # 3. JARVIS Current Orchestrator
    res_jarvis = benchmark_jarvis_orchestrator(test_query)
