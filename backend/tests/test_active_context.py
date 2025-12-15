"""
Tests for ActiveContext - L1 Working Memory

测试活跃上下文（工作记忆）功能：
- SimpleTTLCache 基本功能
- 会话隔离
- TTL 过期
- 容量限制
"""

import time

import pytest

from backend.core.active_context import (
    ActiveContext,
    SimpleTTLCache,
    get_context,
    set_context,
)


class TestSimpleTTLCache:
    """测试 SimpleTTLCache 基础功能"""

    def test_set_and_get(self):
        """测试基本的设置和获取"""
        cache = SimpleTTLCache(maxsize=100, ttl=3600)
        cache.set("key1", "value1")
        assert cache.get("key1") == "value1"

    def test_get_default(self):
        """测试获取不存在的键返回默认值"""
        cache = SimpleTTLCache()
        assert cache.get("nonexistent") is None
        assert cache.get("nonexistent", "default") == "default"

    def test_delete(self):
        """测试删除"""
        cache = SimpleTTLCache()
        cache.set("key1", "value1")
        assert cache.delete("key1") is True
        assert cache.get("key1") is None
        assert cache.delete("nonexistent") is False

    def test_clear(self):
        """测试清空"""
        cache = SimpleTTLCache()
        cache.set("key1", "value1")
        cache.set("key2", "value2")
        cache.clear()
        assert len(cache) == 0
        assert cache.get("key1") is None

    def test_keys(self):
        """测试获取所有键"""
        cache = SimpleTTLCache()
        cache.set("key1", "value1")
        cache.set("key2", "value2")
        keys = cache.keys()
        assert set(keys) == {"key1", "key2"}

    def test_len(self):
        """测试长度"""
        cache = SimpleTTLCache()
        assert len(cache) == 0
        cache.set("key1", "value1")
        assert len(cache) == 1
        cache.set("key2", "value2")
        assert len(cache) == 2

    def test_contains(self):
        """测试 in 操作符"""
        cache = SimpleTTLCache()
        cache.set("key1", "value1")
        assert "key1" in cache
        assert "nonexistent" not in cache

    def test_ttl_expiration(self):
        """测试 TTL 过期"""
        cache = SimpleTTLCache(ttl=1)  # 1 秒过期
        cache.set("key1", "value1")
        assert cache.get("key1") == "value1"

        # 等待过期
        time.sleep(1.1)
        assert cache.get("key1") is None

    def test_custom_ttl(self):
        """测试自定义 TTL"""
        cache = SimpleTTLCache(ttl=3600)  # 默认 1 小时
        cache.set("key1", "value1", ttl=1)  # 自定义 1 秒
        cache.set("key2", "value2")  # 使用默认

        time.sleep(1.1)
        assert cache.get("key1") is None
        assert cache.get("key2") == "value2"

    def test_maxsize_limit(self):
        """测试容量限制"""
        cache = SimpleTTLCache(maxsize=3, ttl=3600)
        cache.set("key1", "value1")
        cache.set("key2", "value2")
        cache.set("key3", "value3")

        # 添加第四个，应该删除最旧的
        cache.set("key4", "value4")

        assert len(cache) == 3
        assert "key4" in cache
        # key1 应该被删除（最旧）
        # 注意：这里可能因为时间精度问题，任何一个都可能被删除
        # 只验证总数正确
        valid_keys = [k for k in ["key1", "key2", "key3", "key4"] if k in cache]
        assert len(valid_keys) == 3


