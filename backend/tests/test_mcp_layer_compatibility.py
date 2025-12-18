"""
测试 MCP v1/v2 术语兼容性

Bug 2: MCP v1/v2 terminology incompatibility
确保 v1.x 术语（constitution, fact, session）能正确映射到 v2.x（identity_schema, verified_fact, event_log）
"""

import pytest
from backend.models.note import MemoryLayer


class TestMemoryLayerCompatibility:
    """测试 MemoryLayer 的 v1/v2 术语兼容性"""

    def test_v2_terms_work(self):
        """测试 v2.x 新术语可以正常工作"""
        assert MemoryLayer.from_string("identity_schema") == MemoryLayer.IDENTITY_SCHEMA
        assert MemoryLayer.from_string("active_context") == MemoryLayer.ACTIVE_CONTEXT
        assert MemoryLayer.from_string("event_log") == MemoryLayer.EVENT_LOG
        assert MemoryLayer.from_string("verified_fact") == MemoryLayer.VERIFIED_FACT
        assert (
            MemoryLayer.from_string("operational_knowledge")
            == MemoryLayer.OPERATIONAL_KNOWLEDGE
        )

    def test_v1_terms_backward_compatible(self):
        """测试 v1.x 旧术语向后兼容"""
        # constitution → identity_schema
        assert MemoryLayer.from_string("constitution") == MemoryLayer.IDENTITY_SCHEMA

        # fact → verified_fact
        assert MemoryLayer.from_string("fact") == MemoryLayer.VERIFIED_FACT

        # session → event_log (默认映射到 event_log)
        assert MemoryLayer.from_string("session") == MemoryLayer.EVENT_LOG

    def test_case_insensitive(self):
        """测试大小写不敏感"""
        assert MemoryLayer.from_string("CONSTITUTION") == MemoryLayer.IDENTITY_SCHEMA
        assert MemoryLayer.from_string("Fact") == MemoryLayer.VERIFIED_FACT
        assert MemoryLayer.from_string("Session") == MemoryLayer.EVENT_LOG

    def test_invalid_layer_raises_error(self):
        """测试无效的层级名称抛出错误"""
        with pytest.raises(ValueError, match="Invalid memory layer"):
            MemoryLayer.from_string("invalid_layer")

        with pytest.raises(ValueError, match="Invalid memory layer"):
            MemoryLayer.from_string("")

    def test_none_layer_raises_error(self):
        """测试 None 抛出错误"""
        with pytest.raises(ValueError, match="Invalid memory layer"):
            MemoryLayer.from_string(None)

    def test_whitespace_trimmed(self):
        """测试前后空格会被去除"""
        assert MemoryLayer.from_string(" constitution ") == MemoryLayer.IDENTITY_SCHEMA
        assert MemoryLayer.from_string("\tfact\n") == MemoryLayer.VERIFIED_FACT
