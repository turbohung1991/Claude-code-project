from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from src.api.routes import router

app = FastAPI(title="美妆售后智能体", version="0.1.0")
app.include_router(router, prefix="/api/v1")

# 托管千牛插件前端页面
plugin_dir = Path(__file__).parent.parent.parent / "qianniu-plugin"
if plugin_dir.exists():
    app.mount("/plugin", StaticFiles(directory=str(plugin_dir), html=True), name="plugin")
