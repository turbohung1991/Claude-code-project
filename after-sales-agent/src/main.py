from fastapi import FastAPI

from src.api.routes import router

app = FastAPI(title="美妆售后智能体", version="0.1.0")
app.include_router(router, prefix="/api/v1")
