#!/bin/bash
# 启动 Vibecoding Flask 应用

echo "Starting Vibecoding on port 7860..."
cd "/Users/admin/claude code project"
nohup env DEEPSEEK_API_KEY="sk-6bb48b62f5894ce4ab504dedcb5eca40" REMOVE_BG_API_KEY="27zwCujUJby2n6cxAAHMVm3k" CLIPDROP_API_KEY="0f34f19fa451dee7d3a51537dd5febd7acc64b1e2fbb2bb17a93f2d1ad80fb2df7191f715eeb5e0e9ac9137ee93b7541" /usr/bin/python3 app.py > /tmp/vibecoding.log 2>&1 &
disown

sleep 6
if curl -s -o /dev/null -w '%{http_code}' http://localhost:7860 | grep -q 200; then
    echo "  OK -> http://localhost:7860"
else
    echo "  FAILED - check /tmp/vibecoding.log"
fi
