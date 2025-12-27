"""
Memory Anchor - 记忆锚点
为阿尔茨海默症患者及其照护者提供便利贴式记忆辅助系统

启动命令: uv run uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
"""

import logging
import os

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.api.auth import verify_api_key
from backend.api.constitution import router as constitution_router
from backend.api.memory import router as memory_router
from backend.api.notes import router as notes_router
from backend.api.pending import router as pending_router
from backend.api.search import router as search_router

logger = logging.getLogger(__name__)


def _load_cors_origins() -> list[str]:
    raw = os.getenv("MA_CORS_ALLOW_ORIGINS")
    if raw:
        return [origin.strip() for origin in raw.split(",") if origin.strip()]
    return [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]

app = FastAPI(
    title="Memory Anchor API",
    description="记忆锚点 - 便利贴式记忆辅助系统",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS 配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=_load_cors_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
api_dependencies = [Depends(verify_api_key)]

if not os.getenv("MA_API_KEY"):
    logger.warning("MA_API_KEY not set; API auth is disabled.")

app.include_router(notes_router, prefix="/api/v1", dependencies=api_dependencies)
app.include_router(search_router, dependencies=api_dependencies)  # search 路由已有 /api/v1 前缀
app.include_router(memory_router, dependencies=api_dependencies)  # memory 路由已有 /api/v1/memory 前缀
app.include_router(constitution_router, prefix="/api/v1", dependencies=api_dependencies)  # 宪法层变更路由
app.include_router(pending_router, dependencies=api_dependencies)  # pending 路由已有 /api/v1/pending 前缀


@app.get("/")
async def root():
    """健康检查"""
    return {
        "name": "Memory Anchor",
        "version": "0.1.0",
        "status": "healthy",
        "message": "记忆锚点服务运行中",
    }


@app.get("/health")
async def health_check():
    """详细健康检查"""
    return {
        "status": "healthy",
        "components": {
            "api": "ok",
            "database": "pending",  # TODO: 实现数据库检查
            "qdrant": "pending",  # TODO: 实现 Qdrant 检查
        },
    }
