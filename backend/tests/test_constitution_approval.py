import pytest
from httpx import ASGITransport, AsyncClient

from backend.main import app
from backend.services import constitution as constitution_module
from backend.services import memory as memory_module
from backend.services import search as search_module


@pytest.fixture
async def async_client(monkeypatch, tmp_path):
    """Provide an AsyncClient with isolated in-memory backends."""
    # Use cheap deterministic embeddings to avoid downloading models.
    def fake_embed_text(_: str):
        return [0.1] * search_module.VECTOR_SIZE

    def fake_embed_batch(texts):
        return [[0.1] * search_module.VECTOR_SIZE for _ in texts]

    monkeypatch.setattr(search_module, "embed_text", fake_embed_text)
    monkeypatch.setattr(search_module, "embed_batch", fake_embed_batch)

    # Isolate Qdrant (in-memory) and constitution DB.
    monkeypatch.setattr(
        constitution_module,
        "DB_PATH",
        tmp_path / "constitution_changes.db",
    )
    search_instance = search_module.SearchService(path=":memory:")
    monkeypatch.setattr(search_module, "_search_service", search_instance, raising=False)
    monkeypatch.setattr(constitution_module, "_constitution_service", None, raising=False)

    # Ensure memory service uses the same search backend.
    memory_instance = memory_module.MemoryService(search_service=search_instance)
    monkeypatch.setattr(memory_module, "_memory_service", memory_instance, raising=False)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


@pytest.mark.asyncio
async def test_constitution_proposal_and_approval_flow(async_client):
    proposed_content = "宪法层：患者叫李雷，现居杭州，紧急联系人韩梅梅。"

    # 1) 提议宪法变更
    propose_resp = await async_client.post(
        "/api/v1/constitution/propose",
        json={
            "change_type": "create",
            "proposed_content": proposed_content,
            "reason": "回归测试写入宪法层",
            "category": "person",
        },
    )

    assert propose_resp.status_code == 201
    proposed = propose_resp.json()
    change_id = proposed["id"]
    assert proposed["status"] == "pending"

    # 2) 连续三次审批
    approve_url = f"/api/v1/constitution/approve/{change_id}"
    latest = None

    for idx in range(3):
        approve_resp = await async_client.post(
            approve_url,
            json={"approver": f"reviewer-{idx + 1}", "comment": "looks good"},
        )
        assert approve_resp.status_code == 200
        latest = approve_resp.json()
        assert latest["approvals_count"] == idx + 1

    assert latest is not None
    assert latest["status"] == "applied"
    assert latest["applied_at"] is not None

    # 3) search_memory 能检索到新宪法层内容
    search_resp = await async_client.get(
        "/api/v1/memory/search",
        params={"q": "宪法层", "limit": 5},
    )

    assert search_resp.status_code == 200
    results = search_resp.json()["results"]
    assert any(
        r["content"] == proposed_content and r["layer"] == "identity_schema"  # v2.0 新术语
        for r in results
    )
