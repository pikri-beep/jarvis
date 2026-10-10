"""Post-fix verification benchmark for JARVIS Orchestrator."""

import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.core.orchestrator import Orchestrator

sys.stdout.reconfigure(encoding="utf-8")

orch = Orchestrator()
query = "Explain what you can do"
print(f"Running Optimized JARVIS Benchmark: {query!r}")

t0 = time.time()
first_token_time = None
tokens = []

route, gen = orch.process_input_stream(query)
for t in gen:
    if first_token_time is None:
        first_token_time = time.time() - t0
    tokens.append(t)
total_time = time.time() - t0

full_text = "".join(tokens)
print("=" * 50)
print(f"Time to First Spoken/Visible Token: {first_token_time:.2f} s")
print(f"Total Response Duration:            {total_time:.2f} s")
print(f"Total Streamed Tokens/Fragments:    {len(tokens)}")
print(f"Response Character Count:           {len(full_text)}")
print(f"Route Type:                         {route.route_type.name}")
print("=" * 50)
print("Response Output:")
print(full_text)
