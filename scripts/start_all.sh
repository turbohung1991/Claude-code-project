#!/bin/bash
# 启动 Douyin API + Gradio（持久运行，不受终端退出影响）
set -a
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
[ -f "$PROJECT_DIR/.env" ] && source "$PROJECT_DIR/.env"
set +a

echo "Starting Douyin API on port 80..."
cd /tmp/Douyin_TikTok_Download_API
nohup /usr/bin/python3 start.py > /tmp/douyin_api.log 2>&1 &
disown

sleep 6
if curl -s -o /dev/null -w '%{http_code}' http://localhost:80 | grep -q 200; then
    echo "  API: OK"
else
    echo "  API: FAILED - check /tmp/douyin_api.log"
fi

echo "Starting Gradio on port 7860..."
cd "$PROJECT_DIR"
nohup /usr/bin/python3 app.py > /tmp/gradio_app.log 2>&1 &
disown

sleep 6
if curl -s -o /dev/null -w '%{http_code}' http://localhost:7860 | grep -q 200; then
    echo "  Gradio: OK -> http://localhost:7860"
else
    echo "  Gradio: FAILED - check /tmp/gradio_app.log"
fi
