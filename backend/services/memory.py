"""
Memory Service - 统一记忆管理服务

协调 Note Repository + Search Service，实现三层记忆模型的读写逻辑。
基于 docs/MEMORY_STRATEGY.md 的策略定义。

支持两种宪法层来源：
1. YAML 配置文件（优先）：~/.memory-anchor/projects/{project}/constitution.yaml
2. Qdrant 向量数据库（向后兼容）：动态添加的宪法层条目
"""

from typing import Optional
from uuid import UUID, uuid4
from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field

from backend.models.note import MemoryLayer, NoteCategory
from backend.config import get_config, ConstitutionItem


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


class MemorySearchRequest(BaseModel):
    """搜索记忆请求"""
    query: str = Field(..., min_length=1)
    layer: Optional[MemoryLayer] = None
    category: Optional[NoteCategory] = None
    include_constitution: bool = True  # 是否始终包含宪法层
    limit: int = Field(default=5, ge=1, le=20)
    min_score: float = Field(default=0.3, ge=0.0, le=1.0)


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

    @property
    def note_repo(self):
        """延迟获取 Note 仓库"""
        if self._note_repo is None:
            # 导入放在这里避免循环引用
            from backend.services.note_repository import get_note_repository
            self._note_repo = get_note_repository()
        return self._note_repo

    @property
    def search_service(self):
        """延迟获取搜索服务"""
        if self._search_service is None:
            from backend.services.search import get_search_service
            self._search_service = get_search_service()
        return self._search_service

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

        # 置信度分级处理（仅AI提取）
        if request.source == MemorySource.AI_EXTRACTION:
            if request.confidence >= 0.9:
                # 高置信度：直接存入事实层
                status = "saved"
                requires_approval = False
            elif request.confidence >= 0.7:
                # 中置信度：存入待确认区
                status = "pending_approval"
                requires_approval = True
            else:
                # 低置信度：记录日志但不存储
                return {
                    "id": None,
                    "status": "rejected_low_confidence",
                    "layer": request.layer.value,
                    "confidence": request.confidence,
                    "reason": "置信度低于0.7，不予存储"
                }
        else:
            # 照护者/患者输入：直接存储
            status = "saved"
            requires_approval = request.requires_approval

        # 创建 Note
        note_id = uuid4()
        now = datetime.now()

        # 存储到数据库
        note_data = {
            "id": note_id,
            "content": request.content,
            "layer": request.layer.value,
            "category": request.category.value if request.category else None,
            "confidence": request.confidence,
            "created_by": request.source.value,
            "created_at": now,
            "expires_at": request.expires_at,
            "is_active": not requires_approval,  # 待审批的先设为非激活
        }

        # 如果有 note_repo，存储到数据库
        # （MVP阶段可能只存索引）

        # 索引到向量数据库
        if not requires_approval:
            self.search_service.index_note(
                note_id=note_id,
                content=request.content,
                layer=request.layer.value,
                category=request.category.value if request.category else None,
                is_active=True,
            )

        return {
            "id": note_id,
            "status": status,
            "layer": request.layer.value,
            "confidence": request.confidence,
            "requires_approval": requires_approval,
        }

    async def search_memory(self, request: MemorySearchRequest) -> list[MemoryResult]:
        """
        搜索记忆

        遵循 MEMORY_STRATEGY.md 的检索策略：
        - Layer 0: 宪法层始终预加载（不检索）
        - Layer 1-3: 语义检索 + 关键词混合

        Returns:
            MemoryResult 列表
        """
        results = []

        # 1. 如果需要，先加载宪法层（始终可见）
        if request.include_constitution:
            constitution_results = self.search_service.search(
                query=request.query,
                layer=MemoryLayer.CONSTITUTION.value,
                limit=10,  # 宪法层通常不多
            )
            for r in constitution_results:
                results.append(MemoryResult(
                    id=UUID(r["id"]),
                    content=r["content"],
                    layer=MemoryLayer.CONSTITUTION,
                    category=NoteCategory(r["category"]) if r.get("category") else None,
                    score=r["score"],
                    confidence=1.0,  # 宪法层置信度始终为1
                    is_constitution=True,
                ))

        # 2. 搜索指定层（或事实层+会话层）
        search_layer = request.layer.value if request.layer else None

        # 如果指定了宪法层，跳过（已在上面处理）
        if request.layer != MemoryLayer.CONSTITUTION:
            search_results = self.search_service.search(
                query=request.query,
                layer=search_layer,
                category=request.category.value if request.category else None,
                limit=request.limit,
            )

            for r in search_results:
                # 过滤低分结果
                if r["score"] < request.min_score:
                    continue

                # 跳过已添加的宪法层结果
                if r.get("layer") == MemoryLayer.CONSTITUTION.value:
                    continue

                results.append(MemoryResult(
                    id=UUID(r["id"]),
                    content=r["content"],
                    layer=MemoryLayer(r["layer"]),
                    category=NoteCategory(r["category"]) if r.get("category") else None,
                    score=r["score"],
                    confidence=r.get("confidence", 1.0),
                    is_constitution=False,
                ))

        # 3. 按分数排序，但宪法层始终在前
        constitution_results = [r for r in results if r.is_constitution]
        other_results = [r for r in results if not r.is_constitution]
        other_results.sort(key=lambda x: x.score, reverse=True)

        return constitution_results + other_results[:request.limit]

    async def get_constitution(self) -> list[MemoryResult]:
        """
        获取全部宪法层记忆

        宪法层始终全量加载，不依赖检索。

        来源优先级：
        1. YAML 配置文件（~/.memory-anchor/projects/{project}/constitution.yaml）
        2. Qdrant 向量数据库（动态添加的宪法层条目，向后兼容）

        两个来源会合并返回，YAML 条目在前。
        """
        results = []

        # 1. 从 YAML 配置加载宪法层（优先）
        config = get_config()
        for item in config.constitution:
            # 将 ConstitutionItem 转为 MemoryResult
            category = None
            if item.category:
                try:
                    category = NoteCategory(item.category)
                except ValueError:
                    pass  # 忽略无效分类

            results.append(MemoryResult(
                id=uuid4(),  # YAML 条目生成临时 UUID
                content=item.content,
                layer=MemoryLayer.CONSTITUTION,
                category=category,
                score=1.0,  # 宪法层分数始终为1
                source=f"yaml:{item.id}",  # 标记来源
                confidence=1.0,
                is_constitution=True,
            ))

        # 2. 从 Qdrant 加载动态添加的宪法层条目（向后兼容）
        try:
            qdrant_results = self.search_service.search(
                query="",  # 空查询获取全部
                layer=MemoryLayer.CONSTITUTION.value,
                limit=config.max_constitution_items,
            )

            # 如果空查询不工作，用通用查询
            if not qdrant_results:
                qdrant_results = self.search_service.search(
                    query="核心信息",
                    layer=MemoryLayer.CONSTITUTION.value,
                    limit=config.max_constitution_items,
                )

            for r in qdrant_results:
                results.append(MemoryResult(
                    id=UUID(r["id"]),
                    content=r["content"],
                    layer=MemoryLayer.CONSTITUTION,
                    category=NoteCategory(r["category"]) if r.get("category") else None,
                    score=1.0,
                    source="qdrant",  # 标记来源
                    confidence=1.0,
                    is_constitution=True,
                ))
        except Exception:
            # Qdrant 不可用时仍返回 YAML 条目
            pass

        return results


# 全局单例
_memory_service: Optional[MemoryService] = None


def get_memory_service() -> MemoryService:
    """获取记忆服务单例"""
    global _memory_service
    if _memory_service is None:
        _memory_service = MemoryService()
    return _memory_service


__all__ = [
    "MemoryService",
    "MemoryAddRequest",
    "MemorySearchRequest",
    "MemoryResult",
    "MemorySource",
    "get_memory_service",
]
