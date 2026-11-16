#!/usr/bin/env python3
"""
oc_bridge.py —— 把「真实 opencode 客户端」变成 OpenAI 兼容端点。

思路（2026-10-15）：Zen 免费额度的闸门挡的是客户端本身，任何"模仿"都 403，
但官方客户端自己（`opencode serve` 无头服务器）能过。所以不做 fingerprint 伪装，
而是起一个真实客户端进程当传输层，再把它的 HTTP API 翻译成 /v1/chat/completions。

  rikkahub / 任何 OpenAI 客户端
        │  POST /v1/chat/completions
        ▼
  oc_bridge.py (本文件, 默认 :8790)
        │  POST /session , POST /session/{id}/message
        ▼
  opencode serve (真实 1.19.0 二进制, 127.0.0.1:4097)
        │  POST /inference/v1/chat/completions   ← 真客户端指纹，可过闸
        ▼
  opencode.ai Zen 网关  ✅

用法:
  # 1) 确保已装 opencode（真实二进制）。本机可用 npm 包：
  #    npm i -g opencode-ai   →  或指定 --opencode-bin /path/to/opencode
  python3 oc_bridge.py [--port 8790] [--oc-port 4097] [--opencode-bin PATH]
                       [--free-models a,b,c] [--mode stateless|stateful]
                       [--agent NAME] [--prompt TEXT] [--full-prompt]
  # 默认用精简系统提示（~1KB）；--full-prompt 恢复 opencode 默认的完整提示（~9.5KB）
  # 2) rikkahub 提供商:
  #    Base URL = http://127.0.0.1:8790/v1     API Key = 随便
  #    模型 ID  = mimo-v2.6-flash-free
"""
import argparse, json, os, shutil, signal, subprocess, sys, threading, time
import urllib.request, urllib.error
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

VERSION = "1.1.0"

# 默认不做模型过滤：/v1/models 直接把 Zen 上游的全量清单原样返回，
# chat 请求里的 model 也原样透传给上游（可用与否由上游裁决）。
# 只有显式传 --free-models a,b,c 时才启用白名单（旧行为）。
DEFAULT_FREE = []

# 默认用这个自定义 agent 顶掉 opencode 注入的 ~9.5KB 系统提示（实测降到 ~1KB）。
# 通过环境变量 OPENCODE_CONFIG_CONTENT 注入，与用户自己的 opencode.json 合并，不改动其文件。
DEFAULT_AGENT = "bridge"
MINIMAL_PROMPT = "You are a helpful assistant."

ARGS = None
OC_BASE = None
_proc = None
_sessions = {}          # conversation-key -> session id  (stateful 模式)
_lock = threading.Lock()

# 上游模型清单缓存（Zen 的 /v1/models 就是 OpenAI 格式，可原样透传）
ZEN_MODELS_URL = "https://opencode.ai/zen/v1/models"
OC_UA = "opencode/1.19.0"
_models_cache = {"ts": 0.0, "data": None}
_models_lock = threading.Lock()


def upstream_models():
    """取上游全量模型清单（只增不减，不做任何过滤）。

    1) Zen 直连 /zen/v1/models —— 当前 85 个，OpenAI 格式可原样透传；
    2) 补上 opencode serve `/config/providers` 里有、但 Zen 清单缺的
       （实测 `nemotron-3-ultra-free` 就属于这种：能调通却不在 Zen 列表里）。
    两路都失败才返回空列表。
    """
    with _models_lock:
        if _models_cache["data"] and time.time() - _models_cache["ts"] < 60:
            return _models_cache["data"]
        data, seen = [], set()

        def add(m):
            mid = m.get("id") if isinstance(m, dict) else m
            if mid and mid not in seen:
                seen.add(mid)
                data.append(m if isinstance(m, dict) else
                            {"id": mid, "object": "model", "created": int(time.time()),
                             "owned_by": "opencode"})

        try:                                  # 1) Zen 直连：已确认只要 opencode UA 就 200
            req = urllib.request.Request(ZEN_MODELS_URL, headers={
                "User-Agent": OC_UA, "Authorization": "Bearer public"})
            with urllib.request.urlopen(req, timeout=15) as r:
                for m in (json.loads(r.read().decode()) or {}).get("data") or []:
                    add(m)
        except Exception:
            pass
        try:                                  # 2) 补 opencode serve 认得的（含 Zen 清单外的）
            d = oc("GET", "/config/providers", timeout=20)
            for prov in d.get("providers", []):
                for mid in (prov.get("models") or {}):
                    add(mid)
        except Exception:
            pass
        if data:
            _models_cache.update(ts=time.time(), data=data)
        return data


