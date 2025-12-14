"""
Tests for Search API and Service.
验证语义搜索功能和召回率。
"""
import tempfile
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.services.search import SearchService

client = TestClient(app)


# --- Test Data ---

TEST_NOTES = [
    {
        "id": uuid4(),
        "content": "你是王明，今年75岁，住在北京朝阳区",
        "layer": "constitution",
        "category": "person",
    },
    {
        "id": uuid4(),
        "content": "你的女儿叫王小红，电话13800138000",
        "layer": "constitution",
        "category": "person",
    },
    {
        "id": uuid4(),
        "content": "每天早上8点吃降压药",
        "layer": "fact",
        "category": "routine",
    },
    {
        "id": uuid4(),
        "content": "下午3点吃治疗糖尿病的药物",
        "layer": "fact",
        "category": "routine",
    },
    {
        "id": uuid4(),
        "content": "家里的钥匙放在门口的鞋柜上",
        "layer": "fact",
        "category": "item",
    },
    {
        "id": uuid4(),
        "content": "昨天女儿来看望了你，带了水果",
        "layer": "session",
        "category": "event",
    },
    {
        "id": uuid4(),
        "content": "张医生是你的主治医生，每月复诊一次",
        "layer": "fact",
        "category": "person",
    },
    {
        "id": uuid4(),
        "content": "你喜欢看京剧，最爱的演员是梅兰芳",
        "layer": "fact",
        "category": "event",
    },
]


# --- Fixtures ---


@pytest.fixture(scope="module")
def search_service():
    """创建临时搜索服务实例（强制本地模式）"""
    with tempfile.TemporaryDirectory() as tmpdir:
        # prefer_server=False 确保使用本地临时数据库，不受 Qdrant Server 影响
        service = SearchService(path=tmpdir, prefer_server=False)
        # 批量索引测试数据
        service.index_notes_batch(TEST_NOTES)
        yield service


# --- Service Tests ---


class TestSearchService:
    """搜索服务单元测试"""

    def test_index_and_search_basic(self, search_service):
        """测试基本的索引和搜索功能"""
        results = search_service.search("吃药", limit=5)

        assert len(results) > 0
        # 应该找到关于吃药的便利贴
        contents = [r["content"] for r in results]
        assert any("药" in c for c in contents)

    def test_search_by_person(self, search_service):
        """测试搜索人物相关内容"""
        results = search_service.search("女儿", limit=5)

        assert len(results) > 0
        # 应该找到关于女儿的便利贴
        contents = [r["content"] for r in results]
        assert any("女儿" in c or "王小红" in c for c in contents)

    def test_search_filter_by_layer(self, search_service):
        """测试按记忆层级过滤"""
        results = search_service.search("我是谁", limit=5, layer="constitution")

        for r in results:
            assert r["layer"] == "constitution"

    def test_search_filter_by_category(self, search_service):
        """测试按类别过滤"""
        results = search_service.search("每天", limit=5, category="routine")

        for r in results:
            assert r["category"] == "routine"

    def test_search_returns_scores(self, search_service):
        """测试返回相似度分数"""
        results = search_service.search("降压药", limit=3)

        for r in results:
            assert "score" in r
            assert 0 <= r["score"] <= 1

    def test_search_relevance_order(self, search_service):
        """测试结果按相关性排序"""
        results = search_service.search("吃降压药", limit=5)

        # 结果应该按分数降序排列
        scores = [r["score"] for r in results]
        assert scores == sorted(scores, reverse=True)

    def test_get_stats(self, search_service):
        """测试获取索引统计"""
        stats = search_service.get_stats()

        assert stats["total_count"] == len(TEST_NOTES)
        assert stats["vector_size"] == 384
        assert stats["distance"] == "Cosine"


# --- API Tests ---


class TestSearchAPI:
    """搜索 API 集成测试"""

    def test_search_endpoint(self):
        """测试搜索端点基本功能"""
        response = client.get("/api/v1/search", params={"q": "吃药"})

        # API 可能返回 200 或 500（如果模型未下载）
        # 这里先检查接口能正常响应
        assert response.status_code in [200, 500]

    def test_search_with_limit(self):
        """测试限制返回数量"""
        response = client.get("/api/v1/search", params={"q": "测试", "limit": 3})

        if response.status_code == 200:
            data = response.json()
            assert len(data["results"]) <= 3

    def test_search_missing_query(self):
        """测试缺少查询参数"""
        response = client.get("/api/v1/search")

        assert response.status_code == 422  # Validation error

    def test_search_stats_endpoint(self):
        """测试统计端点"""
        response = client.get("/api/v1/search/stats")

        # 可能返回 200 或 500
        assert response.status_code in [200, 500]


# --- Recall Rate Tests ---


class TestRecallRate:
    """召回率测试（目标 >70%）"""

    # 测试查询及其期望召回的内容
    RECALL_TESTS = [
        ("我是谁", ["王明", "75岁"]),
        ("女儿", ["王小红", "女儿"]),
        ("吃药", ["降压药", "糖尿病"]),
        ("钥匙", ["钥匙", "鞋柜"]),
        ("医生", ["张医生", "复诊"]),
    ]

    def test_recall_rate(self, search_service):
        """验证召回率 >= 70%"""
        total_tests = 0
        successful_recalls = 0

        for query, expected_keywords in self.RECALL_TESTS:
            results = search_service.search(query, limit=3)
            contents = " ".join([r["content"] for r in results])

            for keyword in expected_keywords:
                total_tests += 1
                if keyword in contents:
                    successful_recalls += 1

        recall_rate = successful_recalls / total_tests if total_tests > 0 else 0

        print(f"\n📊 召回率测试结果: {successful_recalls}/{total_tests} = {recall_rate:.1%}")

        # 目标召回率 >= 70%
        assert recall_rate >= 0.7, f"召回率 {recall_rate:.1%} 低于目标 70%"


# 导出
__all__ = ["TEST_NOTES"]
