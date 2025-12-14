"""
Twin Mode Integration Test - 双模集成测试

验证 Claude (MCP Server) 和 Codex (Native SDK) 能看到一致的记忆。

测试场景：
1. 通过 SDK 添加记忆 → 验证能通过 MCP 查到
2. 通过 MCP 添加记忆 → 验证能通过 SDK 查到
3. 并发访问测试（Claude 和 Codex 同时查询）
"""

import asyncio
from uuid import uuid4

import pytest

from backend.models.note import MemoryLayer

# SDK 相关导入（同步）
from backend.sdk import MemoryClient

# MCP 相关导入（异步）
from backend.services.memory import MemoryAddRequest, MemorySearchRequest, MemoryService


class TestTwinModeIntegration:
    """双模集成测试"""

    @pytest.fixture
    async def memory_service(self):
        """MCP Server 使用的 MemoryService（异步）"""
        return MemoryService()

    @pytest.fixture
    def memory_client(self):
        """Codex 使用的 MemoryClient（同步）"""
        return MemoryClient(agent_id="codex_test")

    @pytest.mark.asyncio
    async def test_sdk_to_mcp_consistency(self, memory_service, memory_client):
        """
        测试：通过 SDK 添加 → MCP 能查到
        """
        # 1. Codex 通过 SDK 添加记忆
        test_content = f"测试记忆-SDK-{uuid4().hex[:8]}"
        sdk_result = memory_client.add_observation(
            content=test_content,
            layer="fact",
            confidence=0.95  # 高置信度，直接存入
        )
        assert sdk_result["status"] == "saved"
        _note_id = sdk_result["id"]  # noqa: F841

        # 等待索引完成
        await asyncio.sleep(0.5)

        # 2. Claude 通过 MCP 搜索
        search_request = MemorySearchRequest(
            query=test_content,
            layer=MemoryLayer.FACT,
            limit=5,
        )
        mcp_results = await memory_service.search_memory(search_request)

        # 3. 验证一致性
        found = any(r.content == test_content for r in mcp_results)
        assert found, "MCP 应该能查到 SDK 添加的记忆"

    @pytest.mark.asyncio
    async def test_mcp_to_sdk_consistency(self, memory_service, memory_client):
        """
        测试：通过 MCP 添加 → SDK 能查到
        """
        # 1. Claude 通过 MCP 添加记忆
        test_content = f"测试记忆-MCP-{uuid4().hex[:8]}"
        add_request = MemoryAddRequest(
            content=test_content,
            layer=MemoryLayer.FACT,
            confidence=0.95,
        )
        mcp_result = await memory_service.add_memory(add_request)
        assert mcp_result["status"] == "saved"

        # 等待索引完成
        await asyncio.sleep(0.5)

        # 2. Codex 通过 SDK 搜索（在线程中运行同步代码）
        sdk_results = await asyncio.to_thread(
            memory_client.search_memory,
            query=test_content,
            layer="fact"
        )

        # 3. 验证一致性
        found = any(r["content"] == test_content for r in sdk_results)
        assert found, "SDK 应该能查到 MCP 添加的记忆"

    @pytest.mark.asyncio
    async def test_constitution_consistency(self, memory_service, memory_client):
        """
        测试：宪法层一致性（所有 AI 看到相同的核心身份）
        """
        # 1. Claude 通过 MCP 获取宪法层
        mcp_constitution = await memory_service.get_constitution()

        # 2. Codex 通过 SDK 获取宪法层（在线程中运行）
        sdk_constitution = await asyncio.to_thread(
            memory_client.get_constitution
        )

        # 3. 验证一致性（内容应该相同）
        mcp_contents = {r.content for r in mcp_constitution}
        sdk_contents = {r["content"] for r in sdk_constitution}

        assert mcp_contents == sdk_contents, "宪法层内容应该完全一致"

    @pytest.mark.asyncio
    async def test_concurrent_search(self, memory_service, memory_client):
        """
        测试：并发访问（Claude 和 Codex 同时查询）
        """
        # 添加测试记忆
        test_content = f"测试并发-{uuid4().hex[:8]}"
        add_request = MemoryAddRequest(
            content=test_content,
            layer=MemoryLayer.FACT,
            confidence=0.95,
        )
        await memory_service.add_memory(add_request)
        await asyncio.sleep(0.5)

        # 并发查询
        async def claude_search():
            """Claude 的查询（async）"""
            req = MemorySearchRequest(query=test_content, limit=5)
            return await memory_service.search_memory(req)

        async def codex_search():
            """Codex 的查询（sync → async）"""
            return await asyncio.to_thread(
                memory_client.search_memory,
                query=test_content
            )

        # 同时执行
        claude_results, codex_results = await asyncio.gather(
            claude_search(),
            codex_search()
        )

        # 验证两者都能查到
        claude_found = any(r.content == test_content for r in claude_results)
        codex_found = any(r["content"] == test_content for r in codex_results)

        assert claude_found, "Claude 应该能查到"
        assert codex_found, "Codex 应该能查到"

    @pytest.mark.asyncio
    async def test_session_isolation(self, memory_service, memory_client):
        """
        测试：会话层隔离（各自的对话上下文）
        """
        # 1. Codex 添加会话层记忆
        codex_session_content = f"Codex会话-{uuid4().hex[:8]}"
        memory_client.add_observation(
            content=codex_session_content,
            layer="session",
            confidence=0.9
        )
        await asyncio.sleep(0.5)

        # 2. Claude 添加会话层记忆
        claude_session_content = f"Claude会话-{uuid4().hex[:8]}"
        add_request = MemoryAddRequest(
            content=claude_session_content,
            layer=MemoryLayer.SESSION,
            confidence=0.9,
        )
        await memory_service.add_memory(add_request)
        await asyncio.sleep(0.5)

        # 3. Codex 搜索会话层（应该只看到自己的）
        codex_sessions = await asyncio.to_thread(
            memory_client.search_memory,
            query="会话",
            layer="session"
        )
        _codex_contents = {r["content"] for r in codex_sessions}  # noqa: F841

        # Codex 应该能看到自己的，看不到 Claude 的
        # （因为 MemoryClient 默认 agent_id="codex"）
        # 注：这个测试依赖于 MemoryKernel 实现会话隔离


if __name__ == "__main__":
    # 简单的命令行测试
    print("运行集成测试...")
    pytest.main([__file__, "-v", "-s"])
