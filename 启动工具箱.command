#!/bin/bash
# 双击此文件即可在终端中启动 AI 智能工具箱
cd "$(dirname "$0")"

# 清理旧进程
lsof -ti:7860 | xargs kill -9 2>/dev/null
sleep 1

echo ""
echo "╔═══════════════════════════════════════╗"
echo "║     AI 智能工具箱 — Vibecoding        ║"
echo "║     http://localhost:7860             ║"
echo "╚═══════════════════════════════════════╝"
echo ""

# 启动
/usr/bin/python3 app.py

# 按任意键退出
read -p "服务已停止，按回车键关闭窗口..."
