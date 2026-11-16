#!/usr/bin/env python3
"""Probe every free model exposed by the bridge.

Usage:
  python test_free_models.py
  python test_free_models.py --quick
  python test_free_models.py --base-url http://127.0.0.1:9000

The list of free models changes upstream. This script reads /v1/models, keeps
ids ending in "-free" plus "big-pickle", and sends a tiny prompt to each one.
"""
import argparse
import json
import sys
import time
import urllib.request

FALLBACK = [
    "deepseek-v4.1-flash-free",
    "glm-5.3-flash-free",
    "minimax-m3.1-flash-free",
    "mimo-v2.6-flash-free",
    "big-pickle",
    "longcat-2.5-free",
    "iceman-free",
    "inkling-2-small-free",
    "flint-40b-free",
    "nemotron-3.5-super-vl-free",
    "nemotron-3.5-lightning-free",
    "hy4-flash-free",
]

QUICK = [
    "deepseek-v4.1-flash-free",
    "glm-5.3-flash-free",
    "minimax-m3.1-flash-free",
    "big-pickle",
]


def get_models(base, timeout):
    req = urllib.request.Request(base + "/models", headers={"Authorization": "Bearer test"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        data = json.loads(r.read().decode()).get("data") or []
    return [m.get("id") for m in data if isinstance(m, dict) and m.get("id")]


def probe(base, model, timeout):
    body = {
        "model": model,
        "messages": [{"role": "user", "content": "Reply with exactly one word: pong"}],
    }
    req = urllib.request.Request(
        base + "/chat/completions", data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json", "Authorization": "Bearer test"},
        method="POST",
    )
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            data = json.loads(r.read().decode())
        text = ((data.get("choices") or [{}])[0].get("message") or {}).get("content") or ""
        elapsed = time.time() - t0
        return ("EMPTY" if not text.strip() else "OK"), elapsed, text.strip().replace("\n", " ")[:60]
    except Exception as e:
        return "FAIL", time.time() - t0, str(e).replace("\n", " ")[:80]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-url", default="http://127.0.0.1:8790")
    ap.add_argument("--timeout", type=int, default=180)
    ap.add_argument("--quick", action="store_true", help="only test the recommended four")
    args = ap.parse_args()
    base = args.base_url.rstrip("/")
    if not base.endswith("/v1"):
        base += "/v1"

    try:
        ids = get_models(base, 60)
    except Exception as e:
        print("FAIL: could not read /v1/models:", e)
        print("Is the bridge running? Start it with start.bat / ./start.sh.")
        return 1

    models = [m for m in ids if m.endswith("-free") or m == "big-pickle"]
    if not models:
        print("WARN: no free models in /v1/models; using the built-in fallback list.")
        models = FALLBACK
    if args.quick:
        models = [m for m in QUICK if m in models or m in FALLBACK]

    print(f"Testing {len(models)} model(s) against {base}\n")
    print(f"{'model':34} {'status':6} {'time':>7}  reply")
    print("-" * 80)

    counts = {"OK": 0, "EMPTY": 0, "FAIL": 0}
    for model in models:
        status, elapsed, text = probe(base, model, args.timeout)
        counts[status] = counts.get(status, 0) + 1
        print(f"{model:34} {status:6} {elapsed:6.1f}s  {text}")

    print("-" * 80)
    print(f"OK: {counts['OK']}   EMPTY: {counts['EMPTY']}   FAIL: {counts['FAIL']}")
    print("Empty replies mean the model returned HTTP 200 but no text; pick another model.")
    print("A few FAILs are normal: free models are added/removed/region-gated upstream.")
    return 0 if counts["OK"] else 1


if __name__ == "__main__":
    sys.exit(main())
