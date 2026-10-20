#!/usr/bin/env python3
"""Ask the agent a question over HTTP (stdlib only). Prints the answer and a JSON metrics line."""
import json
import sys
import time
import urllib.request

url, key, question = sys.argv[1], sys.argv[2], sys.argv[3]
req = urllib.request.Request(
    f"{url}/api/ask",
    data=json.dumps({"question": question}).encode(),
    headers={"Content-Type": "application/json", "X-API-Key": key},
)
t0 = time.perf_counter()
answer, cites, done = [], 0, {}
with urllib.request.urlopen(req, timeout=600) as r:
    for line in r:
        ev = json.loads(line)
        if ev["type"] == "citations":
            cites = len(ev["citations"])
        elif ev["type"] == "token":
            answer.append(ev["text"])
        elif ev["type"] == "done":
            done = ev
        elif ev["type"] == "error":
            sys.exit(f"agent error: {ev['message']}")
print("".join(answer).strip())
print(json.dumps({"citations": cites, "wall_s": round(time.perf_counter() - t0, 2), **done}), file=sys.stderr)
