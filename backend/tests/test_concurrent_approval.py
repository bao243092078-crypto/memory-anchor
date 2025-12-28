"""
测试批准工作流的并发安全性

验证乐观锁机制能够防止并发批准同一记录的 race condition。
"""

import asyncio

import pytest

from backend.config import reset_config
from backend.core.memory_kernel import MemoryKernel
from backend.services import pending_memory
from backend.services.pending_memory import PendingMemoryService
from backend.services.search import SearchService


class TestConcurrentApproval:
    """测试并发批准场景"""

    @pytest.fixture(autouse=True)
    def setup_test_db(self, tmp_path, monkeypatch, request):
        """为每个测试设置独立的临时 SQLite 数据库和 Qdrant collection"""
        test_db = tmp_path / "test_concurrent.db"

        # 重置配置
        reset_config()

        # 每个测试使用唯一的 collection name 确保隔离
        unique_collection = f"test_concurrent_{request.node.name}"
        monkeypatch.setenv("MEMORY_ANCHOR_COLLECTION", unique_collection)

        # monkeypatch _get_db_path 函数返回测试数据库路径
        monkeypatch.setattr(pending_memory, "_get_db_path", lambda: test_db)

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

    async def approve_with_delay(
        self,
        pending_service: PendingMemoryService,
        memory_kernel: MemoryKernel,
        note_id: str,
        delay_ms: int = 0
    ):
        """
        模拟批准操作（带延迟）

        Returns:
            tuple: (success: bool, message: str)
        """
        if delay_ms > 0:
            await asyncio.sleep(delay_ms / 1000)

        # 尝试锁定
        memory = pending_service.try_lock_for_processing(note_id)
        if not memory:
            return (False, "Failed to lock (already processing)")

        try:
            # 索引到 Qdrant
            memory_kernel.search.index_note(
                note_id=memory["id"],
                content=memory["content"],
                layer=memory["layer"],
                category=memory["category"],
                is_active=True,
                confidence=memory["confidence"],
                source=memory["source"],
                created_at=memory["created_at"],
            )

            # 更新状态
            approved = pending_service.approve_pending(note_id, approved_by="test_concurrent")
            if not approved:
                # 补偿：设置为 inactive
                from uuid import UUID
                memory_kernel.search.update_note_status(UUID(memory["id"]), is_active=False)
                pending_service.unlock_from_processing(note_id)
                return (False, "Status changed during processing")

            # 删除记录
            pending_service.delete_pending(note_id)
            return (True, "Approved successfully")

        except Exception as e:
            # 释放锁
            pending_service.unlock_from_processing(note_id)
            return (False, f"Exception: {str(e)}")

    @pytest.mark.asyncio
    async def test_concurrent_approve_same_memory(
        self,
        memory_kernel,
        pending_service
    ):
        """
        测试并发批准同一记忆（应该只有一个成功）
        """
        # 添加待审批记忆
        result = memory_kernel.add_memory(
            content="并发测试记忆",
            layer="verified_fact",
            category="event",
            confidence=0.8,
            source="ai_extraction",
        )
        note_id = str(result["id"])

        # 模拟两个并发请求
        task1 = self.approve_with_delay(pending_service, memory_kernel, note_id, delay_ms=0)
        task2 = self.approve_with_delay(pending_service, memory_kernel, note_id, delay_ms=10)

        results = await asyncio.gather(task1, task2)

        # 验证：只有一个成功
        success_count = sum(1 for success, _ in results if success)
        assert success_count == 1, f"Expected 1 success, got {success_count}. Results: {results}"

        # 验证：失败的请求收到正确的错误消息
        failed_result = [r for r in results if not r[0]][0]
        assert "already processing" in failed_result[1].lower() or "status changed" in failed_result[1].lower()

        # 验证：记录不在待审批列表中
        pending_list = pending_service.list_pending()
        assert len(pending_list) == 0, "Memory should be removed from pending list"

    @pytest.mark.asyncio
    async def test_concurrent_approve_vs_reject(
        self,
        memory_kernel,
        pending_service
    ):
        """
        测试并发批准 vs 拒绝（应该只有一个成功）
        """
        # 添加待审批记忆
        result = memory_kernel.add_memory(
            content="批准vs拒绝测试",
            layer="verified_fact",
            category="event",
            confidence=0.8,
            source="ai_extraction",
        )
        note_id = str(result["id"])

        async def reject_with_lock():
            """模拟拒绝操作（也使用锁）"""
            memory = pending_service.try_lock_for_processing(note_id)
            if not memory:
                return (False, "Failed to lock")

            try:
                # 直接更新为 rejected（跳过 approve_pending）
                rejected = pending_service.reject_pending(note_id, rejected_by="test_concurrent")
                if rejected:
                    return (True, "Rejected successfully")
                else:
                    pending_service.unlock_from_processing(note_id)
                    return (False, "Reject failed")
            except Exception as e:
                pending_service.unlock_from_processing(note_id)
                return (False, f"Exception: {str(e)}")

        # 并发执行批准和拒绝
        task1 = self.approve_with_delay(pending_service, memory_kernel, note_id, delay_ms=0)
        task2 = reject_with_lock()

        results = await asyncio.gather(task1, task2)

        # 验证：只有一个成功
        success_count = sum(1 for success, _ in results if success)
        assert success_count == 1, f"Expected 1 success, got {success_count}. Results: {results}"

    @pytest.mark.asyncio
    async def test_unlock_after_failure(
        self,
        memory_kernel,
        pending_service
    ):
        """
        测试失败后释放锁，记录可以重新被处理
        """
        # 添加待审批记忆
        result = memory_kernel.add_memory(
            content="失败重试测试",
            layer="verified_fact",
            category="event",
            confidence=0.8,
            source="ai_extraction",
        )
        note_id = str(result["id"])

        # 第一次尝试：锁定后故意失败
        memory = pending_service.try_lock_for_processing(note_id)
        assert memory is not None, "First lock should succeed"
        assert memory["status"] == "processing"

        # 释放锁
        unlocked = pending_service.unlock_from_processing(note_id)
        assert unlocked, "Unlock should succeed"

        # 验证状态恢复为 pending
        memory_after = pending_service.get_pending(note_id)
        assert memory_after is not None, "Memory should be pending again"
        assert memory_after["status"] == "pending"

        # 第二次尝试：应该能够成功锁定
        memory2 = pending_service.try_lock_for_processing(note_id)
        assert memory2 is not None, "Second lock should succeed after unlock"
        assert memory2["status"] == "processing"
