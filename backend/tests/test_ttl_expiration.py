"""
测试 TTL 过期过滤

Bug 3: TTL expiration field filtering not implemented
确保已过期的记忆（expires_at < now）被正确过滤掉
"""

import pytest
from datetime import datetime, timedelta, timezone
from uuid import uuid4
from backend.services.search import SearchService
from backend.models.note import MemoryLayer


class TestTTLExpiration:
    """测试 TTL 过期过滤"""

    @pytest.fixture
    def search_service(self, tmp_path):
        """创建测试用的 SearchService"""
        return SearchService(path=str(tmp_path / ".qdrant"))

    def test_expired_memories_filtered_from_search(self, search_service):
        """测试 search() 过滤掉已过期的记忆"""
        now = datetime.now(timezone.utc)
        past = (now - timedelta(hours=1)).isoformat()  # 1小时前过期
        future = (now + timedelta(hours=1)).isoformat()  # 1小时后过期

        # 添加三条记忆
        search_service.index_note(
            note_id=uuid4(),
            content="已过期的记忆",
            layer="event_log",
            expires_at=past,
        )
        search_service.index_note(
            note_id=uuid4(),
            content="未过期的记忆",
            layer="event_log",
            expires_at=future,
        )
        search_service.index_note(
            note_id=uuid4(),
            content="永不过期的记忆",
            layer="event_log",
            expires_at=None,
        )

        # 搜索
        results = search_service.search(
            query="记忆",
            layer=MemoryLayer.EVENT_LOG,
            limit=10,
        )

        # 应该只返回未过期和永不过期的记忆
        assert len(results) == 2
        contents = [r["content"] for r in results]
        assert "未过期的记忆" in contents
        assert "永不过期的记忆" in contents
        assert "已过期的记忆" not in contents

    def test_expired_memories_filtered_from_list(self, search_service):
        """测试 list_notes() 过滤掉已过期的记忆"""
        now = datetime.now(timezone.utc)
        past = (now - timedelta(hours=1)).isoformat()
        future = (now + timedelta(hours=1)).isoformat()

        search_service.index_note(
            note_id=uuid4(),
            content="过期列表记忆",
            layer="verified_fact",
            expires_at=past,
        )
        search_service.index_note(
            note_id=uuid4(),
            content="有效列表记忆",
            layer="verified_fact",
            expires_at=future,
        )
        search_service.index_note(
            note_id=uuid4(),
            content="永久列表记忆",
            layer="verified_fact",
            expires_at=None,
        )

        # 列出
        results = search_service.list_notes(
            layer="verified_fact",
            limit=10,
        )

        # 应该只返回未过期和永不过期的记忆
        assert len(results) == 2
        contents = [r["content"] for r in results]
        assert "有效列表记忆" in contents
        assert "永久列表记忆" in contents
        assert "过期列表记忆" not in contents

    def test_none_expires_at_never_filtered(self, search_service):
        """测试 expires_at=None 的记忆永不过期"""
        search_service.index_note(
            note_id=uuid4(),
            content="永久记忆1",
            layer="verified_fact",
            expires_at=None,
        )
        search_service.index_note(
            note_id=uuid4(),
            content="永久记忆2",
            layer="verified_fact",
            expires_at=None,
        )

        results = search_service.search(
            query="永久",
            layer=MemoryLayer.VERIFIED_FACT,
            limit=10,
        )

        assert len(results) == 2

    def test_edge_case_expires_at_exactly_now(self, search_service):
        """测试 expires_at 正好等于当前时间的边界情况"""
        now = datetime.now(timezone.utc)
        # 加 1 秒避免时间竞争（indexing 和 searching 之间的微小时差）
        now_plus_1s = (now + timedelta(seconds=1)).isoformat()

        search_service.index_note(
            note_id=uuid4(),
            content="边界记忆",
            layer="event_log",
            expires_at=now_plus_1s,
        )

        results = search_service.search(
            query="边界",
            layer=MemoryLayer.EVENT_LOG,
            limit=10,
        )

        # expires_at >= now 应该包含 expires_at == now 的情况
        assert len(results) == 1
        assert results[0]["content"] == "边界记忆"

    def test_multiple_layers_with_expiration(self, search_service):
        """测试不同层级的过期过滤"""
        now = datetime.now(timezone.utc)
        past = (now - timedelta(hours=1)).isoformat()
        future = (now + timedelta(hours=1)).isoformat()

        # 添加不同层级的记忆
        search_service.index_note(
            note_id=uuid4(),
            content="过期 fact",
            layer="verified_fact",
            expires_at=past,
        )
        search_service.index_note(
            note_id=uuid4(),
            content="有效 fact",
            layer="verified_fact",
            expires_at=future,
        )
        search_service.index_note(
            note_id=uuid4(),
            content="过期 event",
            layer="event_log",
            expires_at=past,
        )
        search_service.index_note(
            note_id=uuid4(),
            content="有效 event",
            layer="event_log",
            expires_at=future,
        )

        # 搜索 fact 层
        fact_results = search_service.search(
            query="fact",
            layer=MemoryLayer.VERIFIED_FACT,
            limit=10,
        )
        assert len(fact_results) == 1
        assert fact_results[0]["content"] == "有效 fact"

        # 搜索 event 层
        event_results = search_service.search(
            query="event",
            layer=MemoryLayer.EVENT_LOG,
            limit=10,
        )
        assert len(event_results) == 1
        assert event_results[0]["content"] == "有效 event"
