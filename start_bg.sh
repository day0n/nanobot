#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PORT="${NANOBOT_PORT:-18791}"
LOG_DIR="${NANOBOT_LOG_DIR:-$HOME/.nanobot/logs}"
RUN_DIR="${NANOBOT_RUN_DIR:-$HOME/.nanobot/run}"
LOG_FILE="${NANOBOT_LOG_FILE:-$LOG_DIR/nanobot-${PORT}.log}"
PID_FILE="${NANOBOT_PID_FILE:-$RUN_DIR/nanobot-${PORT}.pid}"
ENV_FILE="${NANOBOT_ENV_FILE:-$SCRIPT_DIR/.env.local}"
NANOBOT_BIN="${NANOBOT_BIN:-$SCRIPT_DIR/.venv/bin/nanobot}"

mkdir -p "$LOG_DIR" "$RUN_DIR"
cd "$SCRIPT_DIR"

if [ -f "$ENV_FILE" ]; then
    echo "[0/4] 加载环境变量: $ENV_FILE"
    set -a
    # shellcheck disable=SC1090
    source "$ENV_FILE"
    set +a
fi

if [ ! -x "$NANOBOT_BIN" ]; then
    echo "nanobot 可执行文件不存在: $NANOBOT_BIN" >&2
    echo "请先创建虚拟环境并安装依赖，或通过 NANOBOT_BIN 指定可执行文件。" >&2
    exit 1
fi

echo "[1/4] 检查现有 PID 文件..."
if [ -f "$PID_FILE" ]; then
    OLD_PID="$(cat "$PID_FILE" 2>/dev/null || true)"
    if [ -n "$OLD_PID" ] && kill -0 "$OLD_PID" 2>/dev/null; then
        echo "nanobot 已在后台运行: PID $OLD_PID"
        echo "PID 文件: $PID_FILE"
        echo "日志文件: $LOG_FILE"
        exit 0
    fi
    rm -f "$PID_FILE"
fi

echo "[2/4] 检查端口占用 (port $PORT)..."
PORT_PID="$(lsof -ti tcp:"$PORT" 2>/dev/null || true)"
if [ -n "$PORT_PID" ]; then
    echo "端口 $PORT 已被进程占用: PID $PORT_PID" >&2
    echo "请先停止该进程，或设置不同的 NANOBOT_PORT。" >&2
    exit 1
fi

echo "[3/4] 后台启动 nanobot..."
nohup env PYTHONPATH="$SCRIPT_DIR" "$NANOBOT_BIN" serve --port "$PORT" \
    >>"$LOG_FILE" 2>&1 &
PID=$!
echo "$PID" > "$PID_FILE"

sleep 1

echo "[4/4] 校验进程状态..."
if ! kill -0 "$PID" 2>/dev/null; then
    echo "nanobot 启动失败，请检查日志: $LOG_FILE" >&2
    rm -f "$PID_FILE"
    exit 1
fi

echo "nanobot 已在后台启动"
echo "  PID: $PID"
echo "  Port: $PORT"
echo "  PID 文件: $PID_FILE"
echo "  日志文件: $LOG_FILE"
echo "  查看日志: tail -f \"$LOG_FILE\""
