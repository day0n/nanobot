#!/usr/bin/env bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PORT="${NANOBOT_PORT:-18791}"
LOG_FILE="/tmp/nanobot.log"
UV="$HOME/.local/bin/uv"

cd "$SCRIPT_DIR"

echo "[1/4] git pull..."
git pull

echo "[2/4] 同步依赖..."
"$UV" pip install -e . --python "$SCRIPT_DIR/.venv/bin/python" -q

echo "[3/4] 杀掉旧进程 (port $PORT)..."
PID=$(lsof -ti tcp:"$PORT" 2>/dev/null || true)
if [ -n "$PID" ]; then
    kill "$PID" && sleep 1 && echo "  已终止 PID $PID"
else
    pkill -f "nanobot serve" 2>/dev/null && sleep 1 && echo "  已终止旧进程" || echo "  无旧进程"
fi

echo "[4/4] 启动 nanobot (port $PORT, log: $LOG_FILE)..."
echo "  以前台模式启动，日志将同时输出到终端和 $LOG_FILE"
echo "  按 Ctrl+C 可停止服务"

env PYTHONPATH="$SCRIPT_DIR" "$SCRIPT_DIR/.venv/bin/nanobot" serve --port "$PORT" \
    2>&1 | tee "$LOG_FILE"
