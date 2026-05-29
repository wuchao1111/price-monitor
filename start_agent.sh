#!/bin/bash
# 启动 Web UI + 价格监控（后台）+ CLI Agent（前台）
# 一个命令启动全部服务

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
LOG_DIR="$SCRIPT_DIR/log"
mkdir -p "$LOG_DIR"

echo "========================================"
echo "  🛡️  保价追踪系统 - 全量启动"
echo "========================================"

# 1. 启动 Web UI（后台）
WEBUI_LOG="$LOG_DIR/webui.log"
echo "启动 Web UI..."
nohup python3 "$SCRIPT_DIR/app.py" > "$WEBUI_LOG" 2>&1 &
WEBUI_PID=$!
echo "  Web UI 已启动 (PID: $WEBUI_PID) → http://localhost:9000"

# 2. 启动价格监控（后台，caffeinate 防休眠）
MONITOR_LOG="$LOG_DIR/monitor_$(date +%Y%m%d_%H%M%S).log"
echo "启动价格监控（caffeinate 防休眠）..."
nohup caffeinate -i python3 "$SCRIPT_DIR/monitor_all_products.py" > "$MONITOR_LOG" 2>&1 &
MONITOR_PID=$!
echo "  监控已启动 (PID: $MONITOR_PID)"
echo "$MONITOR_PID" > "$LOG_DIR/monitor.pid"

echo ""
echo "========== 已启动 =========="
echo "Web UI:   http://localhost:9000"
echo "监控日志: $MONITOR_LOG"
echo "============================"
echo ""

# 3. 启动 CLI Agent 交互模式（前台）
echo "进入 CLI Agent 交互模式..."
echo "输入 'exit' 退出，退出时可选是否同时停止后台服务"
echo "----------------------------------------"
python3 -m src.ui.cli interactive

# CLI 退出后询问是否停止后台服务
echo ""
echo "----------------------------------------"
read -p "是否同时停止后台 Web UI + 监控？(y/n): " stop_choice
if [ "$stop_choice" = "y" ] || [ "$stop_choice" = "Y" ]; then
    bash "$SCRIPT_DIR/stop_monitor.sh"
else
    echo "后台服务仍在运行"
    echo "手动停止: bash $SCRIPT_DIR/stop_monitor.sh"
fi
