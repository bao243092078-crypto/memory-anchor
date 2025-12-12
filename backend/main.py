"""
Memory Anchor - 记忆锚点
为阿尔茨海默症患者及其照护者提供便利贴式记忆辅助系统

启动命令: uv run uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.api.constitution import router as constitution_router
from backend.api.notes import router as notes_router
from backend.api.search import router as search_router
from backend.api.memory import router as memory_router

app = FastAPI(
    title="Memory Anchor API",
    description="记忆锚点 - 便利贴式记忆辅助系统",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS 配置（开发环境允许所有来源）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 生产环境需要限制
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(notes_router, prefix="/api/v1")
app.include_router(search_router)  # search 路由已有 /api/v1 前缀
app.include_router(memory_router)  # memory 路由已有 /api/v1/memory 前缀
app.include_router(constitution_router, prefix="/api/v1")  # 宪法层变更路由


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
