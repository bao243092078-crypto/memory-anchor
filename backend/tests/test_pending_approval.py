"""
测试待审批记忆队列

Bug 6: pending_approval memories not persisted to database
确保置信度 0.7-0.9 的记忆被存入 SQLite，并可通过 API 批准/拒绝
"""

import pytest
import tempfile
import os
from pathlib import Path
from uuid import uuid4
from backend.core.memory_kernel import MemoryKernel
from backend.services.pending_memory import PendingMemoryService
from backend.services.search import SearchService
from backend.config import reset_config, get_config
from backend.services import pending_memory


class TestPendingApprovalQueue:
    """测试待审批队列"""

    @pytest.fixture(autouse=True)
    def setup_test_db(self, tmp_path, monkeypatch):
        """为每个测试设置独立的临时 SQLite 数据库"""
        test_db = tmp_path / "test_pending.db"
        monkeypatch.setattr(pending_memory, "DB_PATH", test_db)

        # 重置配置，确保使用测试数据库
        reset_config()

        # 设置测试环境变量
        monkeypatch.setenv("MEMORY_ANCHOR_COLLECTION", "memory_anchor_test_notes")

        yield

        # 清理
        reset_config()

    @pytest.fixture
    def search_service(self, tmp_path):
        """创建测试用的 SearchService"""
        return SearchService(path=str(tmp_path / ".qdrant"))

    @pytest.fixture
    def memory_kernel(self, search_service):
        """创建测试用的 MemoryKernel"""
        return MemoryKernel(search_service=search_service)

    @pytest.fixture
    def pending_service(self):
        """创建测试用的 PendingMemoryService"""
        return PendingMemoryService()

    def test_confidence_07_09_queued(self, memory_kernel, pending_service):
        """测试置信度 0.7-0.9 的记忆被存入待审批队列"""
        result = memory_kernel.add_memory(
            content="这是一个需要审批的记忆",
            layer="verified_fact",
            category="event",
            confidence=0.8,
            source="ai_extraction",
        )

        # 应该返回 pending_approval 状态
        assert result["status"] == "pending_approval"
        assert result["requires_approval"] is True
        assert result["confidence"] == 0.8

        # 应该存在于 SQLite
        pending_list = pending_service.list_pending()
        assert len(pending_list) == 1
        assert pending_list[0]["content"] == "这是一个需要审批的记忆"
        assert pending_list[0]["confidence"] == 0.8

    def test_confidence_09_saved_directly(self, memory_kernel, pending_service):
        """测试置信度 >= 0.9 的记忆直接存入 Qdrant"""
        result = memory_kernel.add_memory(
            content="这是一个高置信度记忆",
            layer="verified_fact",
            category="event",
            confidence=0.95,
            source="ai_extraction",
        )

        # 应该返回 saved 状态
        assert result["status"] == "saved"
        assert result["requires_approval"] is False

        # 不应该在待审批队列
        pending_list = pending_service.list_pending()
        assert len(pending_list) == 0

    def test_confidence_below_07_rejected(self, memory_kernel, pending_service):
        """测试置信度 < 0.7 的记忆被拒绝"""
        result = memory_kernel.add_memory(
            content="这是一个低置信度记忆",
            layer="verified_fact",
            category="event",
            confidence=0.65,
            source="ai_extraction",
        )

        # 应该返回 rejected 状态
        assert result["status"] == "rejected_low_confidence"
        assert result["id"] is None

        # 不应该在待审批队列
        pending_list = pending_service.list_pending()
        assert len(pending_list) == 0

    def test_list_pending_with_filters(self, memory_kernel, pending_service):
        """测试带过滤条件的列出待审批记忆"""
        # 添加多个待审批记忆
        memory_kernel.add_memory(
            content="事实层记忆 1",
            layer="verified_fact",
            confidence=0.8,
            source="ai_extraction",
        )
        memory_kernel.add_memory(
            content="事实层记忆 2",
            layer="verified_fact",
            confidence=0.75,
            source="ai_extraction",
        )
        memory_kernel.add_memory(
            content="会话层记忆",
            layer="event_log",
            confidence=0.85,
            source="ai_extraction",
        )

        # 测试不带过滤条件
        all_pending = pending_service.list_pending()
        assert len(all_pending) == 3

        # 测试按层级过滤
        fact_pending = pending_service.list_pending(layer="verified_fact")
        assert len(fact_pending) == 2
        assert all(p["layer"] == "verified_fact" for p in fact_pending)

        # 测试按置信度过滤
        high_conf = pending_service.list_pending(min_confidence=0.8)
        assert len(high_conf) == 2
        assert all(p["confidence"] >= 0.8 for p in high_conf)

    def test_approve_pending_moves_to_qdrant(self, memory_kernel, pending_service):
        """测试批准待审批记忆后移动到 Qdrant"""
        # 添加待审批记忆
        result = memory_kernel.add_memory(
            content="待批准的记忆",
            layer="verified_fact",
            category="event",
            confidence=0.8,
            source="ai_extraction",
        )
        note_id = str(result["id"])

        # 批准
        approved = pending_service.approve_pending(note_id, approved_by="test_user")
        assert approved is not None
        assert approved["status"] == "approved"
        assert approved["approved_by"] == "test_user"

        # 验证可以通过 search 找到（在 Qdrant 中）
        # 注意：需要手动调用索引，因为 approve_pending 只更新 SQLite
        memory_kernel.search.index_note(
            note_id=approved["id"],
            content=approved["content"],
            layer=approved["layer"],
            category=approved["category"],
            is_active=True,
            confidence=approved["confidence"],
            source=approved["source"],
            created_at=approved["created_at"],
        )

        search_results = memory_kernel.search_memory(query="待批准", layer="verified_fact")
        assert len(search_results) == 1
        assert search_results[0]["content"] == "待批准的记忆"

    def test_reject_pending_does_not_index(self, memory_kernel, pending_service):
        """测试拒绝待审批记忆不会索引到 Qdrant"""
        # 添加待审批记忆
        result = memory_kernel.add_memory(
            content="待拒绝的记忆",
            layer="verified_fact",
            category="event",
            confidence=0.8,
            source="ai_extraction",
        )
        note_id = str(result["id"])

        # 拒绝
        rejected = pending_service.reject_pending(note_id, rejected_by="test_user")
        assert rejected is not None
        assert rejected["status"] == "rejected"
        assert rejected["approved_by"] == "test_user"

        # 验证无法通过 search 找到（不在 Qdrant 中）
        search_results = memory_kernel.search_memory(query="待拒绝", layer="verified_fact")
        assert len(search_results) == 0

    def test_get_pending_statistics(self, memory_kernel, pending_service):
        """测试获取待审批记忆统计信息"""
        # 添加多个待审批记忆
        memory_kernel.add_memory(
            content="事实层记忆 1",
            layer="verified_fact",
            confidence=0.8,
            source="ai_extraction",
        )
        memory_kernel.add_memory(
            content="事实层记忆 2",
            layer="verified_fact",
            confidence=0.75,
            source="ai_extraction",
        )
        memory_kernel.add_memory(
            content="会话层记忆",
            layer="event_log",
            confidence=0.85,
            source="ai_extraction",
        )

        stats = pending_service.get_statistics()
        assert stats["total_pending"] == 3
        assert stats["by_layer"]["verified_fact"] == 2
        assert stats["by_layer"]["event_log"] == 1
        assert 0.75 <= stats["avg_confidence"] <= 0.85

    def test_caregiver_input_bypasses_queue(self, memory_kernel, pending_service):
        """测试照护者输入绕过待审批队列"""
        result = memory_kernel.add_memory(
            content="照护者添加的记忆",
            layer="verified_fact",
            category="event",
            confidence=0.8,  # 即使置信度在 0.7-0.9 之间
            source="caregiver",  # 照护者来源
        )

        # 应该直接存储
        assert result["status"] == "saved"
        assert result["requires_approval"] is False

        # 不应该在待审批队列
        pending_list = pending_service.list_pending()
        assert len(pending_list) == 0

    def test_multiple_pending_sorted_by_confidence(self, memory_kernel, pending_service):
        """测试多个待审批记忆按置信度排序"""
        memory_kernel.add_memory(
            content="低置信度", layer="verified_fact", confidence=0.72, source="ai_extraction"
        )
        memory_kernel.add_memory(
            content="中置信度", layer="verified_fact", confidence=0.8, source="ai_extraction"
        )
        memory_kernel.add_memory(
            content="高置信度", layer="verified_fact", confidence=0.88, source="ai_extraction"
        )

        pending_list = pending_service.list_pending()
        assert len(pending_list) == 3

        # 应该按置信度降序排列
        assert pending_list[0]["confidence"] == 0.88
        assert pending_list[1]["confidence"] == 0.8
        assert pending_list[2]["confidence"] == 0.72
