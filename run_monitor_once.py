#!/usr/bin/env python3
"""
只运行一次的监控脚本（不启动定时任务）
"""
import asyncio
import os
import sys

# Add the project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from monitor_all_products import check_all_products


if __name__ == "__main__":
    asyncio.run(check_all_products())
