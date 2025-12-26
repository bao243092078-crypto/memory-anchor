"""
MemoryKernel - Memory Anchor 核心引擎 (v2.0)

纯 Python 同步实现，无 async，无框架依赖。
设计用于多种接入方式：MCP Server (async wrapper) 和 Native SDK (直接调用)。

五层认知记忆模型：
- L0: identity_schema (自我概念) - 核心身份，三次审批
- L1: active_context (工作记忆) - 会话临时状态，不持久化
- L2: event_log (情景记忆) - 带时空标记的事件
- L3: verified_fact (语义记忆) - 验证过的长期事实
- L4: operational_knowledge (技能图式) - 操作性知识

核心原则：
1. 同步接口 - Codex 等脚本直接调用
2. 依赖注入 - 方便测试和替换存储后端
3. 无状态 - 所有状态在存储层（除 L1 active_context）
4. 线程安全 - 使用 Qdrant Server 模式，支持并发
"""

import threading
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import NAMESPACE_URL, UUID, uuid4, uuid5

from backend.config import get_config
from backend.core.active_context import ActiveContext

# 导入现有的 models 和 services
from backend.models.note import MemoryLayer, NoteCategory
from backend.services.pending_memory import PendingMemoryService


class MemorySource(str, Enum):
    """记忆来源"""
    CAREGIVER = "caregiver"
    AI_EXTRACTION = "ai_extraction"
    PATIENT = "patient"
    EXTERNAL_AI = "external_ai"  # Codex/Gemini 等外部 AI


# ===== 向后兼容：层级名称规范化 =====
# v1.x → v2.x 术语映射
_LAYER_ALIASES = {
    # 旧术语 → 新术语（Enum value）
    "constitution": "identity_schema",
    "fact": "verified_fact",
    "session": "event_log",
    # 新术语保持不变
    "identity_schema": "identity_schema",
    "active_context": "active_context",
    "event_log": "event_log",
    "verified_fact": "verified_fact",
    "operational_knowledge": "operational_knowledge",
}


def normalize_layer(layer: Optional[str]) -> Optional[str]:
    """
    规范化层级名称，支持 v1.x 旧术语向 v2.x 新术语转换。

    Args:
        layer: 输入的层级字符串（可能是旧术语或新术语）

    Returns:
        规范化后的层级字符串（v2.x 术语）
    """
    if layer is None:
        return None
    return _LAYER_ALIASES.get(layer.lower(), layer)


