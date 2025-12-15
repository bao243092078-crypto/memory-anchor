"""Tests for Notes API"""

from fastapi.testclient import TestClient

from backend.main import app

client = TestClient(app)


class TestHealthCheck:
    """健康检查测试"""

    def test_root(self):
        """根路径返回服务信息"""
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Memory Anchor"
        assert data["status"] == "healthy"

    def test_health_endpoint(self):
        """健康检查端点"""
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "healthy"


class TestNotesAPI:
    """便利贴 CRUD 测试"""

    def test_create_note(self):
        """创建便利贴"""
        response = client.post(
            "/api/v1/notes",
            json={"content": "下午3点吃药", "priority": 0},
        )
        assert response.status_code == 201
        data = response.json()
        assert data["content"] == "下午3点吃药"
        assert data["priority"] == 0
        assert data["layer"] == "verified_fact"  # v2.0 新术语（原 fact）
        assert data["is_active"] is True

    def test_create_constitution_note(self):
        """创建宪法层便利贴"""
        response = client.post(
            "/api/v1/notes",
            json={
                "content": "你是王明，今年75岁",
                "layer": "constitution",
                "priority": 0,
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["layer"] == "identity_schema"  # v2.0 新术语（原 constitution）

    def test_list_notes(self):
        """获取便利贴列表"""
        response = client.get("/api/v1/notes")
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    def test_list_notes_filter_by_layer(self):
        """按层级过滤便利贴"""
        response = client.get("/api/v1/notes?layer=constitution")
        assert response.status_code == 200

    def test_get_note_not_found(self):
        """获取不存在的便利贴"""
        response = client.get("/api/v1/notes/00000000-0000-0000-0000-000000000000")
        assert response.status_code == 404

    def test_update_note(self):
        """更新便利贴"""
        # 先创建
        create_response = client.post(
            "/api/v1/notes",
            json={"content": "原始内容"},
        )
        note_id = create_response.json()["id"]

        # 再更新
        update_response = client.patch(
            f"/api/v1/notes/{note_id}",
            json={"content": "更新后的内容"},
        )
        assert update_response.status_code == 200
        assert update_response.json()["content"] == "更新后的内容"

    def test_delete_note(self):
        """删除便利贴（软删除）"""
        # 先创建
        create_response = client.post(
            "/api/v1/notes",
            json={"content": "将被删除"},
        )
        note_id = create_response.json()["id"]

        # 删除
        delete_response = client.delete(f"/api/v1/notes/{note_id}")
        assert delete_response.status_code == 204

        # 验证软删除
        get_response = client.get(f"/api/v1/notes/{note_id}")
        assert get_response.json()["is_active"] is False
