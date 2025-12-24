"""
L4 search_operations MCP 工具测试

验证：
1. search_operations 工具能通过关键词匹配 SOP
2. quick_match 直接匹配
3. triggers 触发条件匹配
4. include_content 参数正确返回文件内容
5. 错误处理（目录不存在、索引不存在）
"""

import os
from pathlib import Path
from unittest.mock import patch

import pytest


# 设置项目根目录环境变量，确保测试能找到 .ai/operations/
@pytest.fixture(autouse=True)
def set_project_root():
    """设置项目根目录"""
    project_root = Path(__file__).parent.parent
    os.environ["MCP_MEMORY_PROJECT_ROOT"] = str(project_root)
    yield
    # 清理
    if "MCP_MEMORY_PROJECT_ROOT" in os.environ:
        del os.environ["MCP_MEMORY_PROJECT_ROOT"]


class TestSearchOperationsTool:
    """测试 search_operations MCP 工具"""

    @pytest.mark.asyncio
    async def test_search_qdrant_keyword(self):
        """测试：关键词 'qdrant' 能匹配到 SOP"""
        from backend.mcp_memory import _handle_search_operations

        result = await _handle_search_operations({"query": "qdrant"})

        assert len(result) == 1
        text = result[0].text
        assert "qdrant" in text.lower()
        assert "sop-qdrant-startup.md" in text

    @pytest.mark.asyncio
    async def test_search_pending_keyword(self):
        """测试：关键词 'pending' 能匹配到 memory-sync SOP"""
        from backend.mcp_memory import _handle_search_operations

        result = await _handle_search_operations({"query": "pending"})

        assert len(result) == 1
        text = result[0].text
        assert "pending" in text.lower() or "memory" in text.lower()
        assert "sop-memory-sync.md" in text

    @pytest.mark.asyncio
    async def test_search_session_start(self):
        """测试：关键词 '会话' 能匹配到 workflow"""
        from backend.mcp_memory import _handle_search_operations

        result = await _handle_search_operations({"query": "会话"})

        assert len(result) == 1
        text = result[0].text
        assert "workflow-session-start.md" in text

    @pytest.mark.asyncio
    async def test_search_with_trigger(self):
        """测试：通过 trigger 条件匹配"""
        from backend.mcp_memory import _handle_search_operations

        # "502 Bad Gateway" 是 qdrant-startup 的 trigger
        result = await _handle_search_operations({"query": "502"})

        assert len(result) == 1
        text = result[0].text
        assert "sop-qdrant-startup.md" in text

    @pytest.mark.asyncio
    async def test_search_no_match(self):
        """测试：无匹配时返回提示"""
        from backend.mcp_memory import _handle_search_operations

        result = await _handle_search_operations({"query": "不存在的关键词xyz123"})

        assert len(result) == 1
        text = result[0].text
        assert "未找到" in text

    @pytest.mark.asyncio
    async def test_search_empty_query(self):
        """测试：空 query 返回错误"""
        from backend.mcp_memory import _handle_search_operations

        result = await _handle_search_operations({"query": ""})

        assert len(result) == 1
        text = result[0].text
        assert "错误" in text

    @pytest.mark.asyncio
    async def test_search_with_content(self):
        """测试：include_content=True 返回文件内容"""
        from backend.mcp_memory import _handle_search_operations

        result = await _handle_search_operations(
            {"query": "qdrant", "include_content": True}
        )

        assert len(result) == 1
        text = result[0].text
        # 应该包含文件内容（markdown 代码块）
        assert "```markdown" in text
        assert "触发条件" in text  # SOP 文件中应有触发条件

    @pytest.mark.asyncio
    async def test_search_case_insensitive(self):
        """测试：搜索不区分大小写"""
        from backend.mcp_memory import _handle_search_operations

        result1 = await _handle_search_operations({"query": "QDRANT"})
        result2 = await _handle_search_operations({"query": "qdrant"})

        # 都应该能匹配到
        assert "sop-qdrant-startup.md" in result1[0].text
        assert "sop-qdrant-startup.md" in result2[0].text


class TestSearchOperationsEdgeCases:
    """测试 search_operations 边界情况"""

    @pytest.mark.asyncio
    async def test_missing_ops_dir(self):
        """测试：.ai/operations/ 目录不存在时的处理"""
        from backend.mcp_memory import _handle_search_operations

        # 临时设置不存在的目录
        os.environ["MCP_MEMORY_PROJECT_ROOT"] = "/tmp/nonexistent_project"

        result = await _handle_search_operations({"query": "qdrant"})

        text = result[0].text
        assert "目录不存在" in text or "不存在" in text

    @pytest.mark.asyncio
    async def test_tool_in_list_tools(self):
        """测试：search_operations 工具在 list_tools 中注册"""
        from backend.mcp_memory import list_tools

        tools = await list_tools()
        tool_names = [t.name for t in tools]

        assert "search_operations" in tool_names

    @pytest.mark.asyncio
    async def test_tool_description_has_triggers(self):
        """测试：工具描述包含触发场景"""
        from backend.mcp_memory import list_tools

        tools = await list_tools()
        search_ops_tool = next(t for t in tools if t.name == "search_operations")

        desc = search_ops_tool.description
        # 应该包含强制调用场景
        assert "强制调用场景" in desc
        assert "Qdrant" in desc or "qdrant" in desc.lower()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
