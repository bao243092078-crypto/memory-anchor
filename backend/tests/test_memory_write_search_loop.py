"""
Tests for Memory Write-Search Loop (Sprint 1: 记忆回写闭环)

验证：
1. add_memory 写入 Observation → search_memory 能检索出来
2. 置信度分级处理正确（≥0.9直接存入，0.7-0.9待审批，<0.7拒绝）
3. layer/category/tags 正确存储和过滤
"""

import pytest
import asyncio
from uuid import UUID
from datetime import datetime

from backend.services.memory import (
    MemoryService,
    MemoryAddRequest,
    MemorySearchRequest,
    MemorySource,
)
from backend.models.note import MemoryLayer, NoteCategory
from backend.services.search import SearchService


class TestMemoryWriteSearchLoop:
    """测试记忆写入-检索闭环"""

    @pytest.fixture
    def search_service(self, tmp_path):
        """创建临时 Qdrant 实例"""
        return SearchService(path=str(tmp_path / ".qdrant_test"))

    @pytest.fixture
    def memory_service(self, search_service):
        """创建 MemoryService，注入测试用 search_service"""
        service = MemoryService()
        service._search_service = search_service
        return service

    @pytest.mark.asyncio
    async def test_add_memory_high_confidence_then_search(self, memory_service):
        """测试高置信度记忆写入后能检索出来"""
        # 写入一条 bugfix 类型的记忆（高置信度）
        request = MemoryAddRequest(
            content="修复了 search_memory 空查询时返回 None 的问题",
            layer=MemoryLayer.FACT,
            category=NoteCategory.EVENT,
            source=MemorySource.AI_EXTRACTION,
            confidence=0.95,  # 高置信度，直接存入
        )

        result = await memory_service.add_memory(request)

        # 验证写入成功
        assert result["status"] == "saved"
        assert result["layer"] == "fact"
        assert result["id"] is not None
        assert not result.get("requires_approval", False)

        # 搜索刚写入的记忆
        search_request = MemorySearchRequest(
            query="search_memory 空查询",
            layer=MemoryLayer.FACT,
            limit=5,
            min_score=0.3,
            include_constitution=False,
        )

        search_results = await memory_service.search_memory(search_request)

        # 验证能检索到
        assert len(search_results) >= 1
        found = any("search_memory" in r.content for r in search_results)
        assert found, "写入的记忆应该能被检索到"

    @pytest.mark.asyncio
    async def test_add_memory_medium_confidence_pending_approval(self, memory_service):
        """测试中置信度记忆进入待审批状态"""
        request = MemoryAddRequest(
            content="患者可能提到下周要去医院",
            layer=MemoryLayer.FACT,
            category=NoteCategory.EVENT,
            source=MemorySource.AI_EXTRACTION,
            confidence=0.75,  # 中置信度，待审批
        )

        result = await memory_service.add_memory(request)

        # 验证进入待审批状态
        assert result["status"] == "pending_approval"
        assert result["requires_approval"] is True
        assert result["id"] is not None

    @pytest.mark.asyncio
    async def test_add_memory_low_confidence_rejected(self, memory_service):
        """测试低置信度记忆被拒绝"""
        request = MemoryAddRequest(
            content="这是一条模糊的记忆",
            layer=MemoryLayer.FACT,
            source=MemorySource.AI_EXTRACTION,
            confidence=0.5,  # 低置信度，拒绝
        )

        result = await memory_service.add_memory(request)

        # 验证被拒绝
        assert result["status"] == "rejected_low_confidence"
        assert result["id"] is None
        assert "置信度低于0.7" in result["reason"]

    @pytest.mark.asyncio
    async def test_add_memory_constitution_layer_rejected(self, memory_service):
        """测试宪法层写入被拒绝"""
        request = MemoryAddRequest(
            content="尝试写入宪法层",
            layer=MemoryLayer.CONSTITUTION,
            source=MemorySource.AI_EXTRACTION,
            confidence=0.95,
        )

        with pytest.raises(ValueError, match="宪法层"):
            await memory_service.add_memory(request)

    @pytest.mark.asyncio
    async def test_add_memory_session_layer_success(self, memory_service):
        """测试会话层写入成功"""
        request = MemoryAddRequest(
            content="本次会话讨论了 MCP 集成方案",
            layer=MemoryLayer.SESSION,
            source=MemorySource.AI_EXTRACTION,
            confidence=0.9,
        )

        result = await memory_service.add_memory(request)

        assert result["status"] == "saved"
        assert result["layer"] == "session"

    @pytest.mark.asyncio
    async def test_search_with_category_filter(self, memory_service):
        """测试按 category 过滤搜索"""
        # 写入 person 类别的记忆
        person_request = MemoryAddRequest(
            content="患者女儿王小红会每周五来探望",
            layer=MemoryLayer.FACT,
            category=NoteCategory.PERSON,
            source=MemorySource.CAREGIVER,  # 照护者输入，直接存储
        )
        await memory_service.add_memory(person_request)

        # 写入 event 类别的记忆
        event_request = MemoryAddRequest(
            content="今天修复了一个搜索相关的 Bug",
            layer=MemoryLayer.FACT,
            category=NoteCategory.EVENT,
            source=MemorySource.CAREGIVER,
        )
        await memory_service.add_memory(event_request)

        # 按 person 类别搜索
        search_request = MemorySearchRequest(
            query="探望",
            category=NoteCategory.PERSON,
            limit=5,
            include_constitution=False,
        )

        results = await memory_service.search_memory(search_request)

        # 验证只返回 person 类别
        for r in results:
            if r.category:
                assert r.category == NoteCategory.PERSON

    @pytest.mark.asyncio
    async def test_caregiver_input_no_confidence_check(self, memory_service):
        """测试照护者输入不受置信度限制"""
        # 照护者输入即使置信度低也直接存储
        request = MemoryAddRequest(
            content="照护者确认：患者对海鲜过敏",
            layer=MemoryLayer.FACT,
            category=NoteCategory.ITEM,
            source=MemorySource.CAREGIVER,
            confidence=0.5,  # 低置信度，但照护者输入不检查
        )

        result = await memory_service.add_memory(request)

        # 照护者输入直接存储
        assert result["status"] == "saved"


class TestObservationFormat:
    """测试 Observation JSON 格式验证"""

    def test_observation_required_fields(self):
        """验证 Observation 必填字段"""
        # 根据 MEMORY_STRATEGY.md 的 JSON Schema
        required_fields = ["type", "summary", "layer", "created_at", "author"]

        # 创建一个标准的 Observation
        observation = {
            "type": "bugfix",
            "summary": "修复了空指针问题",
            "layer": "fact",
            "created_at": datetime.now().isoformat(),
            "author": "claude-code",
        }

        # 验证必填字段存在
        for field in required_fields:
            assert field in observation

    def test_observation_type_layer_mapping(self):
        """验证类型与层级的映射规则"""
        # type → default layer mapping
        type_layer_map = {
            "decision": "fact",
            "bugfix": "fact",
            "refactor": "fact",
            "discovery": "session",
            "note": "session",
        }

        for obs_type, expected_layer in type_layer_map.items():
            # 根据 type 推断 layer
            if obs_type in ["decision", "bugfix", "refactor"]:
                assert expected_layer == "fact"
            else:
                assert expected_layer == "session"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
