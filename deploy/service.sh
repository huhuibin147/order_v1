#!/bin/bash
# 点单系统服务管理
# 用法: service.sh {start|stop|restart|status}

APP_DIR="/opt/order_v1"
PID_FILE="$APP_DIR/app.pid"
LOG_FILE="$APP_DIR/app.log"

start() {
    if [ -f "$PID_FILE" ] && kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
        echo "已在运行，PID: $(cat "$PID_FILE")"
        return 1
    fi
    cd "$APP_DIR"
    nohup .venv/bin/python app.py > "$LOG_FILE" 2>&1 &
    echo $! > "$PID_FILE"
    echo "已启动，PID: $!"
}

stop() {
    if [ ! -f "$PID_FILE" ]; then
        echo "未在运行"
        return 1
    fi
    PID=$(cat "$PID_FILE")
    if kill -0 "$PID" 2>/dev/null; then
        kill "$PID"
        echo "已停止，PID: $PID"
    else
        echo "进程 $PID 已不存在"
    fi
    rm -f "$PID_FILE"
}

status() {
    if [ -f "$PID_FILE" ] && kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
        echo "运行中，PID: $(cat "$PID_FILE")"
    else
        echo "未运行"
    fi
}

case "${1}" in
    start)   start ;;
    stop)    stop ;;
    restart) stop; sleep 1; start ;;
    status)  status ;;
    *)       echo "用法: $0 {start|stop|restart|status}" ;;
esac
