"""Diagnostic script to measure Ollama and JARVIS latency, token counts, and thinking behavior."""

import json
import time
import requests

OLLAMA_URL = "http://localhost:11434"
MODEL = "qwen3:8b"


def test_ollama_raw(prompt="Hello", test_name="Default /api/chat"):
    print(f"\n{'='*20} {test_name} {'='*20}")
    t_start = time.time()
    
    payload = {
        "model": MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "stream": True,
        "keep_alive": "15m",
    }
    
    try:
        resp = requests.post(
            f"{OLLAMA_URL}/api/chat",
            json=payload,
            stream=True,
            timeout=120,
        )
    except Exception as e:
        print(f"Request failed: {e}")
        return

    first_token_time = None
    first_visible_content_time = None
    chunks_count = 0
    content_tokens = []
    reasoning_tokens = []
    final_stats = None

    for line in resp.iter_lines():
        if not line:
            continue
        chunks_count += 1
        data = json.loads(line)
        now = time.time() - t_start
        
        msg = data.get("message", {})
        c = msg.get("content", "")
        # Some versions use reasoning_content, others stream inside content with <think>
        r = msg.get("reasoning_content", "")
        
        if (c or r) and first_token_time is None:
            first_token_time = now
            
        if c:
            content_tokens.append(c)
            if first_visible_content_time is None and "<think>" not in c:
                first_visible_content_time = now
        if r:
            reasoning_tokens.append(r)
            
        if data.get("done"):
            final_stats = data

    t_total = time.time() - t_start
    full_content = "".join(content_tokens)
    full_reasoning = "".join(reasoning_tokens)

    print(f"Total elapsed:                {t_total:.2f} s")
    print(f"First chunk/token time:       {first_token_time if first_token_time is not None else -1:.2f} s")
    print(f"First visible content time:   {first_visible_content_time if first_visible_content_time is not None else -1:.2f} s")
    print(f"Total chunks:                 {chunks_count}")
    print(f"Content length (chars):       {len(full_content)}")
    print(f"Reasoning length (chars):     {len(full_reasoning)}")
    print(f"Content has <think>:          {'<think>' in full_content}")
    
    if final_stats:
        load_d = final_stats.get("load_duration", 0) / 1e9
        peval_c = final_stats.get("prompt_eval_count", 0)
        peval_d = final_stats.get("prompt_eval_duration", 0) / 1e9
        eval_c = final_stats.get("eval_count", 0)
        eval_d = final_stats.get("eval_duration", 0) / 1e9
        total_d = final_stats.get("total_duration", 0) / 1e9
        
        print("\nOllama Detailed Metrics:")
        print(f"  Model load duration:        {load_d:.3f} s")
        print(f"  Prompt eval count:          {peval_c} tokens")
        print(f"  Prompt eval duration:       {peval_d:.3f} s ({peval_c/peval_d if peval_d > 0 else 0:.1f} tok/s)")
        print(f"  Eval (generation) count:    {eval_c} tokens")
        print(f"  Eval (generation) duration: {eval_d:.3f} s ({eval_c/eval_d if eval_d > 0 else 0:.1f} tok/s)")
        print(f"  Reported total duration:    {total_d:.3f} s")
        
    print(f"\nResponse excerpt:\n{full_content[:200]}")
    if full_reasoning:
        print(f"\nReasoning excerpt:\n{full_reasoning[:200]}")


if __name__ == "__main__":
    test_ollama_raw("Hello")
