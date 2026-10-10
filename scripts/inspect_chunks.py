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
        "messages": [{"role": "user", "content": "Hi"}],
        "stream": True,
        "keep_alive": "15m",
    },
    stream=True,
)

chunks = []
for line in resp.iter_lines():
    if not line:
        continue
    now = time.time() - t0
    d = json.loads(line)
    msg = d.get("message", {})
    chunks.append((now, d, msg))

print(f"Total chunks received: {len(chunks)}")
for idx, (t, d, msg) in enumerate(chunks):
    c = msg.get("content", "")
    r = msg.get("reasoning_content", "")
    # Print non-empty chunks or sample
    if idx < 5 or idx > len(chunks) - 5 or c != "":
        print(f"[{t:6.2f}s] #{idx:3d} content={c!r} reasoning={r!r} done={d.get('done')}")
        if c != "" and idx < 15:
            # show first non-empty content
            pass
