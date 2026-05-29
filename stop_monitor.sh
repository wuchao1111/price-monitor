#!/bin/bash
# 停止 Web UI + 价格监控

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
LOG_DIR="$SCRIPT_DIR/log"
PID_FILE="$LOG_DIR/monitor.pid"

echo "正在停止所有服务..."

# 1. 停止监控进程
if [ -f "$PID_FILE" ]; then
    MONITOR_PID=$(cat "$PID_FILE")
    if ps -p "$MONITOR_PID" > /dev/null 2>&1; then
        echo "停止监控 (PID: $MONITOR_PID)..."
        kill "$MONITOR_PID"
    else
        echo "监控进程 $MONITOR_PID 不存在"
    fi
    rm "$PID_FILE"
else
    echo "没有找到监控 PID 文件，尝试查找 monitor_all_products.py 进程..."
    pkill -f "monitor_all_products.py" 2>/dev/null && echo "已停止监控" || echo "没有找到监控进程"
fi

# 2. 停止 Web UI
echo "停止 Web UI..."
pkill -f "python3.*app.py" 2>/dev/null && echo "已停止 Web UI" || echo "没有找到 Web UI 进程"

# 3. 停止 caffeinate
pkill -f "caffeinate.*monitor_all_products" 2>/dev/null

echo ""
echo "所有服务已停止"
