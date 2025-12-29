"""Graph API - 记忆图谱接口"""

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Query

from backend.models.graph import EdgeType, GraphData, GraphFilter
from backend.services.graph_service import get_graph_service

router = APIRouter(prefix="/graph", tags=["graph"])


@router.get("", response_model=GraphData)
async def get_graph(
    layers: Annotated[
        list[str] | None,
        Query(description="筛选的层级列表（如 identity_schema, event_log）"),
    ] = None,
    categories: Annotated[
        list[str] | None,
        Query(description="筛选的分类列表（如 person, event）"),
    ] = None,
    start_time: Annotated[
        datetime | None,
        Query(description="开始时间（ISO 8601）"),
    ] = None,
    end_time: Annotated[
        datetime | None,
        Query(description="结束时间（ISO 8601）"),
    ] = None,
    limit: Annotated[
        int,
        Query(ge=1, le=2000, description="最大节点数"),
    ] = 500,
    edge_types: Annotated[
        list[str] | None,
        Query(description="包含的边类型（time_sequence, shared_category）"),
    ] = None,
) -> GraphData:
    """
    获取记忆图谱数据

    返回节点（记忆）和边（关系）的完整图结构，用于前端 D3.js 可视化。

    节点按 layer 分色：
    - identity_schema (L0): 红色
    - event_log (L2): 蓝色
    - verified_fact (L3): 绿色
    - operational_knowledge (L4): 紫色

    边类型：
    - time_sequence: 时间序列（虚线）
    - shared_category: 共享分类（实线）
    """
    # 解析边类型
    include_edges = []
    if edge_types:
        for et in edge_types:
            try:
                include_edges.append(EdgeType(et))
            except ValueError:
                pass
    if not include_edges:
        include_edges = [EdgeType.TIME_SEQUENCE, EdgeType.SHARED_CATEGORY]

    filter_params = GraphFilter(
        layers=layers,
        categories=categories,
        start_time=start_time,
        end_time=end_time,
        limit=limit,
        include_edges=include_edges,
    )

    service = get_graph_service()
    return service.build_graph(filter_params)


@router.get("/stats")
async def get_graph_stats() -> dict:
    """
    获取图谱统计信息

    返回各层级和分类的记忆数量，用于前端筛选器。
    """
    service = get_graph_service()
    graph = service.build_graph(GraphFilter(limit=2000))

    return {
        "total_nodes": graph.node_count,
        "total_edges": graph.edge_count,
        "layer_stats": graph.layer_stats,
        "category_stats": graph.category_stats,
    }
