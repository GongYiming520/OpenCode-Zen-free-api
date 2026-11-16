# OpenCode Zen Free API

**English** | [简体中文](./README.md)

> Use **OpenCode Zen's free models** through a standard **OpenAI-compatible
> endpoint**. Point any OpenAI client at `http://127.0.0.1:8790/v1` and use a
> free model.

**Three steps:** download the project → double-click `start.bat` → fill in the
Base URL in your client.

---

## Contents

- [What works and what does not](#what-works-and-what-does-not)
- [How it works](#how-it-works)
- [Requirements](#requirements)
- [Quick start on Windows](#quick-start-on-windows)
- [macOS / Linux / Termux](#macos--linux--termux)
- [Client settings](#client-settings)
- [Models](#models)
- [Examples](#examples)
- [Background mode](#background-mode)
- [Options](#options)
- [API compatibility](#api-compatibility)
- [Troubleshooting](#troubleshooting)
- [Security and legal notes](#security-and-legal-notes)
- [Files](#files)

---

## What works and what does not

| Feature | Status |
|---|---|
| Text chat and multi-turn chat | ✅ |
| Custom `system` / `developer` prompt | ✅ forwarded |
| `GET /v1/models` | ✅ |
| `POST /v1/chat/completions` | ✅ |
| `stream: true` | ✅ standard SSE, but ⚠️ not token-by-token real-time |
| Tools / function calling | ❌ ignored |
| Image / audio input | ❌ only text parts are extracted |
| `temperature`, `top_p`, `max_tokens` | ⚠️ ignored, no error |
| `n > 1` | ❌ one choice only |
| `usage` token counts | ⚠️ always zero |
| `/v1/completions` | ❌ not implemented |
| API key validation | ❌ not checked; any non-empty string works |

**About streaming:** the bridge waits for the whole answer, then emits it as
proper SSE chunks. Clients parse it fine, but you will not see token-by-token
typing. If you need true streaming, this project does not provide it yet.

**About free quota:** the model list, rate limits and region rules are decided
by OpenCode Zen upstream and can change at any time.

---

## How it works

OpenCode Zen's free tier checks that the request comes from the **official
OpenCode client**. Direct third-party requests get:

```text
403 FreeTierError: OpenCode's free tier can only be used from within OpenCode
```

This project does not spoof headers. It starts a **real `opencode` process** and
uses it as the transport:

```text
your client (Cherry Studio / Chatbox / RikkaHub / OpenAI SDK / ...)
        │  POST /v1/chat/completions
        ▼
oc_bridge.py  (:8790)                 ← this project, stdlib only
        │  POST /session
        │  POST /session/{id}/message
        ▼
opencode serve (:4097)                ← official opencode binary
        │  POST /inference/v1/chat/completions
        ▼
OpenCode Zen gateway  ✅
```

See [`FINDINGS-2026-10-15.md`](./FINDINGS-2026-10-15.md) for the measurements
(Chinese).

---

## Requirements

| Dependency | Version | Purpose |
|---|---|---|
| Python | 3.8+ | runs `oc_bridge.py` (no third-party Python packages) |
| Node.js + npm | 18+ | installs opencode with `npm i -g opencode-ai` on first run |
| Network | access to `opencode.ai` and npm | download opencode and reach Zen |

Windows: install Python from <https://www.python.org/downloads/> (tick
**Add Python to PATH**) and Node.js LTS from <https://nodejs.org/>.

macOS / Linux:

```bash
python3 --version    # 3.8+
node --version       # 18+
npm --version
```

---

## Quick start on Windows

1. Download the repo: **Code → Download ZIP**, then extract it to a normal
   folder, e.g. `D:\OpenCode-Zen-free-api`.
2. Double-click **`start.bat`**.
   On first run it checks Python, installs opencode via npm if needed, creates
   an isolated `.opencode-home` directory, and starts the bridge.
3. Keep the window open. When you see this, it is ready:

```text
[bridge] OpenAI-compatible endpoint: http://127.0.0.1:8790/v1 ...
================================================================
  Base URL : http://127.0.0.1:8790/v1
  API Key  : any non-empty string (not checked)
  Model    : deepseek-v4.1-flash-free
  Health   : http://127.0.0.1:8790/health
  Stop     : Ctrl+C
================================================================
```

The first run can take 1–3 minutes (npm download + opencode initialization).
Later starts are much faster.

4. In your client:

| Setting | Value |
|---|---|
| Base URL | `http://127.0.0.1:8790/v1` |
| API Key | anything non-empty, e.g. `sk-anything` |
| Model | `deepseek-v4.1-flash-free` |

---

## macOS / Linux / Termux

```bash
git clone https://github.com/Fly143/OpenCode-Zen-free-api.git
cd OpenCode-Zen-free-api
chmod +x start.sh stop.sh
./start.sh
```

Background mode:

```bash
./start.sh --bg        # log: bridge.log, pid: .bridge.pid
./stop.sh
```

`--bg` must be the first argument, e.g. `./start.sh --bg --port 9000`.

Termux:

```bash
pkg install python nodejs
./start.sh
```

---

## Client settings

Any client that supports an OpenAI-compatible API should work:

- Provider type: `OpenAI` / `OpenAI Compatible`
- Base URL: `http://127.0.0.1:8790/v1`
- API Key: any non-empty string
- Model: any id from `/v1/models`, e.g. `deepseek-v4.1-flash-free`

Some clients add `/v1` automatically. If yours does, use
`http://127.0.0.1:8790` as the base.

If the client runs inside Docker, `127.0.0.1` points to the container. On
Docker Desktop use `http://host.docker.internal:8790/v1`. Do not expose the
bridge to the public internet.

---

## Models

List the current models:

```text
http://127.0.0.1:8790/v1/models
```

Verified free models on 2026-11-16 (this is **not** an allowlist; upstream
changes):

| Model | Status | Notes |
|---|---|---|
| `deepseek-v4.1-flash-free` | ✅ | recommended |
| `glm-5.3-flash-free` | ✅ | recommended |
| `minimax-m3.1-flash-free` | ✅ | recommended |
| `big-pickle` | ✅ | free, no `-free` suffix |
| `longcat-2.5-free` | ✅ | |
| `iceman-free` | ✅ | |
| `inkling-2-small-free` | ✅ | |
| `flint-40b-free` | ✅ | |
| `nemotron-3.5-super-vl-free` | ✅ | |
| `nemotron-3.5-lightning-free` | ✅ | |
| `hy4-flash-free` | ✅ | |
| `mimo-v2.6-flash-free` | ✅ | slow (~14s) |
| `beam-free` | ⚠️ | HTTP 200 but usually empty text |

If a model returns 404, 500, 403 RegionError, or empty text, pick another one.

---

## Examples

### Python

```bash
pip install openai
```

```python
from openai import OpenAI

client = OpenAI(base_url="http://127.0.0.1:8790/v1", api_key="sk-anything")
resp = client.chat.completions.create(
    model="deepseek-v4.1-flash-free",
    messages=[{"role": "user", "content": "Hello!"}],
)
print(resp.choices[0].message.content)
```

### Node.js

```bash
npm i openai
```

```js
import OpenAI from "openai";

const client = new OpenAI({
  baseURL: "http://127.0.0.1:8790/v1",
  apiKey: "sk-anything",
});

const resp = await client.chat.completions.create({
  model: "deepseek-v4.1-flash-free",
  messages: [{ role: "user", content: "Hello!" }],
});
console.log(resp.choices[0].message.content);
```

### curl

```bash
curl http://127.0.0.1:8790/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer sk-anything" \
  -d '{
    "model": "deepseek-v4.1-flash-free",
    "messages": [{"role": "user", "content": "Hello"}]
  }'
```

### Health check

```text
http://127.0.0.1:8790/health
```

Returns `{"ok": true}` when the bridge is alive.

---

## Background mode

### Windows

| Action | How |
|---|---|
| Foreground (recommended for beginners) | double-click `start.bat` |
| Background | double-click `start-zen.bat` |
| Stop background service | double-click `stop-zen.bat` |
| Logs | `bridge.log`, `bridge-err.log` |

`start-zen.bat` is idempotent: if the service is already running it only says
so and exits.

### macOS / Linux

| Action | Command |
|---|---|
| Foreground | `./start.sh` |
| Background | `./start.sh --bg` |
| Stop | `./stop.sh` |
| Logs | `tail -f bridge.log` |

To reset everything, stop the service and delete `.opencode-home`.

---

## Options

```bash
python oc_bridge.py --port 8790 --oc-port 4097
```

| Option | Default | Description |
|---|---|---|
| `--port` | `8790` | OpenAI-compatible endpoint port |
| `--oc-port` | `4097` | internal `opencode serve` port |
| `--opencode-bin` | auto | path to the opencode binary |
| `--home` | user's opencode dir | opencode HOME/data dir; launchers pass `.opencode-home` |
| `--mode` | `stateless` | `stateless`: new session per request; `stateful`: reuse by `X-Conversation-Id` / `X-Session-Id` |
| `--free-models` | no filter | comma-separated allowlist; 404 for other models |
| `--agent` | `bridge` | opencode agent; `bridge` is the injected minimal one |
| `--prompt` | `You are a helpful assistant.` | prompt for the `bridge` agent |
| `--full-prompt` | off | use opencode's full system prompt (~9.5 KB) |
| `--version` | — | print version |

The bridge injects a minimal `bridge` agent through
`OPENCODE_CONFIG_CONTENT`, merged with your existing `opencode.json` without
modifying it.

---

## API compatibility

Implemented:

- `GET /` — service info
- `GET /health` — health check
- `GET /v1/models` — upstream model list
- `GET /v1/models/{id}` — single model
- `POST /v1/chat/completions` — non-stream and SSE stream
- CORS enabled

Limitations:

- no tools / function calling
- no image or audio input
- sampling parameters are ignored
- `usage` is always zero
- streaming is buffered, not token-by-token
- stateless mode requires the client to resend full history

---

## Troubleshooting

### `Python 3 was not found`

Install Python 3.8+ and tick “Add Python to PATH”, then open a **new**
terminal.

### `Node.js / npm was not found`

Install Node.js LTS from <https://nodejs.org/> and open a new terminal.

### `npm i -g opencode-ai` is slow or fails

Check your network/proxy, or run it manually to see the full error. If opencode
is already installed elsewhere:

```bat
start.bat --opencode-bin "C:\path\to\opencode.exe"
```

### Port 8790 is already in use

```bat
start.bat --port 8791
```

Then set the client Base URL to `http://127.0.0.1:8791/v1`.

### The first request is very slow

Normal. `opencode serve` cold start takes 10–20 seconds; later requests are
2–5 seconds.

### `403 FreeTierError`

The upstream free-tier policy changed, or the request did not go through a real
opencode process. Make sure you started the bridge with `start.bat` /
`start-zen.bat`, not by reusing an unrelated `opencode serve`.

### `403 RegionError`

The model is not available from your region. Pick another model or change your
network egress.

### 500 / 502 / empty reply

Upstream model glitch. Try another model. `beam-free` is a known
“HTTP 200 but empty” model.

### `Database is not empty and has no session table`

You are reusing an old opencode database. The launchers use `.opencode-home`,
so this should not happen. If you run manually, add:

```bash
python oc_bridge.py --home .opencode-home
```

### Do I need to log in to opencode?

No for the free models (tested). For paid models, run `opencode auth login`
with the same `--home`.

### Can I expose it to other machines?

Not recommended: there is no authentication and the API key is not checked.
Anyone who can reach the port can consume your quota.

---

## Security and legal notes

- Listens on `127.0.0.1` only by default.
- No authentication; any local process can call it.
- Prompts are sent to OpenCode Zen through the official client.
- Not affiliated with OpenCode or OpenCode Zen.
- This is a grey-area use of the free tier. Heavy use may be blocked. Use an
  official paid key for anything serious.
- MIT licensed; OpenCode and Zen have their own terms.

---

## Files

| File | Purpose |
|---|---|
| `oc_bridge.py` | core bridge, Python stdlib only |
| `start.bat` | Windows one-click foreground launcher |
| `start-zen.bat` / `start-zen.ps1` | Windows background launcher |
| `stop-zen.bat` / `stop-zen.ps1` | Windows stop script |
| `start.sh` / `stop.sh` | Unix launcher and stop script |
| `test_api.py` / `test_api.bat` | quick health/models/chat/stream test |
| `test_free_models.py` / `test_free_models.bat` | probe every free model |
| `opencode.json.example` | optional manual agent config |
| `FINDINGS-2026-10-15.md` | design notes and measurements |
| `CHANGELOG.md` | change log |
| `.opencode-home/` | auto-created isolated opencode data dir (gitignored) |

---

## Development

No third-party Python dependencies:

```bash
python oc_bridge.py --port 8790 --oc-port 4097 --home .opencode-home
```

Run a quick regression:

```bash
python test_api.py
python test_free_models.py --quick
```

Repository: <https://github.com/Fly143/OpenCode-Zen-free-api>
