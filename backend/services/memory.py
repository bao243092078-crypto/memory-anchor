"""
Memory Service - 统一记忆管理服务

协调 Note Repository + Search Service，实现三层记忆模型的读写逻辑。
基于 docs/MEMORY_STRATEGY.md 的策略定义。

支持两种宪法层来源：
1. YAML 配置文件（优先）：~/.memory-anchor/projects/{project}/constitution.yaml
2. Qdrant 向量数据库（向后兼容）：动态添加的宪法层条目
"""

import asyncio
from datetime import datetime
from enum import Enum
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from backend.core.memory_kernel import MemoryKernel
from backend.models.note import MemoryLayer, NoteCategory


class MemorySource(str, Enum):
    """记忆来源"""
    CAREGIVER = "caregiver"  # 照护者手动输入
    AI_EXTRACTION = "ai_extraction"  # AI自动提取
    PATIENT = "patient"  # 患者自述


class MemoryAddRequest(BaseModel):
    """添加记忆请求"""
    content: str = Field(..., min_length=1, max_length=2000)
    layer: MemoryLayer = MemoryLayer.FACT
    category: Optional[NoteCategory] = None
    source: MemorySource = MemorySource.CAREGIVER
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    requires_approval: bool = False
    expires_at: Optional[datetime] = None

    # 可追溯性字段（v2.1 新增，由系统自动填充）
    session_id: Optional[str] = Field(default=None, description="记录时的会话 ID")
    related_files: Optional[list[str]] = Field(default=None, description="关联的文件列表")

    @field_validator("layer", mode="before")
    @classmethod
    def normalize_layer(cls, v):
        """支持 v1.x 旧术语 (constitution/fact/session)"""
        if isinstance(v, str):
            return MemoryLayer.from_string(v)
        return v


class MemorySearchRequest(BaseModel):
    """搜索记忆请求"""
    query: str = Field(..., min_length=1)
    layer: Optional[MemoryLayer] = None
    category: Optional[NoteCategory] = None
    include_constitution: bool = True  # 是否始终包含宪法层
    limit: int = Field(default=5, ge=1, le=20)
    min_score: float = Field(default=0.3, ge=0.0, le=1.0)
    # Bi-temporal 时间查询 (v3.0 新增)
    as_of: Optional[str] = Field(default=None, description="时间点查询 (ISO 8601)")
    start_time: Optional[str] = Field(default=None, description="范围查询开始时间")
    end_time: Optional[str] = Field(default=None, description="范围查询结束时间")
    include_expired: bool = Field(default=False, description="是否包含已过期记忆")

    @field_validator("layer", mode="before")
    @classmethod
    def normalize_layer(cls, v):
        """支持 v1.x 旧术语 (constitution/fact/session)"""
        if v is None:
            return v
        if isinstance(v, str):
            return MemoryLayer.from_string(v)
        return v


class MemoryResult(BaseModel):
    """记忆搜索结果"""
    id: UUID
    content: str
    layer: MemoryLayer
    category: Optional[NoteCategory]
    score: float
    source: Optional[str] = None
    confidence: float = 1.0
    is_constitution: bool = False  # 标记是否为宪法层（始终显示）

    # 可追溯性字段（v2.1 新增）
    session_id: Optional[str] = None  # 记录时的会话 ID
    related_files: Optional[list[str]] = None  # 关联的文件列表


