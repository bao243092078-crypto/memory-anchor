"""
Search API routes for Memory Anchor.
语义搜索 API，支持过滤和分页。
"""
from typing import Optional, List

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

from backend.services.search import get_search_service


router = APIRouter(prefix="/api/v1", tags=["search"])


# --- Request/Response Models ---


class SearchResult(BaseModel):
    """搜索结果项"""

    id: str = Field(..., description="便利贴 ID")
    content: str = Field(..., description="便利贴内容")
    score: float = Field(..., description="相似度分数 (0-1)")
    layer: Optional[str] = Field(None, description="记忆层级")
    category: Optional[str] = Field(None, description="类别")


class SearchResponse(BaseModel):
    """搜索响应"""

    query: str = Field(..., description="原始查询")
    results: List[SearchResult] = Field(..., description="搜索结果")
    total: int = Field(..., description="返回数量")


class IndexStats(BaseModel):
    """索引统计"""

    total_count: int = Field(..., description="总索引数量")
    vector_size: int = Field(..., description="向量维度")
    distance: str = Field(..., description="距离度量")


# --- Routes ---


@router.get("/search", response_model=SearchResponse)
async def search_notes(
    q: str = Query(..., min_length=1, description="搜索查询"),
    limit: int = Query(5, ge=1, le=20, description="返回数量限制"),
    layer: Optional[str] = Query(
        None,
        pattern="^(constitution|fact|session)$",
        description="过滤记忆层级",
    ),
    category: Optional[str] = Query(
        None,
        pattern="^(person|place|event|item|routine)$",
        description="过滤类别",
    ),
    only_active: bool = Query(True, description="是否只返回激活的便利贴"),
):
    """
    语义搜索便利贴。

    使用向量相似度搜索，返回与查询最相关的便利贴。
    支持按记忆层级和类别过滤。

    **使用示例**：
    - 搜索所有相关: `GET /api/v1/search?q=吃药`
    - 只搜索人物: `GET /api/v1/search?q=女儿&category=person`
    - 搜索宪法层: `GET /api/v1/search?q=我是谁&layer=constitution`
    """
    service = get_search_service()

    results = service.search(
        query=q,
        limit=limit,
        layer=layer,
        category=category,
        only_active=only_active,
    )

    return SearchResponse(
        query=q,
        results=[SearchResult(**r) for r in results],
        total=len(results),
    )


@router.get("/search/stats", response_model=IndexStats)
async def get_search_stats():
    """
    获取搜索索引统计信息。

    返回索引中的便利贴总数、向量维度等信息。
    """
    service = get_search_service()
    stats = service.get_stats()
    return IndexStats(**stats)


# 导出
__all__ = ["router"]
