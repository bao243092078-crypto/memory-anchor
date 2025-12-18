"""
测试 MemoryKernel 单例的线程安全性

验证场景：
1. 并发初始化时只创建一个实例
2. 多线程访问返回同一实例
3. 无死锁和竞态条件
"""

import sys
import threading
from pathlib import Path

import pytest

sys.path.insert(0, "/Users/baobao/projects/阿默斯海默症")


class TestMemoryKernelThreadSafety:
    """MemoryKernel 单例线程安全测试"""

    def test_concurrent_initialization(self, test_qdrant_path, monkeypatch):
        """测试并发初始化时只创建一个实例"""
        from backend.core import memory_kernel
        from backend.services.search import SearchService

        # 重置单例状态
        memory_kernel._kernel_instance = None

        # 创建测试用的 SearchService
        search_service = SearchService(path=str(test_qdrant_path))

        # 用于收集所有线程创建的实例
        instances = []
        instances_lock = threading.Lock()

        def create_instance():
            """线程工作函数：创建 kernel 实例"""
            kernel = memory_kernel.get_memory_kernel(search_service=search_service)
            with instances_lock:
                instances.append(kernel)

        # 启动 10 个并发线程
        threads = []
        for _ in range(10):
            t = threading.Thread(target=create_instance)
            threads.append(t)
            t.start()

        # 等待所有线程完成
        for t in threads:
            t.join()

        # 验证：所有实例应该是同一个对象（相同的 id）
        assert len(instances) == 10, "应该有 10 个返回的实例"
        unique_ids = set(id(inst) for inst in instances)
        assert len(unique_ids) == 1, f"应该只有 1 个唯一实例，但有 {len(unique_ids)} 个"

        # 清理
        search_service.client.close()
        del search_service
        memory_kernel._kernel_instance = None

    def test_concurrent_access_after_initialization(self, test_qdrant_path):
        """测试初始化后的并发访问"""
        from backend.core import memory_kernel
        from backend.services.search import SearchService

        # 重置单例状态
        memory_kernel._kernel_instance = None

        # 先初始化一次
        search_service = SearchService(path=str(test_qdrant_path))
        first_kernel = memory_kernel.get_memory_kernel(search_service=search_service)

        # 用于收集所有线程访问的实例
        instances = []
        instances_lock = threading.Lock()

        def access_instance():
            """线程工作函数：访问 kernel 实例"""
            kernel = memory_kernel.get_memory_kernel()
            with instances_lock:
                instances.append(kernel)

        # 启动 20 个并发线程访问
        threads = []
        for _ in range(20):
            t = threading.Thread(target=access_instance)
            threads.append(t)
            t.start()

        # 等待所有线程完成
        for t in threads:
            t.join()

        # 验证：所有访问应该返回同一个实例
        assert len(instances) == 20, "应该有 20 个返回的实例"
        assert all(inst is first_kernel for inst in instances), "所有实例应该是同一个对象"

        # 清理
        search_service.client.close()
        del search_service
        memory_kernel._kernel_instance = None

    def test_no_deadlock_under_load(self, test_qdrant_path):
        """测试高并发下无死锁"""
        from backend.core import memory_kernel
        from backend.services.search import SearchService

        # 重置单例状态
        memory_kernel._kernel_instance = None

        # 创建测试用的 SearchService
        search_service = SearchService(path=str(test_qdrant_path))

        # 用于统计成功访问次数
        success_count = 0
        count_lock = threading.Lock()

        def rapid_access():
            """线程工作函数：快速重复访问"""
            for _ in range(10):
                kernel = memory_kernel.get_memory_kernel(search_service=search_service)
                assert kernel is not None
                with count_lock:
                    nonlocal success_count
                    success_count += 1

        # 启动 10 个线程，每个线程访问 10 次
        threads = []
        for _ in range(10):
            t = threading.Thread(target=rapid_access)
            threads.append(t)
            t.start()

        # 设置超时等待（5秒），如果死锁则会超时
        for t in threads:
            t.join(timeout=5.0)
            assert not t.is_alive(), "线程应该已完成，检测到可能的死锁"

        # 验证所有访问都成功
        assert success_count == 100, f"应该有 100 次成功访问，实际 {success_count}"

        # 清理
        search_service.client.close()
        del search_service
        memory_kernel._kernel_instance = None


if __name__ == "__main__":
    # 直接运行测试
    pytest.main([__file__, "-v", "--tb=short"])
