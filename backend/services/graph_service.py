"""Graph Service - 图谱数据构建服务"""

from collections import defaultdict
from datetime import datetime

from backend.models.graph import (
    EdgeType,
    GraphData,
    GraphEdge,
    GraphFilter,
    GraphNode,
)
from backend.models.note import MemoryLayer
from backend.services.search import SearchService

# 层级颜色映射（与前端保持一致）
LAYER_COLORS = {
    "identity_schema": "#ef4444",  # 红色 - L0 核心身份
    "constitution": "#ef4444",  # 兼容旧术语
    "active_context": "#f97316",  # 橙色 - L1 工作记忆
    "event_log": "#3b82f6",  # 蓝色 - L2 事件日志
    "session": "#3b82f6",  # 兼容旧术语
    "verified_fact": "#22c55e",  # 绿色 - L3 验证事实
    "fact": "#22c55e",  # 兼容旧术语
    "operational_knowledge": "#a855f7",  # 紫色 - L4 操作知识
}

# 分类颜色映射
CATEGORY_COLORS = {
    "person": "#ec4899",  # 粉色
    "place": "#14b8a6",  # 青色
    "event": "#f59e0b",  # 琥珀色
    "item": "#6366f1",  # 靛蓝色
    "routine": "#84cc16",  # 亮绿色
}

# 边类型样式
EDGE_STYLES = {
    EdgeType.TIME_SEQUENCE: {"color": "#94a3b8", "dashed": True},  # 灰色虚线
    EdgeType.SHARED_CATEGORY: {"color": "#84cc16", "dashed": False},  # 绿色实线
    EdgeType.SHARED_LAYER: {"color": "#60a5fa", "dashed": False},  # 蓝色实线
    EdgeType.SEMANTIC_SIMILAR: {"color": "#f472b6", "dashed": False},  # 粉色实线
}


