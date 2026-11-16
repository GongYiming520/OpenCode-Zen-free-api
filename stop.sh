#!/usr/bin/env sh
# stop.sh - stop a bridge started with ./start.sh --bg
set -eu

DIR=$(cd "$(dirname "$0")" && pwd)
PIDFILE="$DIR/.bridge.pid"

if [ ! -f "$PIDFILE" ]; then
  echo "[stop] No .bridge.pid found."
  echo "[stop] If you started the bridge in the foreground, press Ctrl+C in that terminal."
  exit 1
fi

PID=$(cat "$PIDFILE" 2>/dev/null || true)
if [ -z "$PID" ] || ! kill -0 "$PID" 2>/dev/null; then
  echo "[stop] Process $PID is not running; removing the stale pid file."
  rm -f "$PIDFILE"
  exit 0
fi

echo "[stop] Stopping pid $PID ..."
kill "$PID" 2>/dev/null || true
i=0
while kill -0 "$PID" 2>/dev/null && [ "$i" -lt 20 ]; do
  sleep 0.5
  i=$((i + 1))
done
if kill -0 "$PID" 2>/dev/null; then
  echo "[stop] Process did not exit; sending SIGKILL."
  kill -9 "$PID" 2>/dev/null || true
fi
rm -f "$PIDFILE"
echo "[stop] Done."
