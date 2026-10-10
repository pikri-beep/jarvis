import json
import sys
import time
import requests

sys.stdout.reconfigure(encoding="utf-8")

t0 = time.time()
resp = requests.post(
    "http://localhost:11434/api/chat",
    json={
        "model": "qwen3:8b",
        "messages": [{"role": "user", "content": "Hello"}],
        "think": False,
        "stream": True,
        "keep_alive": "15m",
    },
    stream=True,
)

first_content_t = None
content_tokens = []
thinking_tokens = []
final_data = None

for line in resp.iter_lines():
    if not line:
        continue
    d = json.loads(line)
    msg = d.get("message", {})
    c = msg.get("content", "")
    th = msg.get("thinking", "")
    if c:
        if first_content_t is None:
            first_content_t = time.time() - t0
        content_tokens.append(c)
    if th:
        thinking_tokens.append(th)
    if d.get("done"):
        final_data = d

total_t = time.time() - t0
print("--- think=False Test ---")
print(f"First content token:       {first_content_t:.2f} s")
print(f"Total time:                {total_t:.2f} s")
print(f"Thinking tokens count:     {len(thinking_tokens)}")
content_str = "".join(content_tokens)
print(f"Content:                   {content_str}")
if final_data:
    eval_c = final_data.get("eval_count", 0)
    eval_d = final_data.get("eval_duration", 0) / 1e9
    peval_c = final_data.get("prompt_eval_count", 0)
    peval_d = final_data.get("prompt_eval_duration", 0) / 1e9
    print(f"Prompt eval tokens:        {peval_c} in {peval_d:.3f} s")
    print(f"Eval generation tokens:    {eval_c} in {eval_d:.3f} s ({eval_c/eval_d if eval_d > 0 else 0:.1f} tok/s)")
