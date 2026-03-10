#!/usr/bin/env bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PORT="${NANOBOT_PORT:-18791}"
LOG_FILE="/tmp/nanobot.log"

cd "$SCRIPT_DIR"

echo "[1/3] git pull..."
git pull

echo "[2/3] 杀掉旧进程 (port $PORT)..."
PID=$(lsof -ti tcp:"$PORT" 2>/dev/null || true)
if [ -n "$PID" ]; then
    kill "$PID"
    sleep 1
    echo "  已终止 PID $PID"
else
    echo "  无旧进程"
fi

echo "[3/3] 启动 nanobot (port $PORT, log: $LOG_FILE)..."
nohup env PYTHONPATH="$SCRIPT_DIR" "$SCRIPT_DIR/.venv/bin/nanobot" serve --port "$PORT" \
    > "$LOG_FILE" 2>&1 &

echo "  PID: $!"
echo "  日志: tail -f $LOG_FILE"

sleep 2
tail -5 "$LOG_FILE"