class MemoryService:
    """
    统一记忆管理服务

    职责：
    1. 协调 Note 存储和 Search 索引
    2. 实现三层记忆的读写规则
    3. 处理置信度分级和审批流程
    """

    def __init__(self, note_repo=None, search_service=None):
        """
        初始化记忆服务

        Args:
            note_repo: Note 仓库（可选，延迟注入）
            search_service: 搜索服务（可选，延迟注入）
        """
        self._note_repo = note_repo
        self._search_service = search_service
        self._kernel: Optional[MemoryKernel] = None

    @property
    def note_repo(self):
        """Note 仓库（预留）。MVP 阶段可为 None。"""
        return self._note_repo

    @property
    def search_service(self):
        """延迟获取搜索服务"""
        if self._search_service is None:
            from backend.services.search import get_search_service
            self._search_service = get_search_service()
        return self._search_service

    @property
    def kernel(self) -> MemoryKernel:
        """统一核心逻辑入口（同步），供 HTTP/MCP/SDK 共用。"""
        if self._kernel is None:
            # 使用全局单例，确保 SDK 和 MCP 使用同一个实例
            from backend.core.memory_kernel import get_memory_kernel
            self._kernel = get_memory_kernel(self.search_service, self.note_repo)
        return self._kernel

    @staticmethod
    def _to_uuid(value: object) -> UUID:
        if isinstance(value, UUID):
            return value
        return UUID(str(value))

    @staticmethod
    def _to_category(value: object | None) -> Optional[NoteCategory]:
        if value is None:
            return None
        try:
            return NoteCategory(str(value))
        except ValueError:
            return None

    @staticmethod
    def _to_layer(value: object | None) -> MemoryLayer:
        if value is None:
            return MemoryLayer.FACT
        try:
            return MemoryLayer(str(value))
        except ValueError:
            return MemoryLayer.FACT

    def _dict_to_memory_result(self, data: dict) -> MemoryResult:
        return MemoryResult(
            id=self._to_uuid(data.get("id")),
            content=str(data.get("content", "")),
            layer=self._to_layer(data.get("layer")),
            category=self._to_category(data.get("category")),
            score=float(data.get("score", 0.0) or 0.0),
            source=data.get("source"),
            confidence=float(data["confidence"]) if data.get("confidence") is not None else 1.0,
            is_constitution=bool(data.get("is_constitution", False)),
            # 可追溯性字段
            session_id=data.get("session_id"),
            related_files=data.get("related_files"),
        )

    async def add_memory(self, request: MemoryAddRequest) -> dict:
        """
        添加记忆

        遵循 MEMORY_STRATEGY.md 的规则：
        - 宪法层：仅照护者可写，需二次确认（此API不直接写宪法层）
        - 事实层：置信度分级处理
        - 会话层：自动记录

        Returns:
            {"id": UUID, "status": "saved" | "pending_approval", "layer": str}
        """
        # 宪法层保护：不允许通过此API直接写入
        if request.layer == MemoryLayer.CONSTITUTION:
            if request.source != MemorySource.CAREGIVER:
                raise ValueError("宪法层只能由照护者创建")
            # 即使是照护者，也需要通过专门的宪法层API
            raise ValueError("宪法层创建请使用专用API（需二次确认）")

        return await asyncio.to_thread(
            self.kernel.add_memory,
            content=request.content,
            layer=request.layer.value,
            category=request.category.value if request.category else None,
            source=request.source.value,
            confidence=request.confidence,
            expires_at=request.expires_at,
            requires_approval=request.requires_approval,
            # 可追溯性字段
            session_id=request.session_id,
            related_files=request.related_files,
        )

    async def search_memory(self, request: MemorySearchRequest) -> list[MemoryResult]:
        """
        搜索记忆

        遵循 MEMORY_STRATEGY.md 的检索策略：
        - Layer 0: 宪法层始终预加载（不检索）
        - Layer 1-3: 语义检索 + 关键词混合

        Bi-temporal 查询 (v3.0)：
        - as_of: 查询某时刻有效的记忆
        - start_time/end_time: 查询时间范围内的记忆
        - include_expired: 是否包含已过期记忆

        Returns:
            MemoryResult 列表
        """
        raw_results = await asyncio.to_thread(
            self.kernel.search_memory,
            query=request.query,
            layer=request.layer.value if request.layer else None,
            category=request.category.value if request.category else None,
            limit=request.limit,
            min_score=request.min_score,
            include_constitution=request.include_constitution,
            # Bi-temporal 时间查询 (v3.0 新增)
            as_of=request.as_of,
            start_time=request.start_time,
            end_time=request.end_time,
            include_expired=request.include_expired,
        )

        return [self._dict_to_memory_result(r) for r in raw_results]

    async def get_constitution(self) -> list[MemoryResult]:
        """
        获取全部宪法层记忆

        宪法层始终全量加载，不依赖检索。

        来源优先级：
        1. YAML 配置文件（~/.memory-anchor/projects/{project}/constitution.yaml）
        2. Qdrant 向量数据库（动态添加的宪法层条目，向后兼容）

        两个来源会合并返回，YAML 条目在前。
        """
        raw_results = await asyncio.to_thread(self.kernel.get_constitution)
        return [self._dict_to_memory_result(r) for r in raw_results]


# 全局单例
_memory_service: Optional[MemoryService] = None


def get_memory_service() -> MemoryService:
    """获取记忆服务单例"""
    global _memory_service
    if _memory_service is None:
        _memory_service = MemoryService()
    return _memory_service


def reset_memory_service():
    """重置记忆服务单例（用于 MCP 启动时重新加载配置）"""
    global _memory_service
    _memory_service = None


__all__ = [
    "MemoryService",
    "MemoryAddRequest",
    "MemorySearchRequest",
    "MemoryResult",
    "MemorySource",
    "get_memory_service",
    "reset_memory_service",
]
