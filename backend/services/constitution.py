"""
Constitution Service - 宪法层变更管理服务

实现三次审批机制：
1. propose: 提议变更，进入 pending 队列
2. approve: 审批变更，approvals_count +1
3. apply: 当 approvals_count >= 3 时，自动应用到宪法层
"""

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Optional
from uuid import UUID, uuid4

from backend.models.constitution_change import (
    ChangeStatus,
    ChangeType,
    ConstitutionApproveRequest,
    ConstitutionChangeResponse,
    ConstitutionProposeRequest,
)
from backend.models.note import MemoryLayer, NoteCategory
from backend.config import get_config


# 数据库路径
DB_PATH = get_config().sqlite_path


def _get_db_path() -> Path:
    """获取宪法层审批数据库路径（可在测试中通过 monkeypatch DB_PATH 覆盖）"""
    return DB_PATH


def _init_db():
    """初始化数据库表"""
    db_path = _get_db_path()
    db_path.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS constitution_changes (
            id TEXT PRIMARY KEY,
            change_type TEXT NOT NULL,
            proposed_content TEXT NOT NULL,
            reason TEXT NOT NULL,
            target_id TEXT,
            category TEXT,
            status TEXT DEFAULT 'pending',
            approvals_count INTEGER DEFAULT 0,
            approvals_needed INTEGER DEFAULT 3,
            approvals TEXT DEFAULT '[]',
            proposer TEXT DEFAULT 'unknown',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            applied_at TEXT
        )
    """)

    conn.commit()
    conn.close()


class ConstitutionService:
    """宪法层变更管理服务"""

    APPROVALS_NEEDED = 3  # 需要的审批次数

    def __init__(self):
        """初始化服务，确保数据库表存在"""
        _init_db()

    def _get_conn(self) -> sqlite3.Connection:
        """获取数据库连接"""
        conn = sqlite3.connect(str(_get_db_path()))
        conn.row_factory = sqlite3.Row
        return conn

    async def propose(
        self,
        request: ConstitutionProposeRequest,
        proposer: str = "cli_user"
    ) -> ConstitutionChangeResponse:
        """
        提议宪法变更

        Args:
            request: 变更请求
            proposer: 提议人

        Returns:
            变更记录
        """
        now = datetime.now().isoformat()
        change_id = str(uuid4())

        conn = self._get_conn()
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO constitution_changes
            (id, change_type, proposed_content, reason, target_id, category,
             status, approvals_count, approvals_needed, approvals, proposer,
             created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            change_id,
            request.change_type.value,
            request.proposed_content,
            request.reason,
            str(request.target_id) if request.target_id else None,
            request.category,
            ChangeStatus.PENDING.value,
            0,
            self.APPROVALS_NEEDED,
            "[]",
            proposer,
            now,
            now,
        ))

        conn.commit()
        conn.close()

        return ConstitutionChangeResponse(
            id=UUID(change_id),
            change_type=request.change_type,
            proposed_content=request.proposed_content,
            reason=request.reason,
            target_id=request.target_id,
            category=request.category,
            status=ChangeStatus.PENDING,
            approvals_count=0,
            approvals_needed=self.APPROVALS_NEEDED,
            approvals=[],
            proposer=proposer,
            created_at=datetime.fromisoformat(now),
            updated_at=datetime.fromisoformat(now),
        )

    async def approve(
        self,
        change_id: UUID,
        request: ConstitutionApproveRequest
    ) -> ConstitutionChangeResponse:
        """
        审批宪法变更

        每次调用 approvals_count +1
        当达到 APPROVALS_NEEDED 时，自动应用变更

        Args:
            change_id: 变更ID
            request: 审批请求

        Returns:
            更新后的变更记录
        """
        conn = self._get_conn()
        cursor = conn.cursor()

        # 获取当前记录
        cursor.execute(
            "SELECT * FROM constitution_changes WHERE id = ?",
            (str(change_id),)
        )
        row = cursor.fetchone()

        if not row:
            conn.close()
            raise ValueError(f"变更记录不存在: {change_id}")

        if row["status"] != ChangeStatus.PENDING.value:
            conn.close()
            raise ValueError(f"变更状态不是 pending: {row['status']}")

        # 更新审批信息
        now = datetime.now().isoformat()
        approvals = json.loads(row["approvals"])
        approvals.append({
            "approver": request.approver,
            "comment": request.comment,
            "approved_at": now,
        })
        new_count = row["approvals_count"] + 1

        # 判断是否达到审批次数
        if new_count >= self.APPROVALS_NEEDED:
            new_status = ChangeStatus.APPROVED.value
            # 自动应用变更
            await self._apply_change(row)
            new_status = ChangeStatus.APPLIED.value
            applied_at = now
        else:
            new_status = ChangeStatus.PENDING.value
            applied_at = None

        # 更新数据库
        cursor.execute("""
            UPDATE constitution_changes
            SET approvals_count = ?, approvals = ?, status = ?,
                updated_at = ?, applied_at = ?
            WHERE id = ?
        """, (
            new_count,
            json.dumps(approvals),
            new_status,
            now,
            applied_at,
            str(change_id),
        ))

        conn.commit()
        conn.close()

        return ConstitutionChangeResponse(
            id=change_id,
            change_type=ChangeType(row["change_type"]),
            proposed_content=row["proposed_content"],
            reason=row["reason"],
            target_id=UUID(row["target_id"]) if row["target_id"] else None,
            category=row["category"],
            status=ChangeStatus(new_status),
            approvals_count=new_count,
            approvals_needed=self.APPROVALS_NEEDED,
            approvals=approvals,
            proposer=row["proposer"],
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(now),
            applied_at=datetime.fromisoformat(applied_at) if applied_at else None,
        )

    async def _apply_change(self, row: sqlite3.Row):
        """
        应用宪法变更到实际存储

        根据 change_type 执行相应操作：
        - create: 添加新条目到宪法层
        - update: 更新现有条目
        - delete: 删除条目
        """
        from backend.services.search import get_search_service

        search_service = get_search_service()
        change_type = ChangeType(row["change_type"])
        content = row["proposed_content"]
        category = row["category"]
        target_id = row["target_id"]

        if change_type == ChangeType.CREATE:
            # 创建新的宪法层条目
            note_id = uuid4()
            search_service.index_note(
                note_id=note_id,
                content=content,
                layer=MemoryLayer.CONSTITUTION.value,
                category=category,
                is_active=True,
            )
        elif change_type == ChangeType.UPDATE:
            # 更新现有条目（删除旧的，添加新的）
            if target_id:
                search_service.delete_note(UUID(target_id))
                search_service.index_note(
                    note_id=UUID(target_id),
                    content=content,
                    layer=MemoryLayer.CONSTITUTION.value,
                    category=category,
                    is_active=True,
                )
        elif change_type == ChangeType.DELETE:
            # 删除条目
            if target_id:
                search_service.delete_note(UUID(target_id))

    async def get_pending(self) -> list[ConstitutionChangeResponse]:
        """获取所有待审批的变更"""
        conn = self._get_conn()
        cursor = conn.cursor()

        cursor.execute(
            "SELECT * FROM constitution_changes WHERE status = ? ORDER BY created_at DESC",
            (ChangeStatus.PENDING.value,)
        )
        rows = cursor.fetchall()
        conn.close()

        return [self._row_to_response(row) for row in rows]

    async def get_change(self, change_id: UUID) -> Optional[ConstitutionChangeResponse]:
        """获取单个变更记录"""
        conn = self._get_conn()
        cursor = conn.cursor()

        cursor.execute(
            "SELECT * FROM constitution_changes WHERE id = ?",
            (str(change_id),)
        )
        row = cursor.fetchone()
        conn.close()

        if not row:
            return None

        return self._row_to_response(row)

    async def list_changes(
        self,
        status: Optional[ChangeStatus] = None,
        limit: int = 20
    ) -> list[ConstitutionChangeResponse]:
        """列出变更记录"""
        conn = self._get_conn()
        cursor = conn.cursor()

        if status:
            cursor.execute(
                "SELECT * FROM constitution_changes WHERE status = ? ORDER BY created_at DESC LIMIT ?",
                (status.value, limit)
            )
        else:
            cursor.execute(
                "SELECT * FROM constitution_changes ORDER BY created_at DESC LIMIT ?",
                (limit,)
            )

        rows = cursor.fetchall()
        conn.close()

        return [self._row_to_response(row) for row in rows]

    def _row_to_response(self, row: sqlite3.Row) -> ConstitutionChangeResponse:
        """将数据库行转换为响应对象"""
        return ConstitutionChangeResponse(
            id=UUID(row["id"]),
            change_type=ChangeType(row["change_type"]),
            proposed_content=row["proposed_content"],
            reason=row["reason"],
            target_id=UUID(row["target_id"]) if row["target_id"] else None,
            category=row["category"],
            status=ChangeStatus(row["status"]),
            approvals_count=row["approvals_count"],
            approvals_needed=row["approvals_needed"],
            approvals=json.loads(row["approvals"]),
            proposer=row["proposer"],
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
            applied_at=datetime.fromisoformat(row["applied_at"]) if row["applied_at"] else None,
        )


# 全局单例
_constitution_service: Optional[ConstitutionService] = None


def get_constitution_service() -> ConstitutionService:
    """获取宪法服务单例"""
    global _constitution_service
    if _constitution_service is None:
        _constitution_service = ConstitutionService()
    return _constitution_service


__all__ = [
    "ConstitutionService",
    "get_constitution_service",
]