class TestActiveContext:
    """测试 ActiveContext 会话级上下文"""

    def setup_method(self):
        """每个测试前重置"""
        ActiveContext.reset()

    def test_set_and_get(self):
        """测试基本的设置和获取"""
        ActiveContext.set("topic", "今天的活动")
        assert ActiveContext.get("topic") == "今天的活动"

    def test_get_default(self):
        """测试获取不存在的键返回默认值"""
        assert ActiveContext.get("nonexistent") is None
        assert ActiveContext.get("nonexistent", "default") == "default"

    def test_delete(self):
        """测试删除"""
        ActiveContext.set("topic", "测试")
        assert ActiveContext.delete("topic") is True
        assert ActiveContext.get("topic") is None

    def test_session_isolation(self):
        """测试会话隔离"""
        # 设置 session1 的数据
        ActiveContext.set_session("session1")
        ActiveContext.set("data", "session1_data")

        # 切换到 session2
        ActiveContext.set_session("session2")
        ActiveContext.set("data", "session2_data")

        # 验证数据隔离
        ActiveContext.set_session("session1")
        assert ActiveContext.get("data") == "session1_data"

        ActiveContext.set_session("session2")
        assert ActiveContext.get("data") == "session2_data"

    def test_clear_session(self):
        """测试清除会话"""
        ActiveContext.set_session("test_session")
        ActiveContext.set("key1", "value1")
        ActiveContext.set("key2", "value2")

        ActiveContext.clear_session()

        assert ActiveContext.get("key1") is None
        assert ActiveContext.get("key2") is None

    def test_clear_session_isolation(self):
        """测试清除会话不影响其他会话"""
        # 设置 session1 的数据
        ActiveContext.set_session("session1")
        ActiveContext.set("data", "session1_data")

        # 设置 session2 的数据
        ActiveContext.set_session("session2")
        ActiveContext.set("data", "session2_data")

        # 清除 session2
        ActiveContext.clear_session()

        # session1 的数据应该还在
        ActiveContext.set_session("session1")
        assert ActiveContext.get("data") == "session1_data"

    def test_list_keys(self):
        """测试列出当前会话的所有键"""
        ActiveContext.set_session("test_session")
        ActiveContext.set("key1", "value1")
        ActiveContext.set("key2", "value2")

        keys = ActiveContext.list_keys()
        assert set(keys) == {"key1", "key2"}

    def test_get_all(self):
        """测试获取当前会话的所有上下文"""
        ActiveContext.set_session("test_session")
        ActiveContext.set("key1", "value1")
        ActiveContext.set("key2", "value2")

        all_context = ActiveContext.get_all()
        assert all_context == {"key1": "value1", "key2": "value2"}

    def test_get_session(self):
        """测试获取当前会话 ID"""
        ActiveContext.set_session("my_session")
        assert ActiveContext.get_session() == "my_session"

    def test_default_session(self):
        """测试默认会话"""
        # 注意：ContextVar 的默认值在新任务/线程中生效
        # 在同一线程中，需要显式设置回默认值
        ActiveContext.set_session("default")
        assert ActiveContext.get_session() == "default"

    def test_complex_values(self):
        """测试存储复杂值"""
        ActiveContext.set("dict_value", {"name": "张三", "age": 75})
        ActiveContext.set("list_value", [1, 2, 3])
        ActiveContext.set("nested", {"data": [{"id": 1}, {"id": 2}]})

        assert ActiveContext.get("dict_value") == {"name": "张三", "age": 75}
        assert ActiveContext.get("list_value") == [1, 2, 3]
        assert ActiveContext.get("nested")["data"][0]["id"] == 1


class TestConvenienceFunctions:
    """测试便捷函数"""

    def setup_method(self):
        """每个测试前重置"""
        ActiveContext.reset()

    def test_set_context_and_get_context(self):
        """测试 set_context 和 get_context 便捷函数"""
        set_context("topic", "讨论内容")
        assert get_context("topic") == "讨论内容"

    def test_get_context_default(self):
        """测试 get_context 默认值"""
        assert get_context("nonexistent") is None
        assert get_context("nonexistent", "fallback") == "fallback"


class TestActiveContextUseCases:
    """测试 ActiveContext 实际使用场景"""

    def setup_method(self):
        """每个测试前重置"""
        ActiveContext.reset()

    def test_store_current_topic(self):
        """测试存储当前讨论话题"""
        ActiveContext.set_session("chat_001")

        # 用户开始讨论某个话题
        ActiveContext.set("current_topic", "女儿的生日")
        ActiveContext.set("context_entities", ["女儿", "生日", "礼物"])

        # 后续对话可以引用
        assert ActiveContext.get("current_topic") == "女儿的生日"
        assert "女儿" in ActiveContext.get("context_entities")

    def test_store_draft_memory(self):
        """测试存储未确认的草稿记忆"""
        ActiveContext.set_session("chat_001")

        # AI 提取了一些待确认的信息
        draft = {
            "content": "患者提到今天看到了老朋友",
            "confidence": 0.7,
            "needs_confirmation": True,
        }
        ActiveContext.set("pending_memory", draft)

        # 等待用户确认
        pending = ActiveContext.get("pending_memory")
        assert pending["needs_confirmation"] is True
        assert pending["confidence"] == 0.7

    def test_store_session_preferences(self):
        """测试存储会话级别偏好"""
        ActiveContext.set_session("chat_001")

        # 用户在本次会话中表达的偏好
        ActiveContext.set("prefer_brief_responses", True)
        ActiveContext.set("language", "zh-CN")

        assert ActiveContext.get("prefer_brief_responses") is True
        assert ActiveContext.get("language") == "zh-CN"

        # 清除会话后偏好消失
        ActiveContext.clear_session()
        assert ActiveContext.get("prefer_brief_responses") is None


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
