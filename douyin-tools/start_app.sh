#!/bin/bash
# 启动 Vibecoding Flask 应用
set -a
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
[ -f "$SCRIPT_DIR/.env" ] && source "$SCRIPT_DIR/.env"
set +a

echo "Starting Vibecoding on port 7860..."
cd "$SCRIPT_DIR"
nohup /usr/bin/python3 app.py > /tmp/vibecoding.log 2>&1 &
disown

sleep 6
if curl -s -o /dev/null -w '%{http_code}' http://localhost:7860 | grep -q 200; then
    echo "  OK -> http://localhost:7860"
else
    echo "  FAILED - check /tmp/vibecoding.log"
fi
