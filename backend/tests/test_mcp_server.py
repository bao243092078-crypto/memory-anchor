"""
Tests for Memory Anchor MCP Server.
验证 MCP 工具和资源定义正确。
"""

import pytest
import asyncio
from uuid import uuid4

from backend.mcp_memory import (
    list_tools,
    list_resources,
    call_tool,
    read_resource,
)


class TestMCPTools:
    """测试 MCP 工具定义"""

    @pytest.mark.asyncio
    async def test_list_tools_returns_four_tools(self):
        """验证有四个工具"""
        tools = await list_tools()
        assert len(tools) == 4
        tool_names = {t.name for t in tools}
        assert tool_names == {"search_memory", "add_memory", "get_constitution", "propose_constitution_change"}

    @pytest.mark.asyncio
    async def test_search_memory_tool_schema(self):
        """验证 search_memory 工具 schema"""
        tools = await list_tools()
        search_tool = next(t for t in tools if t.name == "search_memory")

        schema = search_tool.inputSchema
        assert "query" in schema["properties"]
        assert "layer" in schema["properties"]
        assert "category" in schema["properties"]
        assert "limit" in schema["properties"]
        assert schema["required"] == ["query"]

    @pytest.mark.asyncio
    async def test_add_memory_tool_schema(self):
        """验证 add_memory 工具 schema"""
        tools = await list_tools()
        add_tool = next(t for t in tools if t.name == "add_memory")

        schema = add_tool.inputSchema
        assert "content" in schema["properties"]
        assert "layer" in schema["properties"]
        assert "category" in schema["properties"]
        assert "confidence" in schema["properties"]
        assert schema["required"] == ["content"]

        # 验证 layer 不包含 constitution
        layer_enum = schema["properties"]["layer"]["enum"]
        assert "constitution" not in layer_enum
        assert "fact" in layer_enum
        assert "session" in layer_enum

    @pytest.mark.asyncio
    async def test_get_constitution_tool_schema(self):
        """验证 get_constitution 工具 schema"""
        tools = await list_tools()
        const_tool = next(t for t in tools if t.name == "get_constitution")

        # 无需参数
        schema = const_tool.inputSchema
        assert schema["properties"] == {}


class TestMCPResources:
    """测试 MCP 资源定义"""

    @pytest.mark.asyncio
    async def test_list_resources_returns_two_resources(self):
        """验证有两个资源"""
        resources = await list_resources()
        assert len(resources) == 2
        uris = {str(r.uri) for r in resources}
        assert uris == {"memory://constitution", "memory://recent"}

    @pytest.mark.asyncio
    async def test_constitution_resource_metadata(self):
        """验证宪法层资源元数据"""
        resources = await list_resources()
        const_res = next(r for r in resources if str(r.uri) == "memory://constitution")

        assert "宪法层" in const_res.name
        assert const_res.mimeType == "text/plain"

    @pytest.mark.asyncio
    async def test_recent_resource_metadata(self):
        """验证最近记忆资源元数据"""
        resources = await list_resources()
        recent_res = next(r for r in resources if str(r.uri) == "memory://recent")

        assert "最近" in recent_res.name
        assert recent_res.mimeType == "text/plain"


class TestMCPToolCalls:
    """测试 MCP 工具调用"""

    @pytest.mark.asyncio
    async def test_call_unknown_tool(self):
        """测试调用未知工具"""
        result = await call_tool("unknown_tool", {})
        assert len(result) == 1
        assert "未知工具" in result[0].text

    @pytest.mark.asyncio
    async def test_add_memory_rejects_constitution(self):
        """测试添加宪法层被拒绝"""
        result = await call_tool("add_memory", {
            "content": "测试宪法层",
            "layer": "constitution",
        })
        assert len(result) == 1
        assert "错误" in result[0].text or "不允许" in result[0].text

    @pytest.mark.asyncio
    async def test_get_constitution_returns_formatted_text(self):
        """测试获取宪法层返回格式化文本"""
        result = await call_tool("get_constitution", {})
        assert len(result) == 1
        # 可能为空或有数据，都应该返回正确格式
        text = result[0].text
        assert "宪法层" in text


class TestMCPResourceRead:
    """测试 MCP 资源读取"""

    @pytest.mark.asyncio
    async def test_read_unknown_resource(self):
        """测试读取未知资源"""
        result = await read_resource("memory://unknown")
        assert "未知资源" in result

    @pytest.mark.asyncio
    async def test_read_constitution_resource(self):
        """测试读取宪法层资源"""
        result = await read_resource("memory://constitution")
        # 可能为空或有数据
        assert isinstance(result, str)

    @pytest.mark.asyncio
    async def test_read_recent_resource(self):
        """测试读取最近记忆资源"""
        result = await read_resource("memory://recent")
        # 可能为空或有数据
        assert isinstance(result, str)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
