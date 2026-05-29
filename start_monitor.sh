#!/bin/bash
# 启动 Web UI + 价格监控（后台运行，caffeinate 防休眠）
# 每10分钟检查一次所有商品

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
LOG_DIR="$SCRIPT_DIR/log"
mkdir -p "$LOG_DIR"

# 1. 启动 Web UI
WEBUI_LOG="$LOG_DIR/webui.log"
echo "启动 Web UI..."
nohup python3 "$SCRIPT_DIR/app.py" > "$WEBUI_LOG" 2>&1 &
WEBUI_PID=$!
echo "Web UI 已启动，PID: $WEBUI_PID"

# 2. 启动价格监控（caffeinate 保持系统不空闲休眠）
MONITOR_LOG="$LOG_DIR/monitor_$(date +%Y%m%d_%H%M%S).log"
echo "启动价格监控（caffeinate 防休眠）..."
nohup caffeinate -i python3 "$SCRIPT_DIR/monitor_all_products.py" > "$MONITOR_LOG" 2>&1 &
MONITOR_PID=$!

echo "监控已启动，PID: $MONITOR_PID"
echo "$MONITOR_PID" > "$LOG_DIR/monitor.pid"

echo ""
echo "========== 已启动 =========="
echo "Web UI:   http://localhost:9000"
echo "日志:     $MONITOR_LOG"
echo ""
echo "查看日志: tail -f $MONITOR_LOG"
echo "停止服务: bash $(dirname "$0")/stop_monitor.sh"
echo "============================"
