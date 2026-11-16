#!/usr/bin/env python3
"""Quick end-to-end check for the bridge.

Usage:
  python test_api.py
  python test_api.py --base-url http://127.0.0.1:9000
  python test_api.py --model glm-5.3-flash-free
"""
import argparse
import json
import sys
import time
import urllib.request

PREFERRED = [
    "deepseek-v4.1-flash-free",
    "glm-5.3-flash-free",
    "minimax-m3.1-flash-free",
    "mimo-v2.6-flash-free",
    "big-pickle",
]


def post_json(url, body, timeout):
    data = json.dumps(body).encode()
    req = urllib.request.Request(
        url, data=data,
        headers={"Content-Type": "application/json", "Authorization": "Bearer test"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode())


def get_json(url, timeout):
    req = urllib.request.Request(url, headers={"Authorization": "Bearer test"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode())


def stream_chat(url, model, timeout):
    body = {
        "model": model,
        "stream": True,
        "messages": [{"role": "user", "content": "Count from 1 to 5, numbers only."}],
    }
    req = urllib.request.Request(
        url, data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json", "Authorization": "Bearer test"},
        method="POST",
    )
    text = ""
    with urllib.request.urlopen(req, timeout=timeout) as r:
        for raw in r:
            line = raw.decode("utf-8", "replace").strip()
            if not line.startswith("data: "):
                continue
            payload = line[6:]
            if payload == "[DONE]":
                break
            chunk = json.loads(payload)
            text += (chunk.get("choices") or [{}])[0].get("delta", {}).get("content") or ""
    return text


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-url", default="http://127.0.0.1:8790")
    ap.add_argument("--model", default=None)
    ap.add_argument("--timeout", type=int, default=180)
    args = ap.parse_args()
    base = args.base_url.rstrip("/")
    if not base.endswith("/v1"):
        base += "/v1"

    failed = False
    print("== health ==")
    try:
        health = get_json(base[:-3] + "/health", 10)
        print("OK:", health)
    except Exception as e:
        print("FAIL:", e)
        print("\nIs the bridge running? Start it with start.bat / ./start.sh.")
        return 1

    print("\n== GET /v1/models ==")
    try:
        models = get_json(base + "/models", args.timeout).get("data") or []
        ids = [m.get("id") for m in models if isinstance(m, dict)]
        free = [m for m in ids if m and (m.endswith("-free") or m == "big-pickle")]
        print(f"OK: {len(ids)} models ({len(free)} free)")
        for m in free[:20]:
            print("  -", m)
        if len(free) > 20:
            print(f"  ... and {len(free) - 20} more")
    except Exception as e:
        print("FAIL:", e)
        return 1

    model = args.model or next((m for m in PREFERRED if m in ids), None)
    if not model:
        model = free[0] if free else (ids[0] if ids else None)
    if not model:
        print("FAIL: no model available to test")
        return 1

    print(f"\n== POST /v1/chat/completions (non-stream, model={model}) ==")
    t0 = time.time()
    try:
        r = post_json(base + "/chat/completions", {
            "model": model,
            "messages": [{"role": "user", "content": "Say hello in one short sentence."}],
        }, args.timeout)
        text = ((r.get("choices") or [{}])[0].get("message") or {}).get("content") or ""
        print(f"OK in {time.time() - t0:.1f}s: {text[:200]!r}")
        if not text.strip():
            print("WARN: the reply is empty")
    except Exception as e:
        print("FAIL:", e)
        failed = True

    print(f"\n== POST /v1/chat/completions (stream, model={model}) ==")
    t0 = time.time()
    try:
        text = stream_chat(base + "/chat/completions", model, args.timeout)
        print(f"OK in {time.time() - t0:.1f}s: {text[:200]!r}")
        if not text.strip():
            print("WARN: the streamed reply is empty")
    except Exception as e:
        print("FAIL:", e)
        failed = True

    print("\nAll checks passed." if not failed else "\nSome checks failed; see above.")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