class MemoryKernel:
    """
    Memory Anchor 核心引擎 v2.0（同步版本）

    这是所有 AI "患者"（Claude/Codex/Gemini）访问记忆的统一入口。
    类比：人类的海马体（负责记忆形成和检索）。

    五层认知记忆模型：
    - L0: identity_schema - 自我概念（核心身份，三次审批）
    - L1: active_context - 工作记忆（会话临时状态，不持久化）
    - L2: event_log - 情景记忆（带时空标记的事件）
    - L3: verified_fact - 语义记忆（验证过的长期事实）
    - L4: operational_knowledge - 技能图式（操作性知识）

    职责：
    - 搜索记忆（五层语义检索）
    - 添加记忆（置信度分级）
    - 管理宪法层（三次审批机制）
    - 管理活跃上下文（L1 工作记忆）
    - 事件日志记录（L2 情景记忆）

    设计原则：
    - 纯 Python，无 async（方便 Codex 等脚本调用）
    - 依赖注入（search_service, note_repo）
    - 无状态（所有状态在存储层，除 L1）
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
        # 规范化层级名称（支持 v1.x 旧术语）
        layer = normalize_layer(layer)

        results: list[dict] = []

        # 0) 宪法层：不依赖向量检索，始终预加载
        if layer == MemoryLayer.CONSTITUTION.value:
            return self.get_constitution()

        if include_constitution:
            results.extend(self.get_constitution())

        # 1) 搜索事实层/会话层
        search_results: list[dict] = []

        if layer == MemoryLayer.FACT.value:
            search_results = self.search.search(
                query=query,
                limit=limit,
                layer=MemoryLayer.FACT.value,
                category=category,
            )
        elif layer == MemoryLayer.SESSION.value:
            search_results = self.search.search(
                query=query,
                limit=limit,
                layer=MemoryLayer.SESSION.value,
                category=category,
                agent_id=agent_id,
            )
        else:
            # 未指定层级：事实层共享 + 会话层按 agent_id 隔离
            search_results.extend(
                self.search.search(
                    query=query,
                    limit=limit,
                    layer=MemoryLayer.FACT.value,
                    category=category,
                )
            )
            search_results.extend(
                self.search.search(
                    query=query,
                    limit=limit,
                    layer=MemoryLayer.SESSION.value,
                    category=category,
                    agent_id=agent_id,
                )
            )

        for r in search_results:
            # 过滤低分结果
            if r["score"] < min_score:
                continue

            # 跳过宪法层（已预加载）
            if r.get("layer") == MemoryLayer.CONSTITUTION.value:
                continue

            results.append({
                "id": r["id"],
                "content": r["content"],
                "layer": r["layer"],
                "category": r.get("category"),
                "score": r["score"],
                "confidence": r.get("confidence") if r.get("confidence") is not None else 1.0,
                "source": r.get("source"),
                "agent_id": r.get("agent_id"),
                "created_at": r.get("created_at"),
                "expires_at": r.get("expires_at"),
                "is_constitution": False,
                # L2 情景记忆特有字段
                "event_when": r.get("event_when"),
                "event_where": r.get("event_where"),
                "event_who": r.get("event_who"),
            })

        # 2. 按分数排序，但宪法层始终在前
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
        priority: Optional[int] = None,
        created_by: Optional[str] = None,
        expires_at: Optional[datetime] = None,
        requires_approval: bool = False,
        agent_id: Optional[str] = None,
        # L2 情景记忆特有字段
        event_when: Optional[str] = None,
        event_where: Optional[str] = None,
        event_who: Optional[List[str]] = None,
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
            priority: 优先级（可选，0=最高）
            created_by: 创建者标识（可选，默认等于 source）
            expires_at: 过期时间（可选）
            requires_approval: 是否需要审批（仅对非 AI 写入生效）
            agent_id: Agent ID（会话层需要）
            event_when: L2 情景记忆 - 事件时间（ISO 时间字符串）
            event_where: L2 情景记忆 - 事件地点
            event_who: L2 情景记忆 - 涉及人物列表

        Returns:
            {"id": UUID, "status": "saved"/"pending_approval"/"rejected", ...}
        """
        # 规范化层级名称（支持 v1.x 旧术语）
        layer = normalize_layer(layer) or "verified_fact"

        # 🔴 红线：宪法层保护
        if layer == MemoryLayer.IDENTITY_SCHEMA.value:
            if source != "caregiver":
                raise PermissionError(
                    "宪法层只能由照护者修改。请使用 propose_constitution_change()"
                )
            raise ValueError("宪法层创建请使用专用API（需三次审批）")

        # 置信度分级处理（AI提取）
        if source in ("ai_extraction", "external_ai"):
            if confidence >= 0.9:
                status = "saved"
                needs_approval = False
            elif confidence >= 0.7:
                status = "pending_approval"
                needs_approval = True
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
            needs_approval = requires_approval

        # 创建 Note
        note_id = uuid4()
        created_at = datetime.now().isoformat()
        created_by_value = created_by or source

        # 索引到向量数据库或存入待审批队列
        if not needs_approval:
            self.search.index_note(
                note_id=note_id,
                content=content,
                layer=layer,
                category=category,
                is_active=True,
                confidence=confidence,
                source=source,
                agent_id=agent_id if layer == MemoryLayer.EVENT_LOG.value else None,
                created_at=created_at,
                expires_at=expires_at.isoformat() if expires_at else None,
                priority=priority,
                created_by=created_by_value,
                # L2 情景记忆特有字段
                event_when=event_when,
                event_where=event_where,
                event_who=event_who,
            )
        else:
            # 存入待审批队列（SQLite）
            pending_service = PendingMemoryService()
            pending_service.add_pending(
                note_id=note_id,
                content=content,
                layer=layer,
                category=category,
                confidence=confidence,
                source=source,
                agent_id=agent_id if layer == MemoryLayer.EVENT_LOG.value else None,
                expires_at=expires_at.isoformat() if expires_at else None,
                priority=priority if priority is not None else 0,
                created_by=created_by_value,
            )

        return {
            "id": note_id,
            "status": status,
            "layer": layer,
            "confidence": confidence,
            "requires_approval": needs_approval,
            "created_at": created_at,
            "priority": priority,
            "created_by": created_by_value,
        }

    def get_constitution(self) -> List[Dict[str, Any]]:
        """
        获取全部宪法层记忆

        宪法层始终全量加载，不依赖检索。
        包含患者的核心身份信息。

        Returns:
            宪法层记忆列表
        """
        config = get_config()

        results: list[dict] = []
        seen_contents: set[str] = set()

        # 1) YAML（优先）：来自 ~/.memory-anchor/projects/{project}/constitution.yaml
        for item in config.constitution:
            category = None
            if item.category:
                try:
                    category = NoteCategory(item.category).value
                except ValueError:
                    category = None

            stable_id = uuid5(
                NAMESPACE_URL,
                f"memory-anchor:{config.project_name}:constitution:{item.id}",
            )

            results.append(
                {
                    "id": stable_id,
                    "content": item.content,
                    "layer": MemoryLayer.CONSTITUTION.value,
                    "category": category,
                    "score": 1.0,
                    "confidence": 1.0,
                    "source": f"yaml:{item.id}",
                    "is_constitution": True,
                }
            )
            seen_contents.add(item.content)

        # 2) Qdrant（向后兼容）：动态宪法条目（如三次审批写入）
        qdrant_results = self.search.list_notes(
            layer=MemoryLayer.CONSTITUTION.value,
            only_active=True,
            limit=config.max_constitution_items,
        )

        for r in qdrant_results:
            content = r.get("content", "")
            if not content or content in seen_contents:
                continue
            seen_contents.add(content)

            results.append(
                {
                    "id": UUID(str(r["id"])),
                    "content": content,
                    "layer": MemoryLayer.CONSTITUTION.value,
                    "category": r.get("category"),
                    "score": 1.0,
                    "confidence": r.get("confidence") if r.get("confidence") is not None else 1.0,
                    "source": r.get("source") or "qdrant",
                    "agent_id": r.get("agent_id"),
                    "created_at": r.get("created_at"),
                    "expires_at": r.get("expires_at"),
                    "is_constitution": True,
                }
            )

        return results

    def delete_memory(self, note_id: str | UUID) -> bool:
        """
        删除记忆

        Args:
            note_id: Note ID

        Returns:
            是否成功
        """
        note_uuid = note_id if isinstance(note_id, UUID) else UUID(str(note_id))
        result = self.search.delete_note(note_uuid)
        return bool(result)

    def update_memory_status(self, note_id: str | UUID, is_active: bool) -> bool:
        """
        更新记忆状态（激活/停用）

        Args:
            note_id: Note ID
            is_active: 是否激活

        Returns:
            是否成功
        """
        note_uuid = note_id if isinstance(note_id, UUID) else UUID(str(note_id))
        result = self.search.update_note_status(note_uuid, is_active)
        return bool(result)

    def get_stats(self) -> Dict[str, Any]:
        """
        获取记忆统计信息

        Returns:
            统计信息：total_count, vector_size等
        """
        result = self.search.get_stats()
        return dict(result)

    # ===== L1: Active Context (工作记忆) =====

    def set_active_context(
        self, key: str, value: Any, ttl: Optional[int] = None
    ) -> None:
        """
        设置活跃上下文（L1 工作记忆）

        Args:
            key: 键名
            value: 值（任意类型）
            ttl: 存活时间（秒），默认 1 小时
        """
        ActiveContext.set(key, value, ttl)

    def get_active_context(self, key: str, default: Any = None) -> Any:
        """
        获取活跃上下文（L1 工作记忆）

        Args:
            key: 键名
            default: 默认值

        Returns:
            存储的值或默认值
        """
        return ActiveContext.get(key, default)

    def clear_active_context(self) -> None:
        """清除当前会话的所有活跃上下文"""
        ActiveContext.clear_session()

    def list_active_context(self) -> Dict[str, Any]:
        """列出当前会话的所有活跃上下文"""
        return ActiveContext.get_all()

    # ===== L2: Event Log (情景记忆) =====

    def log_event(
        self,
        content: str,
        when: Optional[datetime] = None,
        where: Optional[str] = None,
        who: Optional[List[str]] = None,
        category: Optional[str] = None,
        source: str = "ai",
        ttl_days: Optional[int] = None,
        confidence: float = 0.8,
        agent_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        记录事件到情景记忆（L2 event_log）

        情景记忆的核心特征（来自认知科学）：
        - when: 事件发生的时间
        - where: 事件发生的地点
        - who: 涉及的人物

        Args:
            content: 事件内容描述
            when: 事件时间（默认当前）
            where: 事件地点
            who: 涉及的人物列表
            category: 分类
            source: 来源 (ai/user/caregiver)
            ttl_days: 存活天数（None=永久）
            confidence: 置信度
            agent_id: Agent ID

        Returns:
            {"id": UUID, "status": "saved", ...}
        """
        event_time = when or datetime.now()
        participants = who or []

        # 构建丰富的内容（包含时空元数据）
        enriched_content = content
        metadata_parts = []
        if where:
            metadata_parts.append(f"地点:{where}")
        if participants:
            metadata_parts.append(f"人物:{','.join(participants)}")
        if metadata_parts:
            enriched_content = f"{content} [{'; '.join(metadata_parts)}]"

        # 计算过期时间
        expires_at = None
        if ttl_days:
            from datetime import timedelta
            expires_at = event_time + timedelta(days=ttl_days)

        # 调用 add_memory 写入 event_log 层，传递 L2 情景记忆特有字段
        result = self.add_memory(
            content=enriched_content,
            layer=MemoryLayer.EVENT_LOG.value,
            category=category,
            source=source,
            confidence=confidence,
            expires_at=expires_at,
            agent_id=agent_id,
            # L2 情景记忆特有字段 - 存储到 Qdrant payload
            event_when=event_time.isoformat(),
            event_where=where,
            event_who=participants,
        )

        # 添加事件特有字段到返回结果（便于调用者使用）
        result["when"] = event_time.isoformat()
        result["where"] = where
        result["who"] = participants
        result["ttl_days"] = ttl_days

        return result

    def search_events(
        self,
        query: str,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        where: Optional[str] = None,
        who: Optional[str] = None,
        limit: int = 10,
        agent_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        搜索事件日志（L2 event_log）

        支持基于时间、地点、人物的过滤。

        Args:
            query: 搜索查询
            start_time: 开始时间
            end_time: 结束时间
            where: 地点过滤
            who: 人物过滤
            limit: 返回数量
            agent_id: Agent ID

        Returns:
            事件列表
        """
        # 增强查询（包含时空过滤词）
        enhanced_query = query
        if where:
            enhanced_query += f" 地点:{where}"
        if who:
            enhanced_query += f" 人物:{who}"

        # 搜索 event_log 层
        results = self.search_memory(
            query=enhanced_query,
            layer=MemoryLayer.EVENT_LOG.value,
            limit=limit,
            include_constitution=False,
            agent_id=agent_id,
        )

        # TODO: 添加时间范围过滤（需要 Qdrant payload 过滤支持）

        return results

    def promote_event_to_fact(
        self,
        event_id: str | UUID,
        verified_by: str = "caregiver",
        notes: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        将事件提升为验证事实（L2 → L3）

        当一个事件经过验证，可以提升为长期事实层。

        Args:
            event_id: 事件 ID
            verified_by: 验证者
            notes: 提升备注

        Returns:
            {"status": "promoted", "new_id": UUID, ...}
        """
        event_uuid = event_id if isinstance(event_id, UUID) else UUID(str(event_id))

        # 获取原事件
        event_data = self.search.get_note(event_uuid)
        if not event_data:
            return {"status": "error", "reason": "事件不存在"}

        # 检查是否已提升
        if event_data.get("layer") == MemoryLayer.VERIFIED_FACT.value:
            return {"status": "already_fact", "id": event_uuid}

        # 创建新的 verified_fact 记录
        content = event_data.get("content", "")
        if notes:
            content += f" [验证备注: {notes}]"

        new_result = self.add_memory(
            content=content,
            layer=MemoryLayer.VERIFIED_FACT.value,
            category=event_data.get("category"),
            source="promoted_from_event",
            confidence=1.0,  # 提升后置信度为 1
            created_by=verified_by,
        )

        # 标记原事件为已提升（更新 payload）
        self.search.update_note(
            event_uuid,
            {
                "promoted_to_fact": True,
                "promoted_at": datetime.now().isoformat(),
                "promoted_fact_id": str(new_result["id"]),
            },
        )

        return {
            "status": "promoted",
            "original_event_id": str(event_uuid),
            "new_fact_id": str(new_result["id"]),
            "verified_by": verified_by,
            "promoted_at": datetime.now().isoformat(),
        }


# 全局单例（支持依赖注入）+ 线程安全锁
_kernel_instance: Optional[MemoryKernel] = None
_kernel_lock = threading.Lock()


def get_memory_kernel(search_service=None, note_repo=None) -> MemoryKernel:
    """
    获取 MemoryKernel 单例（线程安全）

    使用 double-checked locking 模式：
    1. 第一次检查（无锁）- 快速路径，避免已初始化时的锁开销
    2. 获取锁
    3. 第二次检查（有锁）- 防止并发初始化

    Args:
        search_service: 搜索服务（可选，延迟注入）
        note_repo: Note 仓库（可选）

    Returns:
        MemoryKernel 实例
    """
    global _kernel_instance

    # 第一次检查（无锁）- 快速路径
    if _kernel_instance is not None:
        return _kernel_instance

    # 获取锁并再次检查
    with _kernel_lock:
        # 第二次检查（有锁）- 防止并发初始化
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
