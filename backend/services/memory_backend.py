"""
Memory Backend - 可插拔的记忆存储后端抽象

设计目标：
1. Skill 和 MCP 层只依赖此接口，不直接依赖 Qdrant/ChromaDB/MemOS
2. 底层引擎可随时替换（Qdrant → mcp-memory-service → MemOS）
3. 统一的 CRUD + 搜索接口

架构：
    Skill (行为层)
        ↓
    MCP Server (接口层)
        ↓
    MemoryBackend (抽象接口)  ← 这个文件
        ↓
    QdrantBackend / McpMemoryServiceBackend / MemOSBackend (具体实现)
"""

import os
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Literal, Optional, Protocol, runtime_checkable
from uuid import UUID, uuid4

# === 核心数据结构 ===


class MemoryLayer(str, Enum):
    """记忆层级"""
    CONSTITUTION = "constitution"  # 宪法层：核心身份，需三次审批修改
    FACT = "fact"                  # 事实层：长期记忆，经过验证
    SESSION = "session"            # 会话层：短期记忆，24h内


class MemoryCategory(str, Enum):
    """记忆分类"""
    PERSON = "person"      # 人物
    PLACE = "place"        # 地点
    EVENT = "event"        # 事件
    ITEM = "item"          # 物品
    ROUTINE = "routine"    # 日常习惯
    DECISION = "decision"  # 决策记录（开发场景）
    BUGFIX = "bugfix"      # Bug修复记录
    CONTEXT = "context"    # 上下文背景


@dataclass
class MemoryItem:
    """统一的记忆条目"""
    id: UUID
    content: str
    layer: MemoryLayer
    category: Optional[MemoryCategory] = None
    confidence: float = 1.0
    score: float = 0.0  # 搜索相关度
    source: Optional[str] = None  # caregiver / ai_extraction / patient
    created_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    metadata: dict = field(default_factory=dict)

    @property
    def is_constitution(self) -> bool:
        return self.layer == MemoryLayer.CONSTITUTION


@dataclass
class SearchRequest:
    """搜索请求"""
    query: str
    layer: Optional[MemoryLayer] = None
    category: Optional[MemoryCategory] = None
    include_constitution: bool = True  # 是否始终包含宪法层
    limit: int = 5
    min_score: float = 0.3


@dataclass
class AddRequest:
    """添加记忆请求"""
    content: str
    layer: MemoryLayer = MemoryLayer.FACT
    category: Optional[MemoryCategory] = None
    confidence: float = 1.0
    source: str = "caregiver"
    expires_at: Optional[datetime] = None
    metadata: dict = field(default_factory=dict)


@dataclass
class AddResult:
    """添加记忆结果"""
    id: Optional[UUID]
    status: str  # saved / pending_approval / rejected
    layer: str
    confidence: float
    requires_approval: bool = False
    reason: Optional[str] = None


# === 抽象后端接口 ===


@runtime_checkable
class MemoryBackend(Protocol):
    """
    可插拔的记忆后端接口

    所有具体实现（Qdrant、mcp-memory-service、MemOS）必须实现此协议。
    Skill 和 MCP 层只依赖此接口。
    """

    async def search(self, request: SearchRequest) -> list[MemoryItem]:
        """
        搜索记忆

        规则：
        - 如果 include_constitution=True，宪法层始终预加载在结果最前面
        - 其他层按相关度排序
        - 结果数量不超过 limit
        """
        ...

    async def add(self, request: AddRequest) -> AddResult:
        """
        添加记忆

        规则：
        - 宪法层不允许通过此方法添加（需专用流程）
        - AI 提取的记忆按置信度分级：
          - ≥0.9: 直接存入
          - 0.7-0.9: 待确认
          - <0.7: 拒绝
        """
        ...

    async def get_constitution(self) -> list[MemoryItem]:
        """
        获取全部宪法层记忆

        宪法层始终全量返回，不依赖检索。
        """
        ...

    async def get_by_id(self, memory_id: UUID) -> Optional[MemoryItem]:
        """根据 ID 获取单条记忆"""
        ...

    async def delete(self, memory_id: UUID) -> bool:
        """删除记忆"""
        ...

    async def get_timeline(
        self,
        since: Optional[datetime] = None,
        limit: int = 20
    ) -> list[MemoryItem]:
        """
        获取时间线（最近记忆）

        用于回顾最近发生的事情。
        """
        ...


