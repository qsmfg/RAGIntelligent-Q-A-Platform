#!/bin/bash
# =============================================
# 小A智能问答系统 — Gunicorn 启动脚本
# 部署服务器: 1.95.49.216
# 使用: bash start.sh [start|stop|restart|status]
# =============================================

APP_NAME="小A智能问答系统"
APP_MODULE="app:app"
BIND_ADDR="0.0.0.0:8000"
WORKERS=4
WORKER_CLASS="uvicorn.workers.UvicornWorker"
PID_FILE="/var/run/xiaoA-qa.pid"
LOG_DIR="/var/log/xiaoA-qa"
PROJECT_DIR="/opt/xiaoA-qa"

# 确保日志目录存在
mkdir -p "$LOG_DIR"

start() {
    if [ -f "$PID_FILE" ] && kill -0 $(cat "$PID_FILE") 2>/dev/null; then
        echo "[$APP_NAME] 已在运行中 (PID: $(cat $PID_FILE))"
        return 1
    fi

    echo "[$APP_NAME] 启动中..."
    cd "$PROJECT_DIR"

    gunicorn "$APP_MODULE" \
        --bind "$BIND_ADDR" \
        --workers "$WORKERS" \
        --worker-class "$WORKER_CLASS" \
        --pid "$PID_FILE" \
        --access-logfile "$LOG_DIR/access.log" \
        --error-logfile "$LOG_DIR/error.log" \
        --log-level info \
        --daemon \
        --timeout 120 \
        --graceful-timeout 30

    sleep 2
    if [ -f "$PID_FILE" ] && kill -0 $(cat "$PID_FILE") 2>/dev/null; then
        echo "[$APP_NAME] 启动成功 (PID: $(cat $PID_FILE))"
    else
        echo "[$APP_NAME] 启动失败，请检查日志: $LOG_DIR/error.log"
        return 1
    fi
}

stop() {
    if [ -f "$PID_FILE" ] && kill -0 $(cat "$PID_FILE") 2>/dev/null; then
        echo "[$APP_NAME] 正在停止 (PID: $(cat $PID_FILE))..."
        kill -TERM $(cat "$PID_FILE")
        sleep 2
        rm -f "$PID_FILE"
        echo "[$APP_NAME] 已停止"
    else
        echo "[$APP_NAME] 未在运行"
    fi
}

restart() {
    stop
    sleep 1
    start
}

status() {
    if [ -f "$PID_FILE" ] && kill -0 $(cat "$PID_FILE") 2>/dev/null; then
        echo "[$APP_NAME] 运行中 (PID: $(cat $PID_FILE))"
    else
        echo "[$APP_NAME] 未运行"
    fi
}

case "${1:-start}" in
    start)   start ;;
    stop)    stop ;;
    restart) restart ;;
    status)  status ;;
    *)
        echo "用法: $0 {start|stop|restart|status}"
        exit 1
        ;;
esac