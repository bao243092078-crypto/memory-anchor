"""
Memory Traceability Tests - v2.1 可追溯性字段测试

测试 session_id 和 related_files 字段的：
1. 存储到 Qdrant
2. 从 Qdrant 检索
3. MCP 自动填充
"""

import pytest
from uuid import uuid4

from backend.models.note import MemoryLayer, NoteCategory
from backend.services.memory import (
    MemoryAddRequest,
    MemorySearchRequest,
    MemorySource,
    get_memory_service,
)
from backend.services.search import get_search_service


class TestTraceabilityStorage:
    """测试可追溯性字段存储"""

    @pytest.fixture
    def search_service(self):
        """获取搜索服务"""
        return get_search_service()

    def test_index_note_with_session_id(self, search_service):
        """测试存储 session_id"""
        note_id = uuid4()
        session_id = "20251227_200000"

        success = search_service.index_note(
            note_id=note_id,
            content="测试记忆内容",
            layer="verified_fact",
            category="event",
            session_id=session_id,
        )

        assert success

        # 验证存储
        note = search_service.get_note(note_id)
        assert note is not None
        assert note.get("session_id") == session_id

    def test_index_note_with_related_files(self, search_service):
        """测试存储 related_files"""
        note_id = uuid4()
        related_files = [
            "backend/services/search.py",
            "backend/core/memory_kernel.py",
        ]

        success = search_service.index_note(
            note_id=note_id,
            content="测试记忆内容",
            layer="verified_fact",
            category="event",
            related_files=related_files,
        )

        assert success

        # 验证存储
        note = search_service.get_note(note_id)
        assert note is not None
        assert note.get("related_files") == related_files

    def test_index_note_with_both_traceability_fields(self, search_service):
        """测试同时存储 session_id 和 related_files"""
        note_id = uuid4()
        session_id = "20251227_201500"
        related_files = ["backend/mcp_memory.py"]

        success = search_service.index_note(
            note_id=note_id,
            content="修复了 MCP 工具调用问题",
            layer="verified_fact",
            category="event",
            session_id=session_id,
            related_files=related_files,
        )

        assert success

        # 验证存储
        note = search_service.get_note(note_id)
        assert note is not None
        assert note.get("session_id") == session_id
        assert note.get("related_files") == related_files


class TestTraceabilityRetrieval:
    """测试可追溯性字段检索"""

    @pytest.fixture
    def memory_service(self):
        """获取记忆服务"""
        return get_memory_service()

    @pytest.mark.asyncio
    async def test_search_returns_traceability_fields(self, memory_service):
        """测试搜索结果包含可追溯性字段"""
        # 添加带有可追溯性字段的记忆
        request = MemoryAddRequest(
            content="测试可追溯性搜索结果",
            layer=MemoryLayer.VERIFIED_FACT,
            category=NoteCategory.EVENT,
            source=MemorySource.CAREGIVER,
            confidence=1.0,
            session_id="20251227_test_search",
            related_files=["test_file.py"],
        )

        add_result = await memory_service.add_memory(request)
        assert add_result["status"] == "saved"

        # 搜索并验证
        search_request = MemorySearchRequest(
            query="可追溯性搜索结果",
            limit=5,
        )
        results = await memory_service.search_memory(search_request)

        # 找到我们刚添加的记忆
        matching = [r for r in results if "可追溯性搜索结果" in r.content]
        assert len(matching) > 0

        result = matching[0]
        assert result.session_id == "20251227_test_search"
        assert result.related_files == ["test_file.py"]


class TestMemoryAddRequestFields:
    """测试 MemoryAddRequest 新字段"""

    def test_request_accepts_session_id(self):
        """测试请求接受 session_id"""
        request = MemoryAddRequest(
            content="测试内容",
            session_id="20251227_123456",
        )
        assert request.session_id == "20251227_123456"

    def test_request_accepts_related_files(self):
        """测试请求接受 related_files"""
        request = MemoryAddRequest(
            content="测试内容",
            related_files=["file1.py", "file2.py"],
        )
        assert request.related_files == ["file1.py", "file2.py"]

    def test_request_fields_optional(self):
        """测试新字段是可选的"""
        request = MemoryAddRequest(
            content="只有内容",
        )
        assert request.session_id is None
        assert request.related_files is None


class TestMemoryResultFields:
    """测试 MemoryResult 新字段"""

    @pytest.fixture
    def memory_service(self):
        """获取记忆服务"""
        return get_memory_service()

    @pytest.mark.asyncio
    async def test_result_contains_session_id(self, memory_service):
        """测试结果包含 session_id"""
        request = MemoryAddRequest(
            content="测试结果包含会话ID",
            layer=MemoryLayer.VERIFIED_FACT,
            source=MemorySource.CAREGIVER,
            confidence=1.0,
            session_id="20251227_result_test",
        )

        add_result = await memory_service.add_memory(request)
        assert add_result.get("session_id") == "20251227_result_test"

    @pytest.mark.asyncio
    async def test_result_contains_related_files(self, memory_service):
        """测试结果包含 related_files"""
        request = MemoryAddRequest(
            content="测试结果包含关联文件",
            layer=MemoryLayer.VERIFIED_FACT,
            source=MemorySource.CAREGIVER,
            confidence=1.0,
            related_files=["backend/tests/test_traceability.py"],
        )

        add_result = await memory_service.add_memory(request)
        assert add_result.get("related_files") == ["backend/tests/test_traceability.py"]


class TestBackwardCompatibility:
    """测试向后兼容性"""

    @pytest.fixture
    def search_service(self):
        """获取搜索服务"""
        return get_search_service()

    def test_old_notes_return_null_traceability(self, search_service):
        """测试旧记忆返回 null 的可追溯性字段"""
        # 创建一条没有可追溯性字段的记忆（模拟旧数据）
        note_id = uuid4()
        success = search_service.index_note(
            note_id=note_id,
            content="旧格式记忆，没有可追溯性字段",
            layer="verified_fact",
            category="event",
            # 不传 session_id 和 related_files
        )

        assert success

        # 验证检索结果
        note = search_service.get_note(note_id)
        assert note is not None
        # 旧记忆应该没有这些字段，或者为 None
        assert note.get("session_id") is None
        assert note.get("related_files") is None
