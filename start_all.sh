#!/bin/bash
# 启动 Douyin API + Gradio（持久运行，不受终端退出影响）

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
cd "/Users/admin/claude code project"
nohup env REMOVE_BG_API_KEY="27zwCujUJby2n6cxAAHMVm3k" CLIPDROP_API_KEY="0f34f19fa451dee7d3a51537dd5febd7acc64b1e2fbb2bb17a93f2d1ad80fb2df7191f715eeb5e0e9ac9137ee93b7541" /usr/bin/python3 app.py > /tmp/gradio_app.log 2>&1 &
disown

sleep 6
if curl -s -o /dev/null -w '%{http_code}' http://localhost:7860 | grep -q 200; then
    echo "  Gradio: OK -> http://localhost:7860"
else
    echo "  Gradio: FAILED - check /tmp/gradio_app.log"
fi
