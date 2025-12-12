"""
MemoryKernel - Memory Anchor 核心引擎

纯 Python 同步实现，无 async，无框架依赖。
设计用于多种接入方式：MCP Server (async wrapper) 和 Native SDK (直接调用)。

核心原则：
1. 同步接口 - Codex 等脚本直接调用
2. 依赖注入 - 方便测试和替换存储后端
3. 无状态 - 所有状态在存储层
4. 线程安全 - 使用 Qdrant Server 模式，支持并发
"""

from typing import List, Optional, Dict, Any
from uuid import UUID, uuid4
from datetime import datetime
from enum import Enum

# 导入现有的 models 和 services
from backend.models.note import MemoryLayer, NoteCategory


class MemorySource(str, Enum):
    """记忆来源"""
    CAREGIVER = "caregiver"
    AI_EXTRACTION = "ai_extraction"
    PATIENT = "patient"
    EXTERNAL_AI = "external_ai"  # Codex/Gemini 等外部 AI


class MemoryKernel:
    """
    Memory Anchor 核心引擎（同步版本）

    这是所有 AI "患者"（Claude/Codex/Gemini）访问记忆的统一入口。
    类比：人类的海马体（负责记忆形成和检索）。

    职责：
    - 搜索记忆（三层语义检索）
    - 添加记忆（置信度分级）
    - 管理宪法层（三次审批机制）

    设计原则：
    - 纯 Python，无 async（方便 Codex 等脚本调用）
    - 依赖注入（search_service, note_repo）
    - 无状态（所有状态在存储层）
    - 线程安全（通过 Qdrant Server 模式）
    """

    def __init__(self, search_service, note_repo=None):
        """
        初始化记忆核心

        Args:
            search_service: 搜索服务实例（SearchService）
            note_repo: Note 仓库（可选，用于元数据存储）
        """
        self.search = search_service
        self.notes = note_repo

    def search_memory(
        self,
        query: str,
        layer: Optional[str] = None,
        category: Optional[str] = None,
        limit: int = 5,
        min_score: float = 0.3,
        include_constitution: bool = True,
        agent_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        语义搜索记忆

        Args:
            query: 搜索查询（自然语言）
            layer: 过滤层级（"constitution"/"fact"/"session"）
            category: 过滤分类（"person"/"place"/"event"/"item"/"routine"）
            limit: 返回数量限制
            min_score: 最小相关度分数
            include_constitution: 是否包含宪法层（始终显示）
            agent_id: Agent ID（用于会话层隔离）

        Returns:
            记忆结果列表，每项包含：
            - id: UUID
            - content: 内容
            - layer: 层级
            - category: 分类
            - score: 相关度分数
            - is_constitution: 是否为宪法层
        """
        results = []

        # 1. 如果需要，先加载宪法层（始终可见，所有 AI 共享）
        if include_constitution:
            constitution_results = self.search.search(
                query=query,
                layer=MemoryLayer.CONSTITUTION.value,
                limit=10,
            )
            for r in constitution_results:
                results.append({
                    "id": r["id"],
                    "content": r["content"],
                    "layer": MemoryLayer.CONSTITUTION.value,
                    "category": r.get("category"),
                    "score": r["score"],
                    "confidence": 1.0,
                    "is_constitution": True,
                })

        # 2. 搜索指定层（或事实层+会话层）
        search_layer = layer if layer else None

        # 如果指定了宪法层，跳过（已在上面处理）
        if layer != MemoryLayer.CONSTITUTION.value:
            # 构建过滤条件
            search_kwargs = {
                "query": query,
                "limit": limit,
            }
            if search_layer:
                search_kwargs["layer"] = search_layer
            if category:
                search_kwargs["category"] = category

            search_results = self.search.search(**search_kwargs)

            for r in search_results:
                # 过滤低分结果
                if r["score"] < min_score:
                    continue

                # 跳过已添加的宪法层结果
                if r.get("layer") == MemoryLayer.CONSTITUTION.value:
                    continue

                # 会话层隔离：如果指定了 agent_id，只返回该 agent 的会话
                if r.get("layer") == MemoryLayer.SESSION.value:
                    if agent_id and r.get("agent_id") != agent_id:
                        continue

                results.append({
                    "id": r["id"],
                    "content": r["content"],
                    "layer": r["layer"],
                    "category": r.get("category"),
                    "score": r["score"],
                    "confidence": r.get("confidence", 1.0),
                    "is_constitution": False,
                })

        # 3. 按分数排序，但宪法层始终在前
        constitution_results = [r for r in results if r["is_constitution"]]
        other_results = [r for r in results if not r["is_constitution"]]
        other_results.sort(key=lambda x: x["score"], reverse=True)

        return constitution_results + other_results[:limit]

    def add_memory(
        self,
        content: str,
        layer: str = "fact",
        category: Optional[str] = None,
        source: str = "caregiver",
        confidence: float = 1.0,
        agent_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        添加记忆

        遵循置信度分级规则：
        - ≥0.9: 直接存入
        - 0.7-0.9: 待确认
        - <0.7: 拒绝

        Args:
            content: 记忆内容
            layer: 层级（"fact"/"session"）
            category: 分类
            source: 来源（"caregiver"/"ai_extraction"/"external_ai"）
            confidence: 置信度（0-1）
            agent_id: Agent ID（会话层需要）

        Returns:
            {"id": UUID, "status": "saved"/"pending_approval"/"rejected", ...}
        """
        # 🔴 红线：宪法层保护
        if layer == "constitution":
            if source != "caregiver":
                raise PermissionError(
                    "宪法层只能由照护者修改。请使用 propose_constitution_change()"
                )
            raise ValueError("宪法层创建请使用专用API（需三次审批）")

        # 置信度分级处理（AI提取）
        if source in ("ai_extraction", "external_ai"):
            if confidence >= 0.9:
                status = "saved"
                requires_approval = False
            elif confidence >= 0.7:
                status = "pending_approval"
                requires_approval = True
            else:
                return {
                    "id": None,
                    "status": "rejected_low_confidence",
                    "layer": layer,
                    "confidence": confidence,
                    "reason": "置信度低于0.7，不予存储"
                }
        else:
            # 照护者/患者输入：直接存储
            status = "saved"
            requires_approval = False

        # 创建 Note
        note_id = str(uuid4())

        # 索引到向量数据库
        if not requires_approval:
            # 构建 payload
            payload_data = {
                "id": note_id,
                "content": content,
                "layer": layer,
                "is_active": True,
            }
            if category:
                payload_data["category"] = category
            if agent_id and layer == "session":
                payload_data["agent_id"] = agent_id
            if confidence < 1.0:
                payload_data["confidence"] = confidence

            self.search.index_note(
                note_id=UUID(note_id),
                content=content,
                layer=layer,
                category=category,
                is_active=True,
            )

        return {
            "id": note_id,
            "status": status,
            "layer": layer,
            "confidence": confidence,
            "requires_approval": requires_approval,
        }

    def get_constitution(self) -> List[Dict[str, Any]]:
        """
        获取全部宪法层记忆

        宪法层始终全量加载，不依赖检索。
        包含患者的核心身份信息。

        Returns:
            宪法层记忆列表
        """
        # 使用通用查询获取所有宪法层数据
        results = self.search.search(
            query="核心信息",  # 通用查询词
            layer=MemoryLayer.CONSTITUTION.value,
            limit=20,
        )

        return [
            {
                "id": r["id"],
                "content": r["content"],
                "layer": MemoryLayer.CONSTITUTION.value,
                "category": r.get("category"),
                "score": 1.0,  # 宪法层分数始终为1
                "confidence": 1.0,
                "is_constitution": True,
            }
            for r in results
        ]

    def delete_memory(self, note_id: str) -> bool:
        """
        删除记忆

        Args:
            note_id: Note ID

        Returns:
            是否成功
        """
        return self.search.delete_note(UUID(note_id))

    def update_memory_status(self, note_id: str, is_active: bool) -> bool:
        """
        更新记忆状态（激活/停用）

        Args:
            note_id: Note ID
            is_active: 是否激活

        Returns:
            是否成功
        """
        return self.search.update_note_status(UUID(note_id), is_active)

    def get_stats(self) -> Dict[str, Any]:
        """
        获取记忆统计信息

        Returns:
            统计信息：total_count, vector_size等
        """
        return self.search.get_stats()


# 全局单例（支持依赖注入）
_kernel_instance: Optional[MemoryKernel] = None


def get_memory_kernel(search_service=None, note_repo=None) -> MemoryKernel:
    """
    获取 MemoryKernel 单例

    Args:
        search_service: 搜索服务（可选，延迟注入）
        note_repo: Note 仓库（可选）

    Returns:
        MemoryKernel 实例
    """
    global _kernel_instance
    if _kernel_instance is None:
        if search_service is None:
            # 延迟导入，避免循环引用
            from backend.services.search import get_search_service
            search_service = get_search_service()

        _kernel_instance = MemoryKernel(search_service, note_repo)
    return _kernel_instance


__all__ = [
    "MemoryKernel",
    "MemorySource",
    "get_memory_kernel",
]
