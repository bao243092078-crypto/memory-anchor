"""
Day 7 检索质量测试 - 10个测试场景
基于 docs/MEMORY_STRATEGY.md 定义的测试用例

测试目标：
1. 宪法层始终返回（无论查询内容）
2. 同义词理解（"女儿"="闺女"="女孩"）
3. 语义理解（"吃药时间"能匹配"早餐后服用阿司匹林"）
4. 层级过滤正确
5. 置信度分级处理正确
"""

import sys
from uuid import uuid4

import pytest

sys.path.insert(0, "/Users/baobao/projects/阿默斯海默症")


class TestRetrievalQuality:
    """检索质量测试套件"""

    @pytest.fixture(autouse=True)
    def setup(self, test_qdrant_path):
        """每个测试前初始化

        显式使用 test_qdrant_path 确保测试隔离。
        """
        from backend.services.search import SearchService
        self.search = SearchService(path=str(test_qdrant_path))
        # 清理测试数据
        self._cleanup_test_data()
        # 添加测试数据
        self._add_test_data()
        yield
        # 测试后清理并关闭客户端
        self._cleanup_test_data()
        # 关闭 Qdrant 客户端释放锁
        if hasattr(self.search.client, 'close'):
            self.search.client.close()
        del self.search

    def _cleanup_test_data(self):
        """清理测试数据"""
        try:
            # 删除整个 collection 重建
            collection_name = self.search.collection_name
            collections = self.search.client.get_collections().collections
            if any(c.name == collection_name for c in collections):
                self.search.client.delete_collection(collection_name)
            self.search._ensure_collection()
        except Exception as e:
            print(f"Cleanup error: {e}")

    def _add_test_data(self):
        """添加测试数据 - 模拟患者王建国的记忆"""
        test_notes = [
            # === 宪法层（核心身份）===
            {
                "id": uuid4(),
                "content": "我叫王建国，今年78岁，住在北京市朝阳区幸福里小区3号楼501室",
                "layer": "constitution",
                "category": "person",
            },
            {
                "id": uuid4(),
                "content": "女儿王小红，电话13800138000，每周日下午来探望",
                "layer": "constitution",
                "category": "person",
            },
            {
                "id": uuid4(),
                "content": "儿子王小明，在上海工作，电话13900139000",
                "layer": "constitution",
                "category": "person",
            },
            {
                "id": uuid4(),
                "content": "对青霉素过敏，严禁使用",
                "layer": "constitution",
                "category": "routine",
            },
            {
                "id": uuid4(),
                "content": "每天早餐后服用阿司匹林100mg和降压药",
                "layer": "constitution",
                "category": "routine",
            },

            # === 事实层（长期记忆）===
            {
                "id": uuid4(),
                "content": "2024年国庆节全家人一起去天安门看升旗，女儿拍了很多照片",
                "layer": "fact",
                "category": "event",
            },
            {
                "id": uuid4(),
                "content": "老伴李秀英2020年去世，葬在八宝山公墓",
                "layer": "fact",
                "category": "person",
            },
            {
                "id": uuid4(),
                "content": "年轻时在首钢工作，是高级工程师，1998年退休",
                "layer": "fact",
                "category": "event",
            },
            {
                "id": uuid4(),
                "content": "最喜欢吃女儿做的红烧肉，每次来都要做",
                "layer": "fact",
                "category": "item",
            },
            {
                "id": uuid4(),
                "content": "楼下的张阿姨是老朋友，经常一起下棋",
                "layer": "fact",
                "category": "person",
            },

            # === 会话层（短期记忆）===
            {
                "id": uuid4(),
                "content": "今天上午女儿打电话说周日要带外孙女一起来",
                "layer": "session",
                "category": "event",
            },
            {
                "id": uuid4(),
                "content": "下午3点要去社区医院做血压检查",
                "layer": "session",
                "category": "routine",
            },
            {
                "id": uuid4(),
                "content": "晚上要看CCTV4的新闻联播",
                "layer": "session",
                "category": "routine",
            },
        ]

        self.search.index_notes_batch(test_notes)
        self.test_notes = test_notes
        print(f"Added {len(test_notes)} test notes")

    # ==================== 10个测试场景 ====================

    def test_01_constitution_always_returns(self):
        """测试1: 宪法层始终返回（无论查询什么）"""
        # 查询一个完全无关的内容
        results = self.search.search("今天天气怎么样", limit=10, layer="constitution")

        # 应该返回宪法层内容（基于语义相似度排序）
        assert len(results) > 0, "宪法层应该有结果"
        for r in results:
            assert r["layer"] == "constitution", f"应该只返回宪法层，但返回了 {r['layer']}"

    def test_02_synonym_understanding_daughter(self):
        """测试2: 同义词理解 - 闺女能找到女儿"""
        results = self.search.search("闺女电话是多少", limit=5)

        # 应该找到女儿相关的记录
        found_daughter = any("女儿" in r["content"] or "王小红" in r["content"] for r in results)
        assert found_daughter, f"应该找到女儿相关信息，但结果是: {results}"

    def test_03_semantic_understanding_medicine(self):
        """测试3: 语义理解 - 吃药时间匹配早餐后服用"""
        results = self.search.search("什么时候吃药", limit=5)

        # 应该找到用药相关的记录
        found_medicine = any("阿司匹林" in r["content"] or "服用" in r["content"] for r in results)
        assert found_medicine, f"应该找到用药信息，但结果是: {results}"

    def test_04_layer_filter_fact_only(self):
        """测试4: 层级过滤 - 只查询事实层"""
        results = self.search.search("家人", limit=10, layer="fact")

        for r in results:
            assert r["layer"] == "fact", f"过滤事实层时返回了 {r['layer']}"

    def test_05_layer_filter_session_only(self):
        """测试5: 层级过滤 - 只查询会话层"""
        results = self.search.search("今天", limit=10, layer="session")

        for r in results:
            assert r["layer"] == "session", f"过滤会话层时返回了 {r['layer']}"

    def test_06_category_filter_person(self):
        """测试6: 类别过滤 - 只查询人物"""
        results = self.search.search("联系方式", limit=10, category="person")

        for r in results:
            assert r["category"] == "person", f"过滤人物类别时返回了 {r['category']}"

    def test_07_allergy_information(self):
        """测试7: 关键医疗信息 - 过敏信息"""
        results = self.search.search("过敏", limit=5)

        found_allergy = any("青霉素" in r["content"] for r in results)
        assert found_allergy, "应该找到过敏信息"

    def test_08_family_relationship(self):
        """测试8: 家庭关系 - 查询儿子信息"""
        results = self.search.search("儿子在哪里工作", limit=5)

        found_son = any("王小明" in r["content"] or "上海" in r["content"] for r in results)
        assert found_son, f"应该找到儿子信息，但结果是: {results}"

    def test_09_past_event(self):
        """测试9: 过去事件 - 工作经历"""
        results = self.search.search("以前在哪里工作", limit=5)

        found_work = any("首钢" in r["content"] or "工程师" in r["content"] for r in results)
        assert found_work, f"应该找到工作经历，但结果是: {results}"

    def test_10_today_schedule(self):
        """测试10: 今日安排"""
        results = self.search.search("今天要做什么", limit=5, layer="session")

        # 会话层应该有今日安排
        assert len(results) > 0, "会话层应该有今日安排"
        for r in results:
            assert r["layer"] == "session"


class TestSearchServiceBasic:
    """搜索服务基础功能测试"""

    @pytest.fixture(autouse=True)
    def setup(self, test_qdrant_path):
        """显式使用 test_qdrant_path 确保测试隔离"""
        from backend.services.search import SearchService
        self.search = SearchService(path=str(test_qdrant_path))
        yield
        # 关闭 Qdrant 客户端释放锁
        if hasattr(self.search.client, 'close'):
            self.search.client.close()
        del self.search

    def test_connection_mode(self):
        """测试连接模式"""
        print(f"Current mode: {self.search.mode}")
        assert self.search.mode in ["server", "local"]

    def test_collection_exists(self):
        """测试 collection 存在"""
        collections = self.search.client.get_collections().collections
        names = [c.name for c in collections]
        assert self.search.collection_name in names

    def test_get_stats(self):
        """测试获取统计信息"""
        stats = self.search.get_stats()
        assert "total_count" in stats
        assert "vector_size" in stats
        print(f"Stats: {stats}")


if __name__ == "__main__":
    # 直接运行测试
    pytest.main([__file__, "-v", "--tb=short"])
