"""
Tests for Memory API endpoints.
验证 /api/v1/memory/* 接口功能。
"""

import os
import shutil
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.services.memory import MemoryService, get_memory_service
from backend.services.search import SearchService

client = TestClient(app)


class TestMemoryAddAPI:
    """测试 POST /api/v1/memory/add"""

    def test_add_fact_memory_success(self):
        """测试添加事实层记忆（v2.0 使用新术语 verified_fact）"""
        response = client.post(
            "/api/v1/memory/add",
            json={
                "content": "患者今天去了公园散步",
                "layer": "verified_fact",  # v2.0 新术语
                "category": "event",
                "source": "caregiver",
                "confidence": 1.0,
            },
        )

        assert response.status_code == 201
        data = response.json()
        assert data["status"] == "saved"
        assert data["layer"] == "verified_fact"  # v2.0 新术语
        assert data["confidence"] == 1.0
        assert data["id"] is not None

    def test_add_session_memory_success(self):
        """测试添加事件层记忆（v2.0 使用新术语 event_log）"""
        response = client.post(
            "/api/v1/memory/add",
            json={
                "content": "刚才和女儿通了电话",
                "layer": "event_log",  # v2.0 新术语
                "category": "event",
                "source": "caregiver",
            },
        )

        assert response.status_code == 201
        data = response.json()
        assert data["status"] == "saved"
        assert data["layer"] == "event_log"  # v2.0 新术语

    def test_add_constitution_memory_rejected(self):
        """测试宪法层创建被拒绝"""
        response = client.post(
            "/api/v1/memory/add",
            json={
                "content": "你是王明",
                "layer": "constitution",
                "source": "caregiver",
            },
        )

        assert response.status_code == 400
        assert "宪法层" in response.json()["detail"]

    def test_add_ai_extraction_high_confidence(self):
        """测试AI提取高置信度直接存储"""
        response = client.post(
            "/api/v1/memory/add",
            json={
                "content": "患者提到他喜欢下棋",
                "layer": "verified_fact",  # v2.0 新术语
                "source": "ai_extraction",
                "confidence": 0.95,
            },
        )

        assert response.status_code == 201
        data = response.json()
        assert data["status"] == "saved"
        assert data["requires_approval"] is False

    def test_add_ai_extraction_medium_confidence(self):
        """测试AI提取中置信度需审批"""
        response = client.post(
            "/api/v1/memory/add",
            json={
                "content": "患者可能以前住在上海",
                "layer": "verified_fact",  # v2.0 新术语
                "source": "ai_extraction",
                "confidence": 0.75,
            },
        )

        assert response.status_code == 201
        data = response.json()
        assert data["status"] == "pending_approval"
        assert data["requires_approval"] is True

    def test_add_ai_extraction_low_confidence_rejected(self):
        """测试AI提取低置信度被拒绝"""
        response = client.post(
            "/api/v1/memory/add",
            json={
                "content": "患者说了一些模糊的话",
                "layer": "verified_fact",  # v2.0 新术语
                "source": "ai_extraction",
                "confidence": 0.5,
            },
        )

        assert response.status_code == 201
        data = response.json()
        assert data["status"] == "rejected_low_confidence"
        assert data["id"] is None

    def test_add_memory_validation_error(self):
        """测试参数验证"""
        # 空内容
        response = client.post(
            "/api/v1/memory/add",
            json={
                "content": "",
                "layer": "verified_fact",  # v2.0 新术语
            },
        )
        assert response.status_code == 422

        # 无效层级
        response = client.post(
            "/api/v1/memory/add",
            json={
                "content": "测试内容",
                "layer": "invalid_layer",
            },
        )
        assert response.status_code == 422


class TestMemorySearchAPI:
    """测试 GET /api/v1/memory/search"""

    @pytest.fixture(autouse=True)
    def setup(self):
        """设置测试数据"""
        self.test_path = f".qdrant_test_api_{uuid4().hex[:8]}"
        test_search_service = SearchService(path=self.test_path)

        # 索引测试数据（v2.0 使用新术语）
        test_data = [
            {
                "id": uuid4(),
                "content": "你是王明，今年75岁",
                "layer": "identity_schema",  # v2.0 新术语（原 constitution）
                "category": "person",
            },
            {
                "id": uuid4(),
                "content": "女儿王小红，电话13800138000",
                "layer": "identity_schema",  # v2.0 新术语（原 constitution）
                "category": "person",
            },
            {
                "id": uuid4(),
                "content": "你喜欢下棋和钓鱼",
                "layer": "verified_fact",  # v2.0 新术语（原 fact）
                "category": "event",
            },
            {
                "id": uuid4(),
                "content": "今天去了公园散步",
                "layer": "event_log",  # v2.0 新术语（原 session）
                "category": "event",
            },
        ]

        for data in test_data:
            test_search_service.index_note(
                note_id=data["id"],
                content=data["content"],
                layer=data["layer"],
                category=data["category"],
                is_active=True,
            )

        # 注入测试服务
        self.original_service = get_memory_service()
        test_memory_service = MemoryService(search_service=test_search_service)

        # 替换全局单例
        import backend.services.memory as memory_module
        memory_module._memory_service = test_memory_service

        yield

        # 恢复原服务并清理
        memory_module._memory_service = self.original_service
        if os.path.exists(self.test_path):
            shutil.rmtree(self.test_path)

    def test_search_basic(self):
        """测试基本搜索"""
        response = client.get("/api/v1/memory/search", params={"q": "女儿电话"})

        assert response.status_code == 200
        data = response.json()
        assert data["count"] > 0
        assert data["query"] == "女儿电话"
        # 应该找到女儿的信息
        contents = " ".join([r["content"] for r in data["results"]])
        assert "王小红" in contents or "13800138000" in contents

    def test_search_with_layer_filter(self):
        """测试按层级过滤（v2.0 使用新术语 event_log）"""
        response = client.get(
            "/api/v1/memory/search",
            params={"q": "公园", "layer": "event_log"},  # v2.0 新术语
        )

        assert response.status_code == 200
        data = response.json()
        # 结果应该只有 event_log 层（除了可能的宪法层）
        for r in data["results"]:
            if not r["is_constitution"]:
                assert r["layer"] == "event_log"  # v2.0 新术语

    def test_search_include_constitution(self):
        """测试宪法层始终包含"""
        response = client.get(
            "/api/v1/memory/search",
            params={"q": "随便什么", "include_constitution": True},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["include_constitution"] is True

    def test_search_missing_query(self):
        """测试缺少查询参数"""
        response = client.get("/api/v1/memory/search")
        assert response.status_code == 422


class TestConstitutionAPI:
    """测试 GET /api/v1/memory/constitution"""

    def test_get_constitution_empty(self):
        """测试获取宪法层（可能为空）"""
        response = client.get("/api/v1/memory/constitution")

        assert response.status_code == 200
        data = response.json()
        assert "memories" in data
        assert "count" in data
        assert isinstance(data["memories"], list)


class TestPendingAPI:
    """测试待审批相关接口"""

    def test_get_pending_placeholder(self):
        """测试待审批列表占位接口"""
        response = client.get("/api/v1/memory/pending")

        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 0
        assert "后续版本" in data["message"]

    def test_approve_placeholder(self):
        """测试审批通过占位接口"""
        response = client.patch(f"/api/v1/memory/{uuid4()}/approve")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "approved"

    def test_reject_placeholder(self):
        """测试拒绝占位接口"""
        response = client.patch(
            f"/api/v1/memory/{uuid4()}/reject",
            params={"reason": "信息不准确"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "rejected"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
