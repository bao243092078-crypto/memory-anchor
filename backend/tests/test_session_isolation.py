"""
测试会话隔离

Bug 1: Session isolation failure (agent_id filter never triggers)
确保 agent_id 过滤在 event_log 层正确生效
"""

import pytest
from uuid import uuid4
from backend.services.search import SearchService
from backend.models.note import MemoryLayer, NoteCategory


class TestSessionIsolation:
    """测试会话隔离"""

    @pytest.fixture
    def search_service(self, tmp_path):
        """创建测试用的 SearchService"""
        return SearchService(path=str(tmp_path / ".qdrant"))

    def test_agent_id_filter_with_event_log_layer(self, search_service):
        """测试 agent_id 过滤在 event_log 层生效"""
        agent1 = str(uuid4())
        agent2 = str(uuid4())

        # 为两个 agent 各添加记忆
        search_service.index_note(
            note_id=uuid4(),
            content="Agent 1 的记忆",
            layer="event_log",  # 使用字符串
            agent_id=agent1,
        )
        search_service.index_note(
            note_id=uuid4(),
            content="Agent 2 的记忆",
            layer="event_log",
            agent_id=agent2,
        )

        # 查询 agent1 的记忆
        results = search_service.search(
            query="记忆",
            layer=MemoryLayer.EVENT_LOG,
            agent_id=agent1,
            limit=10,
        )

        # 应该只返回 agent1 的记忆
        assert len(results) == 1
        assert results[0]["content"] == "Agent 1 的记忆"

    def test_agent_id_filter_not_applied_to_other_layers(self, search_service):
        """测试 agent_id 过滤不应用于其他层"""
        agent_id = str(uuid4())

        # 为不同层添加记忆
        search_service.index_note(
            note_id=uuid4(),
            content="Fact 层记忆",
            layer="verified_fact",
            agent_id=agent_id,
        )
        search_service.index_note(
            note_id=uuid4(),
            content="另一个 Fact 层记忆",
            layer="verified_fact",
            agent_id=str(uuid4()),  # 不同 agent
        )

        # 查询 fact 层时，agent_id 不应生效
        results = search_service.search(
            query="记忆",
            layer=MemoryLayer.VERIFIED_FACT,
            agent_id=agent_id,  # 指定 agent_id
            limit=10,
        )

        # 应该返回所有 fact 层记忆（agent_id 不生效）
        assert len(results) == 2

    def test_no_agent_id_returns_all_event_logs(self, search_service):
        """测试不指定 agent_id 时返回所有 event_log"""
        agent1 = str(uuid4())
        agent2 = str(uuid4())

        search_service.index_note(
            note_id=uuid4(),
            content="Agent 1 的记忆",
            layer="event_log",
            agent_id=agent1,
        )
        search_service.index_note(
            note_id=uuid4(),
            content="Agent 2 的记忆",
            layer="event_log",
            agent_id=agent2,
        )

        # 不指定 agent_id，应该返回所有
        results = search_service.search(
            query="记忆",
            layer=MemoryLayer.EVENT_LOG,
            agent_id=None,
            limit=10,
        )

        assert len(results) == 2

    def test_agent_id_isolation_with_v1_term_session(self, search_service):
        """测试使用 v1.x 术语 'session' 时 agent_id 过滤也生效"""
        agent1 = str(uuid4())
        agent2 = str(uuid4())

        search_service.index_note(
            note_id=uuid4(),
            content="Agent 1 会话记忆",
            layer="event_log",
            agent_id=agent1,
        )
        search_service.index_note(
            note_id=uuid4(),
            content="Agent 2 会话记忆",
            layer="event_log",
            agent_id=agent2,
        )

        # 使用 v1.x 术语 'session' 查询（会被映射到 EVENT_LOG）
        results = search_service.search(
            query="会话",
            layer=MemoryLayer.from_string("session"),  # v1.x 术语
            agent_id=agent1,
            limit=10,
        )

        # 应该只返回 agent1 的记忆
        assert len(results) == 1
        assert results[0]["content"] == "Agent 1 会话记忆"