class AbstractMemoryBackend(ABC):
    """
    抽象基类实现

    提供通用逻辑（如置信度分级），子类只需实现存储相关方法。
    """

    # 置信度阈值（可配置）
    HIGH_CONFIDENCE_THRESHOLD = 0.9
    MID_CONFIDENCE_THRESHOLD = 0.7

    @abstractmethod
    async def _do_search(
        self,
        query: str,
        layer: Optional[str] = None,
        category: Optional[str] = None,
        limit: int = 10
    ) -> list[dict]:
        """实际执行搜索（子类实现）"""
        pass

    @abstractmethod
    async def _do_index(
        self,
        memory_id: UUID,
        content: str,
        layer: str,
        category: Optional[str],
        metadata: dict
    ) -> bool:
        """实际执行索引（子类实现）"""
        pass

    @abstractmethod
    async def _do_delete(self, memory_id: UUID) -> bool:
        """实际执行删除（子类实现）"""
        pass

    async def search(self, request: SearchRequest) -> list[MemoryItem]:
        """搜索记忆（通用逻辑）"""
        results = []

        # 1. 如果需要，先加载宪法层
        if request.include_constitution:
            constitution_results = await self._do_search(
                query=request.query,
                layer=MemoryLayer.CONSTITUTION.value,
                limit=10
            )
            for r in constitution_results:
                results.append(self._dict_to_memory_item(r, is_constitution=True))

        # 2. 搜索指定层
        if request.layer != MemoryLayer.CONSTITUTION:
            layer_value = request.layer.value if request.layer else None
            category_value = request.category.value if request.category else None

            search_results = await self._do_search(
                query=request.query,
                layer=layer_value,
                category=category_value,
                limit=request.limit
            )

            for r in search_results:
                # 跳过低分结果
                if r.get("score", 0) < request.min_score:
                    continue
                # 跳过已添加的宪法层
                if r.get("layer") == MemoryLayer.CONSTITUTION.value:
                    continue
                results.append(self._dict_to_memory_item(r))

        # 3. 排序：宪法层在前，其他按分数
        constitution = [r for r in results if r.is_constitution]
        others = sorted(
            [r for r in results if not r.is_constitution],
            key=lambda x: x.score,
            reverse=True
        )

        return constitution + others[:request.limit]

    async def add(self, request: AddRequest) -> AddResult:
        """添加记忆（通用逻辑）"""
        # 宪法层保护
        if request.layer == MemoryLayer.CONSTITUTION:
            return AddResult(
                id=None,
                status="rejected",
                layer=request.layer.value,
                confidence=request.confidence,
                reason="宪法层只能通过专用流程创建"
            )

        # 置信度分级（仅 AI 提取）
        if request.source == "ai_extraction":
            if request.confidence >= self.HIGH_CONFIDENCE_THRESHOLD:
                status = "saved"
                requires_approval = False
            elif request.confidence >= self.MID_CONFIDENCE_THRESHOLD:
                status = "pending_approval"
                requires_approval = True
            else:
                return AddResult(
                    id=None,
                    status="rejected",
                    layer=request.layer.value,
                    confidence=request.confidence,
                    reason=f"置信度 {request.confidence:.2f} 低于阈值 {self.MID_CONFIDENCE_THRESHOLD}"
                )
        else:
            status = "saved"
            requires_approval = False

        # 生成 ID 并索引
        memory_id = uuid4()

        if not requires_approval:
            await self._do_index(
                memory_id=memory_id,
                content=request.content,
                layer=request.layer.value,
                category=request.category.value if request.category else None,
                metadata={
                    "source": request.source,
                    "confidence": request.confidence,
                    **request.metadata
                }
            )

        return AddResult(
            id=memory_id,
            status=status,
            layer=request.layer.value,
            confidence=request.confidence,
            requires_approval=requires_approval
        )

    async def get_constitution(self) -> list[MemoryItem]:
        """获取全部宪法层"""
        results = await self._do_search(
            query="",  # 空查询获取全部
            layer=MemoryLayer.CONSTITUTION.value,
            limit=20
        )

        # 如果空查询不工作，用通用查询
        if not results:
            results = await self._do_search(
                query="核心信息",
                layer=MemoryLayer.CONSTITUTION.value,
                limit=20
            )

        return [
            self._dict_to_memory_item(r, is_constitution=True)
            for r in results
        ]

    def _dict_to_memory_item(self, data: dict, is_constitution: bool = False) -> MemoryItem:
        """将字典转换为 MemoryItem"""
        return MemoryItem(
            id=UUID(data["id"]) if isinstance(data.get("id"), str) else data.get("id", uuid4()),
            content=data.get("content", ""),
            layer=MemoryLayer(data.get("layer", "fact")),
            category=MemoryCategory(data["category"]) if data.get("category") else None,
            confidence=data.get("confidence", 1.0),
            score=data.get("score", 1.0 if is_constitution else 0.0),
            source=data.get("source"),
            metadata=data.get("metadata", {})
        )


# === 后端工厂 ===

# 支持的后端类型
BackendType = Literal["qdrant", "mcp-memory-service"]


def get_memory_backend(
    backend_type: Optional[BackendType] = None
) -> "MemoryBackend":
    """
    获取记忆后端实例（工厂方法）

    优先级：
    1. 显式传入的 backend_type
    2. 环境变量 MEMORY_BACKEND
    3. 默认使用 qdrant

    Args:
        backend_type: 后端类型，可选 "qdrant" 或 "mcp-memory-service"

    Returns:
        MemoryBackend 实例

    示例：
        # 使用默认后端（Qdrant）
        backend = get_memory_backend()

        # 显式指定后端
        backend = get_memory_backend("mcp-memory-service")

        # 通过环境变量切换
        # export MEMORY_BACKEND=mcp-memory-service
        backend = get_memory_backend()

    配置说明：
        - MEMORY_BACKEND: 后端类型 (qdrant | mcp-memory-service)
        - MCP_MEMORY_SERVICE_URL: mcp-memory-service 的 HTTP 地址（默认 http://localhost:3333）
    """
    # 确定后端类型
    selected_backend = backend_type or os.getenv("MEMORY_BACKEND", "qdrant")

    if selected_backend == "mcp-memory-service":
        from backend.services.backends.mcp_memory_service_backend import get_mcp_memory_backend
        return get_mcp_memory_backend()
    else:
        # 默认使用 Qdrant
        from backend.services.backends.qdrant_backend import get_qdrant_backend
        return get_qdrant_backend()


# === 导出 ===


__all__ = [
    "MemoryLayer",
    "MemoryCategory",
    "MemoryItem",
    "SearchRequest",
    "AddRequest",
    "AddResult",
    "MemoryBackend",
    "AbstractMemoryBackend",
    "get_memory_backend",
    "BackendType",
]