class GraphService:
    """图谱服务：从记忆数据构建图结构"""

    def __init__(self, search_service: SearchService | None = None):
        self._search_service = search_service or SearchService()

    def build_graph(self, filter_params: GraphFilter | None = None) -> GraphData:
        """
        构建记忆图谱

        Args:
            filter_params: 筛选条件

        Returns:
            GraphData 包含节点和边
        """
        filter_params = filter_params or GraphFilter()

        # 1. 获取记忆列表
        notes = self._fetch_notes(filter_params)

        if not notes:
            return GraphData(node_count=0, edge_count=0)

        # 2. 构建节点
        nodes = self._build_nodes(notes)

        # 3. 构建边
        edges = self._build_edges(notes, filter_params.include_edges)

        # 4. 统计信息
        layer_stats = defaultdict(int)
        category_stats = defaultdict(int)
        for node in nodes:
            layer_stats[node.layer] += 1
            if node.category:
                category_stats[node.category] += 1

        return GraphData(
            nodes=nodes,
            edges=edges,
            node_count=len(nodes),
            edge_count=len(edges),
            layer_stats=dict(layer_stats),
            category_stats=dict(category_stats),
        )

    def _fetch_notes(self, filter_params: GraphFilter) -> list[dict]:
        """获取符合条件的记忆"""
        all_notes = []

        # 按层级获取（如果指定了层级）
        layers = filter_params.layers or [
            "identity_schema",
            "event_log",
            "verified_fact",
            "operational_knowledge",
        ]

        for layer in layers:
            try:
                notes = self._search_service.list_notes(
                    layer=layer,
                    limit=filter_params.limit,
                )
                all_notes.extend(notes)
            except Exception:
                # 某些层级可能为空，忽略错误
                pass

        # 过滤分类
        if filter_params.categories:
            all_notes = [
                n for n in all_notes
                if n.get("category") in filter_params.categories
            ]

        # 过滤时间范围
        if filter_params.start_time or filter_params.end_time:
            filtered = []
            for n in all_notes:
                created_at = n.get("created_at")
                if isinstance(created_at, str):
                    try:
                        created_at = datetime.fromisoformat(
                            created_at.replace("Z", "+00:00")
                        )
                    except ValueError:
                        continue
                if filter_params.start_time and created_at < filter_params.start_time:
                    continue
                if filter_params.end_time and created_at > filter_params.end_time:
                    continue
                filtered.append(n)
            all_notes = filtered

        # 限制数量
        return all_notes[: filter_params.limit]

    def _build_nodes(self, notes: list[dict]) -> list[GraphNode]:
        """构建图谱节点"""
        nodes = []
        for note in notes:
            note_id = str(note.get("id", ""))
            layer = note.get("layer", "verified_fact")
            category = note.get("category")
            content = note.get("content", "")

            # 生成标签（截取前 50 字符）
            label = content[:50] + "..." if len(content) > 50 else content

            # 解析创建时间
            created_at = note.get("created_at")
            if isinstance(created_at, str):
                try:
                    created_at = datetime.fromisoformat(
                        created_at.replace("Z", "+00:00")
                    )
                except ValueError:
                    created_at = datetime.now()
            elif not isinstance(created_at, datetime):
                created_at = datetime.now()

            # 节点大小根据置信度调整
            confidence = float(note.get("confidence", 0.5))
            size = int(8 + confidence * 12)  # 8-20

            nodes.append(
                GraphNode(
                    id=note_id,
                    label=label,
                    layer=layer,
                    category=category,
                    created_at=created_at,
                    color=LAYER_COLORS.get(layer, "#888888"),
                    size=size,
                    content=content,
                    confidence=confidence,
                )
            )

        return nodes

    def _build_edges(
        self, notes: list[dict], include_edges: list[EdgeType]
    ) -> list[GraphEdge]:
        """构建图谱边"""
        edges = []

        # 按时间排序（用于时间序列边）
        sorted_notes = sorted(
            notes,
            key=lambda n: n.get("created_at", ""),
        )

        # 1. 时间序列边：相邻时间的记忆连接
        if EdgeType.TIME_SEQUENCE in include_edges:
            for i in range(len(sorted_notes) - 1):
                source_id = str(sorted_notes[i].get("id", ""))
                target_id = str(sorted_notes[i + 1].get("id", ""))
                if source_id and target_id:
                    style = EDGE_STYLES[EdgeType.TIME_SEQUENCE]
                    edges.append(
                        GraphEdge(
                            source=source_id,
                            target=target_id,
                            edge_type=EdgeType.TIME_SEQUENCE,
                            weight=0.3,  # 时间序列权重较低
                            color=style["color"],
                            dashed=style["dashed"],
                        )
                    )

        # 2. 共享分类边：相同 category 的记忆连接
        if EdgeType.SHARED_CATEGORY in include_edges:
            category_groups = defaultdict(list)
            for note in notes:
                category = note.get("category")
                if category:
                    category_groups[category].append(str(note.get("id", "")))

            for category, ids in category_groups.items():
                if len(ids) < 2:
                    continue
                # 只连接前 10 个，避免边过多
                for i in range(min(len(ids) - 1, 10)):
                    for j in range(i + 1, min(len(ids), 10)):
                        style = EDGE_STYLES[EdgeType.SHARED_CATEGORY]
                        edges.append(
                            GraphEdge(
                                source=ids[i],
                                target=ids[j],
                                edge_type=EdgeType.SHARED_CATEGORY,
                                weight=0.7,  # 共享分类权重较高
                                color=CATEGORY_COLORS.get(category, style["color"]),
                                dashed=style["dashed"],
                            )
                        )

        # 3. 共享层级边：相同 layer 的记忆连接（可选，默认不启用）
        if EdgeType.SHARED_LAYER in include_edges:
            layer_groups = defaultdict(list)
            for note in notes:
                layer = note.get("layer", "verified_fact")
                layer_groups[layer].append(str(note.get("id", "")))

            for layer, ids in layer_groups.items():
                if len(ids) < 2:
                    continue
                # 只连接前 5 个
                for i in range(min(len(ids) - 1, 5)):
                    for j in range(i + 1, min(len(ids), 5)):
                        style = EDGE_STYLES[EdgeType.SHARED_LAYER]
                        edges.append(
                            GraphEdge(
                                source=ids[i],
                                target=ids[j],
                                edge_type=EdgeType.SHARED_LAYER,
                                weight=0.5,
                                color=LAYER_COLORS.get(layer, style["color"]),
                                dashed=style["dashed"],
                            )
                        )

        return edges


# 单例
_graph_service: GraphService | None = None


def get_graph_service() -> GraphService:
    """获取 GraphService 单例"""
    global _graph_service
    if _graph_service is None:
        _graph_service = GraphService()
    return _graph_service
