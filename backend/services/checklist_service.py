"""
Checklist Service - 清单管理服务

与 Memory Service 的区别：
- Memory: 被动记忆存储（Note）
- Checklist: 主动清单跟踪（与 Plan skill 协同）

设计原则（来自三方 AI 头脑风暴）：
- Checklist = 战略层（跨会话持久）
- Plan skill = 战术层（单次任务）
- 通过 (ma:xxx) ID 机制连接两者
"""

import logging
import re
from datetime import datetime
from typing import Optional
from uuid import UUID, uuid4

from backend.models.checklist import (
    ChecklistBriefingRequest,
    ChecklistItemCreate,
    ChecklistItemResponse,
    ChecklistItemUpdate,
    ChecklistPriority,
    ChecklistScope,
    ChecklistStatus,
    PlanSyncRequest,
    PlanSyncResponse,
    SyncedItemInfo,
)
from backend.services.embedding import embed_text
from backend.services.search import get_search_service

logger = logging.getLogger(__name__)


class ChecklistService:
    """
    清单管理服务

    职责：
    1. 管理跨会话持久化的清单项
    2. 生成会话开始时的清单简报
    3. 从 Plan skill 同步完成状态
    """

    # Qdrant collection 前缀
    COLLECTION_PREFIX = "memory_anchor_checklist"

    # 搜索项目时的最大返回数量
    MAX_SEARCH_LIMIT = 100

    def __init__(self, search_service=None):
        """
        初始化清单服务

        Args:
            search_service: 搜索服务（复用 Qdrant 连接）
        """
        self._search_service = search_service

    @property
    def search_service(self):
        """延迟获取搜索服务"""
        if self._search_service is None:
            self._search_service = get_search_service()
        return self._search_service

    def _get_collection_name(self, project_id: str) -> str:
        """获取项目对应的 collection 名称"""
        safe_name = re.sub(r"[^a-zA-Z0-9_-]", "_", project_id)
        return f"{self.COLLECTION_PREFIX}_{safe_name}"

    def create_item(
        self, project_id: str, request: ChecklistItemCreate
    ) -> ChecklistItemResponse:
        """
        创建清单项

        Args:
            project_id: 项目 ID
            request: 创建请求

        Returns:
            创建的清单项
        """
        now = datetime.now()
        item = ChecklistItemResponse(
            id=uuid4(),
            content=request.content,
            status=request.status,
            scope=request.scope,
            priority=request.priority,
            tags=request.tags,
            project_id=project_id,
            created_at=now,
            updated_at=now,
            expires_at=self._calculate_expires_at(request.ttl_days) if request.ttl_days else None,
        )

        # 存储到 Qdrant（复用 search_service 的向量化能力）
        self._store_item(project_id, item)
        return item

    def _calculate_expires_at(self, ttl_days: int) -> datetime:
        """计算过期时间"""
        from datetime import timedelta
        return datetime.now() + timedelta(days=ttl_days)

    def _store_item(self, project_id: str, item: ChecklistItemResponse) -> None:
        """存储清单项到 Qdrant"""
        # 构建存储数据
        payload = {
            "id": str(item.id),
            "content": item.content,
            "status": item.status.value,
            "scope": item.scope.value,
            "priority": item.priority.value,
            "tags": item.tags,
            "project_id": item.project_id,
            "created_at": item.created_at.isoformat() if item.created_at else None,
            "updated_at": item.updated_at.isoformat() if item.updated_at else None,
            "completed_at": item.completed_at.isoformat() if item.completed_at else None,
            "expires_at": item.expires_at.isoformat() if item.expires_at else None,
            "type": "checklist",  # 区分 note
        }

        # 使用现有的 search_service 索引
        # 这里我们直接使用底层 Qdrant client
        try:
            from qdrant_client.models import PointStruct

            collection = self._get_collection_name(project_id)
            self._ensure_collection_exists(collection)

            # 生成向量
            embedding = embed_text(item.content)

            # 存储
            self.search_service.client.upsert(
                collection_name=collection,
                points=[
                    PointStruct(
                        id=str(item.id),
                        vector=embedding,
                        payload=payload,
                    )
                ],
            )
        except (ConnectionError, OSError) as e:
            # MVP: 如果 Qdrant 不可用，静默失败但记录日志
            logger.warning("Failed to store checklist item: %s", e)

    def _ensure_collection_exists(self, collection_name: str) -> None:
        """确保 collection 存在"""
        try:
            from qdrant_client.models import Distance, VectorParams

            from backend.config import get_config

            config = get_config()
            collections = self.search_service.client.get_collections().collections
            if not any(c.name == collection_name for c in collections):
                self.search_service.client.create_collection(
                    collection_name=collection_name,
                    vectors_config=VectorParams(
                        size=config.vector_size,
                        distance=Distance.COSINE,
                    ),
                )
        except (ConnectionError, OSError) as e:
            logger.warning("Failed to create collection: %s", e)

    def get_briefing(self, request: ChecklistBriefingRequest) -> str:
        """
        获取清单简报（会话开始时调用）

        Args:
            request: 简报请求

        Returns:
            格式化的 Markdown 简报
        """
        items = self._list_open_items(
            project_id=request.project_id,
            scope=request.scope,
            limit=request.limit,
        )

        if not items:
            return "📋 **清单简报**\n\n当前没有待办清单项。"

        # 按优先级分组
        by_priority: dict[ChecklistPriority, list[ChecklistItemResponse]] = {}
        for item in items:
            if item.priority not in by_priority:
                by_priority[item.priority] = []
            by_priority[item.priority].append(item)

        # 生成 Markdown
        lines = ["📋 **清单简报**", ""]

        priority_labels = {
            ChecklistPriority.CRITICAL: "🔴 紧急",
            ChecklistPriority.HIGH: "🟠 高优",
            ChecklistPriority.NORMAL: "🟡 普通",
            ChecklistPriority.LOW: "🟢 低优",
            ChecklistPriority.BACKLOG: "⚪ 待定",
        }

        for priority in ChecklistPriority:
            if priority in by_priority:
                lines.append(f"### {priority_labels[priority]}")
                for item in by_priority[priority]:
                    ref = item.ma_ref() if request.include_ids else ""
                    status_icon = "[ ]" if item.status == ChecklistStatus.OPEN else "[x]"
                    tags_str = " ".join(f"`{t}`" for t in item.tags) if item.tags else ""
                    lines.append(f"- {status_icon} {item.content} {ref} {tags_str}".strip())
                lines.append("")

        return "\n".join(lines)

    def _list_open_items(
        self,
        project_id: str,
        scope: Optional[ChecklistScope] = None,
        limit: int = 12,
    ) -> list[ChecklistItemResponse]:
        """列出未完成的清单项"""
        try:
            from qdrant_client.models import FieldCondition, Filter, MatchValue

            collection = self._get_collection_name(project_id)

            # 构建过滤条件
            must_conditions = [
                FieldCondition(key="status", match=MatchValue(value="open")),
                FieldCondition(key="type", match=MatchValue(value="checklist")),
            ]

            if scope:
                must_conditions.append(
                    FieldCondition(key="scope", match=MatchValue(value=scope.value))
                )

            # 查询
            results = self.search_service.client.scroll(
                collection_name=collection,
                scroll_filter=Filter(must=must_conditions),  # type: ignore[arg-type]
                limit=limit,
                with_payload=True,
                with_vectors=False,
            )

            items = []
            for point in results[0]:
                payload = point.payload or {}
                items.append(self._payload_to_item(payload))

            # 按优先级排序
            items.sort(key=lambda x: x.priority.value)
            return items

        except (ConnectionError, OSError, ValueError) as e:
            # ValueError: collection doesn't exist (no items created yet)
            logger.debug("Failed to list checklist items: %s", e)
            return []

    def _payload_to_item(self, payload: dict) -> ChecklistItemResponse:
        """将 Qdrant payload 转换为 ChecklistItemResponse"""
        return ChecklistItemResponse(
            id=UUID(payload.get("id", str(uuid4()))),
            content=payload.get("content", ""),
            status=ChecklistStatus(payload.get("status", "open")),
            scope=ChecklistScope(payload.get("scope", "project")),
            priority=ChecklistPriority(int(payload.get("priority", 3))),
            tags=payload.get("tags", []),
            project_id=payload.get("project_id"),
            created_at=datetime.fromisoformat(payload["created_at"]) if payload.get("created_at") else datetime.now(),
            updated_at=datetime.fromisoformat(payload["updated_at"]) if payload.get("updated_at") else datetime.now(),
            completed_at=datetime.fromisoformat(payload["completed_at"]) if payload.get("completed_at") else None,
            expires_at=datetime.fromisoformat(payload["expires_at"]) if payload.get("expires_at") else None,
        )

    def sync_from_plan(self, request: PlanSyncRequest) -> PlanSyncResponse:
        """
        从 Plan 同步清单状态

        解析 plan.md 内容：
        1. 找到 [x] 的项目，如果有 (ma:xxx) 引用则标记对应清单项完成
        2. 找到 @persist 标签的项目，创建新的清单项
        3. 返回同步结果

        Args:
            request: 同步请求

        Returns:
            同步结果
        """
        response = PlanSyncResponse()

        # 解析 plan.md 内容
        lines = request.plan_markdown.split("\n")

        for line in lines:
            line = line.strip()
            if not line:
                continue

            # 匹配 [x] 或 [X] 的已完成项
            if re.match(r"^\s*-?\s*\[x\]\s*", line, re.IGNORECASE):
                # 查找 (ma:xxxxxxxx) 引用
                ma_match = re.search(r"\(ma:([a-f0-9]{8})\)", line, re.IGNORECASE)
                if ma_match:
                    short_id = ma_match.group(1)
                    if self._mark_completed_by_short_id(request.project_id, short_id):
                        response.completed.append(short_id)

            # 匹配 @persist 标签的新项目
            if "@persist" in line.lower():
                # 提取内容（去掉 checkbox 和标签）
                content = re.sub(r"^\s*-?\s*\[[x\s]\]\s*", "", line, flags=re.IGNORECASE)
                content = re.sub(r"@persist", "", content, flags=re.IGNORECASE).strip()

                if content:
                    # 创建新清单项
                    item = self.create_item(
                        project_id=request.project_id,
                        request=ChecklistItemCreate(
                            content=content,
                            scope=ChecklistScope.PROJECT,
                            priority=ChecklistPriority.NORMAL,
                            tags=["from-plan", request.session_id],
                        ),
                    )
                    response.created.append(SyncedItemInfo(
                        id=str(item.id),
                        content=content,
                        ma_ref=item.ma_ref(),
                    ))

        return response

    def _mark_completed_by_short_id(self, project_id: str, short_id: str) -> bool:
        """根据短 ID 标记清单项完成"""
        try:
            from qdrant_client.http.exceptions import UnexpectedResponse
            from qdrant_client.models import FieldCondition, Filter, MatchValue

            collection = self._get_collection_name(project_id)

            # 搜索匹配的项
            results = self.search_service.client.scroll(
                collection_name=collection,
                scroll_filter=Filter(must=[
                    FieldCondition(key="type", match=MatchValue(value="checklist")),
                ]),
                limit=self.MAX_SEARCH_LIMIT,
                with_payload=True,
            )

            # 查找所有匹配的项
            matches = [
                p for p in results[0]
                if (p.payload or {}).get("id", "").startswith(short_id)
            ]

            if not matches:
                return False

            # 碰撞警告：短 ID 可能匹配多个项
            if len(matches) > 1:
                logger.warning(
                    "Short ID %s matches %d items, marking first one",
                    short_id, len(matches)
                )

            # 标记第一个匹配项为完成
            first_match = matches[0]
            item_id = (first_match.payload or {}).get("id", "")
            self._update_item_status(collection, item_id, ChecklistStatus.DONE)
            return True

        except (UnexpectedResponse, ConnectionError, OSError) as e:
            logger.warning("Failed to mark item completed: %s", e)
            return False

    def _update_item_status(
        self, collection: str, item_id: str, status: ChecklistStatus
    ) -> None:
        """更新清单项状态"""
        try:
            now = datetime.now()

            # 使用 Qdrant 的 set_payload 更新
            self.search_service.client.set_payload(
                collection_name=collection,
                payload={
                    "status": status.value,
                    "updated_at": now.isoformat(),
                    "completed_at": now.isoformat() if status == ChecklistStatus.DONE else None,
                },
                points=[item_id],
            )
        except (ConnectionError, OSError) as e:
            logger.warning("Failed to update item status: %s", e)

    def update_item(
        self, project_id: str, item_id: UUID, update: ChecklistItemUpdate
    ) -> Optional[ChecklistItemResponse]:
        """更新清单项"""
        try:
            collection = self._get_collection_name(project_id)

            # 获取现有项
            points = self.search_service.client.retrieve(
                collection_name=collection,
                ids=[str(item_id)],
                with_payload=True,
            )

            if not points:
                return None

            payload = points[0].payload or {}
            now = datetime.now()

            # 更新字段
            if update.content is not None:
                payload["content"] = update.content
            if update.status is not None:
                payload["status"] = update.status.value
                if update.status == ChecklistStatus.DONE:
                    payload["completed_at"] = now.isoformat()
            if update.priority is not None:
                payload["priority"] = update.priority.value
            if update.tags is not None:
                payload["tags"] = update.tags

            payload["updated_at"] = now.isoformat()

            # 重新存储（如果内容变了需要重新向量化）
            if update.content is not None:
                embedding = embed_text(update.content)
                from qdrant_client.models import PointStruct
                self.search_service.client.upsert(
                    collection_name=collection,
                    points=[PointStruct(
                        id=str(item_id),
                        vector=embedding,
                        payload=payload,
                    )],
                )
            else:
                self.search_service.client.set_payload(
                    collection_name=collection,
                    payload=payload,
                    points=[str(item_id)],
                )

            return self._payload_to_item(payload)

        except (ConnectionError, OSError) as e:
            logger.warning("Failed to update checklist item: %s", e)
            return None


# 全局单例
_checklist_service: Optional[ChecklistService] = None


def get_checklist_service() -> ChecklistService:
    """获取清单服务单例"""
    global _checklist_service
    if _checklist_service is None:
        _checklist_service = ChecklistService()
    return _checklist_service


def reset_checklist_service():
    """重置清单服务单例"""
    global _checklist_service
    _checklist_service = None


__all__ = [
    "ChecklistService",
    "get_checklist_service",
    "reset_checklist_service",
]
