#!/usr/bin/env sh
# start.sh - one-click launcher for Linux / macOS / Termux / WSL
#
#   ./start.sh                          foreground, port 8790
#   ./start.sh --bg                     background (log: bridge.log, pid: .bridge.pid)
#   ./start.sh --port 9000 --mode stateful
#   OPENCODE_BIN=/path/to/opencode ./start.sh
#
# --bg must be the first argument. Everything else is passed to oc_bridge.py.
# The script uses an isolated data directory (.opencode-home) unless you pass
# --home yourself.
set -eu

DIR=$(cd "$(dirname "$0")" && pwd)

BG=0
if [ "${1:-}" = "--bg" ]; then
  BG=1
  shift
fi

USER_BIN=0
USER_HOME=0
for a in "$@"; do
  case "$a" in
    --opencode-bin|--opencode-bin=*) USER_BIN=1 ;;
    --home|--home=*)                 USER_HOME=1 ;;
  esac
done

# ---------- 1. Python ----------
PY=$(command -v python3 || command -v python || true)
if [ -z "$PY" ]; then
  echo "[start] Python 3 was not found."
  echo "[start] Debian/Ubuntu: sudo apt install python3"
  echo "[start] Termux: pkg install python"
  exit 1
fi
if ! "$PY" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 8) else 1)'; then
  echo "[start] Python 3.8 or newer is required."
  "$PY" --version
  exit 1
fi

# ---------- 2. find opencode (absolute path, idempotent) ----------
find_opencode() {
  if [ -n "${OPENCODE_BIN:-}" ] && [ -x "$OPENCODE_BIN" ]; then
    printf '%s\n' "$OPENCODE_BIN"; return 0
  fi
  p=$(command -v opencode 2>/dev/null || true)
  if [ -n "$p" ] && [ -x "$p" ]; then
    printf '%s\n' "$p"; return 0
  fi
  if command -v npm >/dev/null 2>&1; then
    np=$(npm prefix -g 2>/dev/null || true)
    [ -n "$np" ] || np=$(npm root -g 2>/dev/null | sed 's#/lib/node_modules$##' || true)
    for c in "$np/bin/opencode" "$np/opencode" "$np/opencode.exe" \
             "$np/lib/node_modules/opencode-ai/bin/opencode" \
             "$np/node_modules/opencode-ai/bin/opencode"; do
      [ -n "$np" ] && [ -x "$c" ] && { printf '%s\n' "$c"; return 0; }
    done
  fi
  for c in "$HOME/.local/bin/opencode" "$HOME/.opencode/bin/opencode" \
           "/usr/local/bin/opencode" "${PREFIX:-/nonexistent}/bin/opencode"; do
    [ -n "$c" ] && [ -x "$c" ] && { printf '%s\n' "$c"; return 0; }
  done
  return 1
}

OC_BIN=""
if [ "$USER_BIN" = "0" ]; then
  OC_BIN=$(find_opencode || true)
fi

if [ "$USER_BIN" = "0" ] && [ -z "$OC_BIN" ]; then
  echo "[start] opencode was not found. Installing opencode-ai with npm ..."
  if command -v npm >/dev/null 2>&1; then
    npm i -g opencode-ai || echo "[start] npm install failed. See https://opencode.ai"
    OC_BIN=$(find_opencode || true)
  else
    echo "[start] Node.js / npm was not found."
    echo "[start] Install Node.js 18+ first, or install opencode manually."
    echo "[start] Termux: pkg install nodejs && npm i -g opencode-ai"
  fi
fi

if [ "$USER_BIN" = "0" ] && [ -z "$OC_BIN" ]; then
  echo "[start] Still could not locate the opencode binary."
  echo "[start] Run 'opencode --version' once, or pass --opencode-bin PATH."
  exit 1
fi

# ---------- 3. isolated data directory ----------
if [ "$USER_HOME" = "0" ]; then
  mkdir -p "$DIR/.opencode-home"
  set -- --home "$DIR/.opencode-home" "$@"
fi
if [ "$USER_BIN" = "0" ]; then
  set -- --opencode-bin "$OC_BIN" "$@"
fi

export PYTHONUTF8=1
cd "$DIR"

# ---------- 4. start ----------
if [ "$BG" = "1" ]; then
  LOG="$DIR/bridge.log"
  echo "[start] Background mode. Log: $LOG"
  nohup "$PY" -u "$DIR/oc_bridge.py" "$@" >>"$LOG" 2>&1 &
  echo $! >"$DIR/.bridge.pid"
  echo "[start] pid $! (stop with ./stop.sh)"
else
  exec "$PY" -u "$DIR/oc_bridge.py" "$@"
fi
