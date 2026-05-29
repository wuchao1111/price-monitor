#!/bin/bash
# 保价追踪系统 - 统一启动脚本

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "========================================"
echo "  🛡️  保价追踪系统启动中"
echo "========================================"

# 检查 Python 是否可用
if ! command -v python3 &> /dev/null; then
    echo "❌ 错误: 未找到 python3"
    exit 1
fi

# 创建 data 目录
mkdir -p data

echo ""
echo "启动后端服务..."
echo "📱 访问: http://127.0.0.1:9000"
echo ""
echo "按 Ctrl+C 停止服务"
echo "========================================"
echo ""

python3 app.py
