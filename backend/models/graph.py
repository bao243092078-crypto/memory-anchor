"""Graph data models for memory visualization - 记忆图谱数据模型"""

from datetime import datetime
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, Field


class EdgeType(str, Enum):
    """边的类型"""

    TIME_SEQUENCE = "time_sequence"  # 时间序列：按创建时间相邻
    SHARED_CATEGORY = "shared_category"  # 共享分类：相同 category
    SHARED_LAYER = "shared_layer"  # 共享层级：相同 layer
    SEMANTIC_SIMILAR = "semantic_similar"  # 语义相似：向量距离近（预留）


class GraphNode(BaseModel):
    """图谱节点（记忆）"""

    id: str = Field(..., description="节点 ID（记忆 UUID）")
    label: str = Field(..., description="节点标签（记忆内容摘要）")
    layer: str = Field(..., description="记忆层级")
    category: str | None = Field(default=None, description="记忆分类")
    created_at: datetime = Field(..., description="创建时间")

    # 可视化属性
    color: str = Field(default="#888888", description="节点颜色（按 layer 分配）")
    size: int = Field(default=10, description="节点大小")

    # 原始数据（用于详情展示）
    content: str = Field(..., description="完整内容")
    confidence: float = Field(default=1.0, description="置信度")


class GraphEdge(BaseModel):
    """图谱边（关系）"""

    source: str = Field(..., description="源节点 ID")
    target: str = Field(..., description="目标节点 ID")
    edge_type: EdgeType = Field(..., description="边类型")
    weight: float = Field(default=1.0, ge=0.0, le=1.0, description="边权重")

    # 可视化属性
    color: str = Field(default="#cccccc", description="边颜色")
    dashed: bool = Field(default=False, description="是否虚线")


class GraphData(BaseModel):
    """完整图谱数据"""

    nodes: list[GraphNode] = Field(default_factory=list, description="节点列表")
    edges: list[GraphEdge] = Field(default_factory=list, description="边列表")

    # 统计信息
    node_count: int = Field(default=0, description="节点总数")
    edge_count: int = Field(default=0, description="边总数")
    layer_stats: dict[str, int] = Field(default_factory=dict, description="各层级节点数")
    category_stats: dict[str, int] = Field(default_factory=dict, description="各分类节点数")


class GraphFilter(BaseModel):
    """图谱筛选条件"""

    layers: list[str] | None = Field(default=None, description="筛选的层级列表")
    categories: list[str] | None = Field(default=None, description="筛选的分类列表")
    start_time: datetime | None = Field(default=None, description="开始时间")
    end_time: datetime | None = Field(default=None, description="结束时间")
    limit: int = Field(default=500, ge=1, le=2000, description="最大节点数")
    include_edges: list[EdgeType] = Field(
        default_factory=lambda: [EdgeType.TIME_SEQUENCE, EdgeType.SHARED_CATEGORY],
        description="包含的边类型"
    )