# ---------- opencode server helpers ----------
def oc(method, path, body=None, timeout=300):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(OC_BASE + path, data=data,
                                 headers={"Content-Type": "application/json"}, method=method)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode() or "{}")


def find_opencode():
    if ARGS.opencode_bin:
        return ARGS.opencode_bin
    for c in (os.environ.get("OPENCODE_BIN"),
              shutil.which("opencode"),
              shutil.which("opencode.exe")):
        if c and os.path.exists(c):
            return c
    return None


def start_server():
    global _proc, OC_BASE
    OC_BASE = f"http://127.0.0.1:{ARGS.oc_port}"
    # 已有服务器就直接用。注意：复用的实例可能不是本桥拉起的，
    # 因此拿不到注入的 bridge agent，需要退回到 opencode 自带的 build。
    try:
        oc("GET", "/global/health", timeout=3)
        print(f"[bridge] Reusing the running opencode serve @ {OC_BASE}")
        if ARGS.home:
            print("[bridge] Warning: --home only applies when this bridge starts opencode itself.")
        if ARGS.agent and ARGS.agent != "build":
            try:
                cfg = oc("GET", "/config", timeout=5)
                agents = cfg.get("agent") if isinstance(cfg, dict) else {}
                if not isinstance(agents, dict) or ARGS.agent not in agents:
                    print(f"[bridge] Warning: agent {ARGS.agent!r} is not available on the reused "
                          f"instance; falling back to 'build' (larger system prompt).")
                    ARGS.agent = "build"
            except Exception:
                pass
        return
    except Exception:
        pass
    binary = find_opencode()
    if not binary:
        sys.exit("[bridge] ERROR: opencode binary not found. Install it with "
                 "`npm i -g opencode-ai`, or pass --opencode-bin PATH.")
    env = dict(os.environ)
    if ARGS.home:
        env["HOME"] = ARGS.home
        if os.name == "nt":
            # Windows 版 opencode（Bun）读 USERPROFILE 而不是 HOME，
            # 不同步它会导致 --home 指向的干净目录不生效。
            env["USERPROFILE"] = ARGS.home
    # 用环境变量注入一个精简 agent（与用户已有 opencode.json 合并，不改其文件）：
    # agent.<名>.prompt 为「非空」时会「替换」opencode 默认注入的 ~9.5KB 系统提示。
    if ARGS.agent and ARGS.agent != "build":
        try:
            base = json.loads(env.get("OPENCODE_CONFIG_CONTENT") or "{}")
            if not isinstance(base, dict):
                base = {}
        except Exception:
            base = {}
        agents = base.setdefault("agent", {})
        if ARGS.agent not in agents:
            agents[ARGS.agent] = {"mode": "primary", "prompt": ARGS.prompt}
        env["OPENCODE_CONFIG_CONTENT"] = json.dumps(base, ensure_ascii=False)
    _proc = subprocess.Popen([binary, "serve", "--port", str(ARGS.oc_port), "--hostname", "127.0.0.1"],
                             env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for _ in range(60):
        try:
            oc("GET", "/global/health", timeout=3)
            print(f"[bridge] opencode serve is ready ({binary})")
            return
        except Exception:
            time.sleep(0.5)
    sys.exit("[bridge] ERROR: opencode serve failed to start. "
             "Check that the opencode binary works: opencode --version")


def flush_children(*_):
    if _proc:
        try:
            if os.name == "nt":
                # Popen 的直接子进程可能是 cmd.exe（opencode.CMD），
                # 只杀父进程会留下 node/opencode 孤儿进程。
                subprocess.run(["taskkill", "/F", "/T", "/PID", str(_proc.pid)],
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=10)
            else:
                _proc.send_signal(signal.SIGTERM)
                time.sleep(0.5)
                _proc.kill()
        except Exception:
            pass
    sys.exit(0)


# ---------- OpenAI <-> opencode 转换 ----------
def _text_of(content):
    if isinstance(content, list):  # 多模态/分段
        return "".join(p.get("text", "") for p in content
                       if isinstance(p, dict) and p.get("type") in ("text", "input_text"))
    if isinstance(content, str):
        return content
    return "" if content is None else str(content)


def split_messages(messages):
    """拆成 (system_text, prompt_text)。

    下游 agent（dsh / mimo code 等）自带的 system 提示**原样**走 opencode 的
    `system` 字段，不被塞进 user 文本里；其余消息按角色拼成一段文本
    （stateless 无历史，必须整段重发）。
    """
    systems, lines = [], []
    label = {"assistant": "Assistant", "tool": "Tool"}
    for m in messages or []:
        text = _text_of(m.get("content"))
        role = m.get("role")
        if role in ("system", "developer"):
            if text:
                systems.append(text)
        elif role == "user":
            lines.append(text)
        else:
            lines.append(f"{label.get(role, role or 'User')}: {text}")
    return "\n\n".join(systems), "\n\n".join(lines)


def ask(model, prompt, key, system=None):
    """返回助手文本。stateless=每请求新会话；stateful=按 key 复用会话。"""
    with _lock:
        sid = _sessions.get(key) if ARGS.mode == "stateful" else None
        if not sid:
            sid = oc("POST", "/session", {"title": "bridge"})["id"]
            if ARGS.mode == "stateful":
                _sessions[key] = sid
    body = {"model": {"providerID": "opencode", "modelID": model},
            "parts": [{"type": "text", "text": prompt or "."}]}
    if system:
        # 下游客户端自己的系统提示，原样透传（opencode 会追加在 agent prompt 之后）
        body["system"] = system
    if ARGS.agent:
        # 用注入的精简 agent（默认）顶掉 opencode 默认的 ~9.5KB 系统提示。
        body["agent"] = ARGS.agent
    d = oc("POST", f"/session/{sid}/message", body)
    parts = d.get("parts") or d.get("info", {}).get("parts") or []
    return "".join(p.get("text", "") for p in parts if p.get("type") == "text").strip()


# ---------- HTTP 端点 ----------
class BridgeHTTPServer(ThreadingHTTPServer):
    # Windows 的 SO_REUSEADDR 允许两个进程绑定同一端口（会静默抢请求），
    # 必须关掉；Unix 上保留它是为了正常重启时能复用 TIME_WAIT 端口。
    allow_reuse_address = os.name != "nt"


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *a):
        pass

    def handle_one_request(self):
        # 客户端提前断开（健康检查、取消请求、关闭窗口）不应该打印整段 traceback。
        try:
            super().handle_one_request()
        except (ConnectionResetError, ConnectionAbortedError, BrokenPipeError):
            self.close_connection = True

    def _json(self, code, obj):
        b = json.dumps(obj, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, GET, OPTIONS")
        self.send_header("Content-Length", "0")
        self.end_headers()

    def do_GET(self):
        path = self.path.split("?", 1)[0].rstrip("/")
        if path in ("", "/"):
            self._json(200, {
                "name": "OpenCode Zen Bridge",
                "version": VERSION,
                "ok": True,
                "endpoints": {
                    "models": "/v1/models",
                    "chat": "/v1/chat/completions",
                    "health": "/health",
                },
                "usage": {
                    "base_url": f"http://127.0.0.1:{ARGS.port}/v1",
                    "api_key": "any non-empty string",
                    "example_model": "deepseek-v4.1-flash-free",
                },
            })
        elif path.endswith("/models"):
            if ARGS.free_models:            # 显式传了 --free-models 才过滤
                now = int(time.time())
                data = [{"id": m, "object": "model", "created": now, "owned_by": "opencode"}
                        for m in ARGS.free_models]
            else:                           # 默认：上游给什么就返回什么
                data = upstream_models()
            self._json(200, {"object": "list", "data": data})
        elif "/models/" in path:
            model_id = path.rsplit("/models/", 1)[-1]
            for m in (upstream_models() if not ARGS.free_models else []):
                if m.get("id") == model_id:
                    return self._json(200, m)
            if model_id in (ARGS.free_models or []):
                return self._json(200, {"id": model_id, "object": "model",
                                        "created": int(time.time()), "owned_by": "opencode"})
            self._json(404, {"error": {"message": f"model {model_id!r} not found"}})
        elif "health" in self.path:
            self._json(200, {"ok": True})
        else:
            self._json(404, {"error": {"message": "not found"}})

    def do_POST(self):
        ln = int(self.headers.get("Content-Length") or 0)
        try:
            req = json.loads(self.rfile.read(ln) or b"{}")
        except Exception as e:
            return self._json(400, {"error": {"message": f"bad json: {e}"}})
        if not self.path.rstrip("/").endswith("/chat/completions"):
            return self._json(404, {"error": {"message": "only /v1/chat/completions"}})

        model = str(req.get("model") or "").strip()
        model = model.split("/")[-1]
        if model.endswith("(high)") or "(" in model:
            model = model.split("(")[0].strip()
        if ARGS.free_models and model not in ARGS.free_models:
            return self._json(404, {"error": {"message": f"model {model!r} not in allowlist",
                                              "type": "ModelError"}})
        system_text, prompt = split_messages(req.get("messages"))
        key = self.headers.get("X-Conversation-Id") or self.headers.get("X-Session-Id") or "default"
        try:
            text = ask(model, prompt, key, system_text or None)
        except urllib.error.HTTPError as e:
            body = e.read(400).decode(errors="replace")
            return self._json(e.code, {"error": {"message": body, "type": "UpstreamError"}})
        except Exception as e:
            return self._json(502, {"error": {"message": repr(e), "type": "BridgeError"}})

        cid = f"chatcmpl-{int(time.time()*1000)}"
        if req.get("stream"):
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-cache")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Connection", "close")
            self.end_headers()
            def chunk(delta, finish=None):
                d = {"id": cid, "object": "chat.completion.chunk", "created": int(time.time()),
                     "model": model, "choices": [{"index": 0, "delta": delta, "finish_reason": finish}]}
                self.wfile.write(f"data: {json.dumps(d, ensure_ascii=False)}\n\n".encode())
            try:
                chunk({"role": "assistant", "content": ""})
                for i in range(0, len(text), 24):
                    chunk({"content": text[i:i+24]}); self.wfile.flush()
                chunk({}, "stop")
                self.wfile.write(b"data: [DONE]\n\n")
                self.wfile.flush()
            except (ConnectionResetError, ConnectionAbortedError, BrokenPipeError):
                pass
            self.close_connection = True
        else:
            self._json(200, {"id": cid, "object": "chat.completion", "created": int(time.time()),
                             "model": model,
                             "choices": [{"index": 0, "message": {"role": "assistant", "content": text},
                                          "finish_reason": "stop"}],
                             "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}})


def main():
    global ARGS
    ap = argparse.ArgumentParser()
    ap.add_argument("--version", action="version", version=f"oc_bridge {VERSION}")
    ap.add_argument("--port", type=int, default=8790)
    ap.add_argument("--oc-port", type=int, default=4097)
    ap.add_argument("--opencode-bin", default=None)
    ap.add_argument("--home", default=None, help="opencode 的 HOME（配置/凭据目录）")
    ap.add_argument("--free-models", default=None,
                    help="可选：逗号分隔的白名单。不传（默认）= 不过滤，/v1/models 原样返回上游全量清单，"
                         "chat 的 model 直接透传；传了则只允许这些模型（旧行为）")
    ap.add_argument("--mode", choices=["stateless", "stateful"], default="stateless")
    ap.add_argument("--agent", default=DEFAULT_AGENT,
                    help=f"要使用的 opencode agent 名（默认 {DEFAULT_AGENT}：桥自动注入的精简 agent，"
                         "可把注入的系统提示从 ~9.5KB 降到 ~1KB；填 build 则用 opencode 默认完整提示）")
    ap.add_argument("--prompt", default=MINIMAL_PROMPT,
                    help=f"--agent 为 {DEFAULT_AGENT} 时使用的系统提示文本（默认 {MINIMAL_PROMPT!r}）")
    ap.add_argument("--full-prompt", action="store_true",
                    help="用 opencode 默认的完整系统提示（等价于 --agent build）")
    ARGS = ap.parse_args()
    ARGS.free_models = [m.strip() for m in (ARGS.free_models or "").split(",") if m.strip()]
    if ARGS.full_prompt:
        ARGS.agent = "build"
    signal.signal(signal.SIGTERM, flush_children)
    signal.signal(signal.SIGINT, flush_children)
    # 先绑定 HTTP 端口，避免端口被占用时已经拉起 opencode serve 留下孤儿进程。
    try:
        httpd = BridgeHTTPServer(("127.0.0.1", ARGS.port), Handler)
    except OSError as e:
        sys.exit(f"[bridge] ERROR: cannot listen on 127.0.0.1:{ARGS.port} ({e}). "
                 f"The port is probably already in use; pass --port 8791 or stop the other process.")
    start_server()
    if ARGS.free_models:
        desc = f"白名单 {len(ARGS.free_models)} 个: {', '.join(ARGS.free_models[:4])}..."
    else:
        desc = f"不过滤（上游全量 {len(upstream_models())} 个模型）"
    print(f"[bridge] OpenAI-compatible endpoint: http://127.0.0.1:{ARGS.port}/v1  ({desc})  mode={ARGS.mode}")
    print("=" * 64)
    print("  Base URL : http://127.0.0.1:%d/v1" % ARGS.port)
    print("  API Key  : any non-empty string (not checked)")
    print("  Model    : deepseek-v4.1-flash-free")
    print("  Health   : http://127.0.0.1:%d/health" % ARGS.port)
    print("  Stop     : Ctrl+C")
    print("=" * 64)
    httpd.serve_forever()


if __name__ == "__main__":
    main()
