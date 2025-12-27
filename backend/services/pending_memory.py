"""
Pending Memory Service - 待审批记忆管理服务

处理置信度在 0.7-0.9 之间的记忆：
1. 存储到 SQLite pending_memories 表
2. 提供列表、批准、拒绝功能
3. 批准后移动到 Qdrant
"""

import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
from uuid import UUID

from backend.config import get_config

def _get_db_path() -> Path:
    """获取数据库路径（可在测试中通过 monkeypatch get_config 覆盖）"""
    return get_config().sqlite_path


def _init_db():
    """初始化 pending_memories 表"""
    db_path = _get_db_path()
    db_path.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS pending_memories (
            id TEXT PRIMARY KEY,
            content TEXT NOT NULL,
            layer TEXT NOT NULL,
            category TEXT,
            confidence REAL NOT NULL,
            source TEXT NOT NULL,
            agent_id TEXT,
            expires_at TEXT,
            priority INTEGER DEFAULT 0,
            created_by TEXT,
            status TEXT DEFAULT 'pending',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            approved_at TEXT,
            approved_by TEXT
        )
    """)

    conn.commit()
    conn.close()


class PendingMemoryService:
    """待审批记忆管理服务"""

    def __init__(self):
        """初始化服务，确保数据库表存在"""
        _init_db()

    def _get_conn(self) -> sqlite3.Connection:
        """获取数据库连接"""
        _init_db()
        conn = sqlite3.connect(str(_get_db_path()))
        conn.row_factory = sqlite3.Row
        return conn

    def add_pending(
        self,
        note_id: UUID,
        content: str,
        layer: str,
        category: Optional[str],
        confidence: float,
        source: str,
        agent_id: Optional[str] = None,
        expires_at: Optional[str] = None,
        priority: int = 0,
        created_by: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        添加待审批记忆到 SQLite

        Args:
            note_id: 记忆 ID
            content: 记忆内容
            layer: 记忆层级
            category: 分类
            confidence: 置信度
            source: 来源
            agent_id: Agent ID（可选）
            expires_at: 过期时间（可选）
            priority: 优先级
            created_by: 创建者

        Returns:
            添加的记录
        """
        now = datetime.now().isoformat()
        conn = self._get_conn()
        cursor = conn.cursor()

        cursor.execute(
            """
            INSERT INTO pending_memories (
                id, content, layer, category, confidence, source,
                agent_id, expires_at, priority, created_by,
                status, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                str(note_id),
                content,
                layer,
                category,
                confidence,
                source,
                agent_id,
                expires_at,
                priority,
                created_by,
                "pending",
                now,
                now,
            ),
        )

        conn.commit()
        conn.close()

        return {
            "id": str(note_id),
            "content": content,
            "layer": layer,
            "category": category,
            "confidence": confidence,
            "status": "pending",
            "created_at": now,
        }

    def list_pending(
        self,
        layer: Optional[str] = None,
        min_confidence: Optional[float] = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """
        列出待审批记忆

        Args:
            layer: 按层级过滤（可选）
            min_confidence: 最低置信度（可选）
            limit: 返回数量限制

        Returns:
            待审批记忆列表
        """
        conn = self._get_conn()
        cursor = conn.cursor()

        query = "SELECT * FROM pending_memories WHERE status = 'pending'"
        params: list[str | float | int] = []

        if layer:
            query += " AND layer = ?"
            params.append(layer)

        if min_confidence is not None:
            query += " AND confidence >= ?"
            params.append(min_confidence)

        query += " ORDER BY confidence DESC, created_at DESC LIMIT ?"
        params.append(limit)

        cursor.execute(query, params)
        rows = cursor.fetchall()
        conn.close()

        return [dict(row) for row in rows]

    def get_pending(self, note_id: str) -> Optional[Dict[str, Any]]:
        """
        获取单个待审批记忆

        Args:
            note_id: 记忆 ID

        Returns:
            待审批记忆，如果不存在则返回 None
        """
        conn = self._get_conn()
        cursor = conn.cursor()

        cursor.execute(
            "SELECT * FROM pending_memories WHERE id = ? AND status = 'pending'",
            (note_id,),
        )
        row = cursor.fetchone()
        conn.close()

        return dict(row) if row else None

    def try_lock_for_processing(self, note_id: str) -> Optional[Dict[str, Any]]:
        """
        尝试锁定记忆用于处理（乐观锁）

        使用原子性的 UPDATE ... WHERE status='pending' 来确保只有一个请求能成功锁定。
        如果锁定成功，状态变为 'processing'，其他并发请求会因为 rowcount=0 而失败。

        Args:
            note_id: 记忆 ID

        Returns:
            锁定的记忆（状态已变为 'processing'），如果已被其他请求锁定则返回 None
        """
        conn = self._get_conn()
        cursor = conn.cursor()

        now = datetime.now().isoformat()

        # 原子性地更新状态为 processing（乐观锁）
        cursor.execute(
            """
            UPDATE pending_memories
            SET status = 'processing', updated_at = ?
            WHERE id = ? AND status = 'pending'
            """,
            (now, note_id),
        )

        if cursor.rowcount == 0:
            conn.close()
            return None  # 已被其他请求处理或不存在

        # 获取锁定后的记录
        cursor.execute("SELECT * FROM pending_memories WHERE id = ?", (note_id,))
        row = cursor.fetchone()
        conn.commit()
        conn.close()

        return dict(row) if row else None

    def unlock_from_processing(self, note_id: str) -> bool:
        """
        释放处理锁，将状态恢复为 'pending'

        用于异常情况下的回滚，让记录可以重新被处理。

        Args:
            note_id: 记忆 ID

        Returns:
            是否释放成功
        """
        conn = self._get_conn()
        cursor = conn.cursor()

        now = datetime.now().isoformat()

        cursor.execute(
            """
            UPDATE pending_memories
            SET status = 'pending', updated_at = ?
            WHERE id = ? AND status = 'processing'
            """,
            (now, note_id),
        )

        unlocked = cursor.rowcount > 0
        conn.commit()
        conn.close()

        return unlocked

    def approve_pending(
        self, note_id: str, approved_by: str = "caregiver"
    ) -> Optional[Dict[str, Any]]:
        """
        批准待审批记忆

        批准后记忆会被标记为 'approved'，但不会自动删除，
        由调用方负责将其索引到 Qdrant 后再删除。

        接受 'pending' 或 'processing' 状态的记录（乐观锁后状态为 'processing'）。

        Args:
            note_id: 记忆 ID
            approved_by: 批准人

        Returns:
            批准的记忆，如果不存在或状态不对则返回 None
        """
        conn = self._get_conn()
        cursor = conn.cursor()

        now = datetime.now().isoformat()

        cursor.execute(
            """
            UPDATE pending_memories
            SET status = 'approved',
                approved_at = ?,
                approved_by = ?,
                updated_at = ?
            WHERE id = ? AND status IN ('pending', 'processing')
            """,
            (now, approved_by, now, note_id),
        )

        if cursor.rowcount == 0:
            conn.close()
            return None

        cursor.execute("SELECT * FROM pending_memories WHERE id = ?", (note_id,))
        row = cursor.fetchone()
        conn.commit()
        conn.close()

        return dict(row) if row else None

    def reject_pending(
        self, note_id: str, rejected_by: str = "caregiver"
    ) -> Optional[Dict[str, Any]]:
        """
        拒绝待审批记忆

        接受 'pending' 或 'processing' 状态的记录（乐观锁后状态为 'processing'）。

        Args:
            note_id: 记忆 ID
            rejected_by: 拒绝人

        Returns:
            拒绝的记忆，如果不存在或状态不对则返回 None
        """
        conn = self._get_conn()
        cursor = conn.cursor()

        now = datetime.now().isoformat()

        cursor.execute(
            """
            UPDATE pending_memories
            SET status = 'rejected',
                approved_by = ?,
                updated_at = ?
            WHERE id = ? AND status IN ('pending', 'processing')
            """,
            (rejected_by, now, note_id),
        )

        if cursor.rowcount == 0:
            conn.close()
            return None

        cursor.execute("SELECT * FROM pending_memories WHERE id = ?", (note_id,))
        row = cursor.fetchone()
        conn.commit()
        conn.close()

        return dict(row) if row else None

    def delete_pending(self, note_id: str) -> bool:
        """
        删除待审批记忆（通常在批准并索引到 Qdrant 后调用）

        Args:
            note_id: 记忆 ID

        Returns:
            是否删除成功
        """
        conn = self._get_conn()
        cursor = conn.cursor()

        cursor.execute(
            "DELETE FROM pending_memories WHERE id = ?",
            (note_id,),
        )

        deleted = cursor.rowcount > 0
        conn.commit()
        conn.close()

        return deleted

    def get_statistics(self) -> Dict[str, Any]:
        """
        获取待审批记忆统计信息

        Returns:
            统计信息
        """
        conn = self._get_conn()
        cursor = conn.cursor()

        # 总数
        cursor.execute("SELECT COUNT(*) FROM pending_memories WHERE status = 'pending'")
        total_pending = cursor.fetchone()[0]

        # 按层级统计
        cursor.execute(
            """
            SELECT layer, COUNT(*) as count
            FROM pending_memories
            WHERE status = 'pending'
            GROUP BY layer
            """
        )
        by_layer = {row[0]: row[1] for row in cursor.fetchall()}

        # 平均置信度
        cursor.execute(
            "SELECT AVG(confidence) FROM pending_memories WHERE status = 'pending'"
        )
        avg_confidence = cursor.fetchone()[0] or 0.0

        conn.close()

        return {
            "total_pending": total_pending,
            "by_layer": by_layer,
            "avg_confidence": round(avg_confidence, 2),
        }
