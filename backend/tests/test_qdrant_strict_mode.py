"""
测试 Qdrant Server Fail-Fast 模式

Bug 5: Remove Qdrant auto-downgrade logic
确保生产环境未配置 QDRANT_URL 时会失败，而不是静默降级到本地模式
"""

import pytest

from backend.config import get_config
from backend.services.search import SearchService


class TestQdrantStrictMode:
    """测试 Qdrant 严格模式（Fail-Fast）"""

    def test_missing_url_and_path_raises_error(self):
        """测试未配置 URL 和 path 时抛出错误"""
        with pytest.raises(ValueError, match="QDRANT_URL must be set"):
            SearchService(url=None, path=None)

    def test_invalid_server_url_raises_runtime_error(self):
        """测试无效的 Server URL 抛出 RuntimeError"""
        with pytest.raises(RuntimeError, match="Qdrant Server connection failed"):
            SearchService(url="http://invalid-host:9999")

    def test_local_path_works_for_testing(self, tmp_path):
        """测试本地路径模式（仅用于测试）"""
        service = SearchService(path=str(tmp_path / ".qdrant"))
        assert service.mode == "local"
        assert service.client is not None

    def test_valid_server_url_works(self):
        """测试有效的 Server URL（需要实际运行的 Qdrant Server）"""
        # 这个测试需要环境变量 QDRANT_URL 指向运行中的 server
        # 如果没有 server 运行，会抛出 RuntimeError
        config = get_config()
        if config.qdrant_url:
            service = SearchService(url=config.qdrant_url)
            assert service.mode == "server"
            assert service.client is not None
        else:
            pytest.skip("No QDRANT_URL configured, skipping server test")

    def test_prefer_server_parameter_is_deprecated(self, tmp_path):
        """测试 prefer_server 参数已废弃但保留向后兼容"""
        # prefer_server 参数不应影响行为
        service1 = SearchService(path=str(tmp_path / ".qdrant1"), prefer_server=True)
        service2 = SearchService(path=str(tmp_path / ".qdrant2"), prefer_server=False)
        assert service1.mode == "local"
        assert service2.mode == "local"
