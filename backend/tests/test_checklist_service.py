"""
Tests for ChecklistService.

Tests cover:
- Item creation and retrieval
- Briefing generation
- Plan sync functionality
- Priority and scope handling
"""

from uuid import UUID

import pytest

from backend.models.checklist import (
    ChecklistBriefingRequest,
    ChecklistItemCreate,
    ChecklistItemUpdate,
    ChecklistPriority,
    ChecklistScope,
    ChecklistStatus,
    PlanSyncRequest,
)
from backend.services.checklist_service import (
    ChecklistService,
    get_checklist_service,
    reset_checklist_service,
)


class TestChecklistService:
    """Test ChecklistService core functionality."""

    @pytest.fixture
    def service(self):
        """Create a fresh ChecklistService instance."""
        reset_checklist_service()
        return ChecklistService()

    @pytest.fixture
    def project_id(self):
        """Test project ID."""
        return "test_project_checklist"

    def test_create_item_basic(self, service, project_id):
        """Test creating a basic checklist item."""
        request = ChecklistItemCreate(
            content="Test checklist item",
            priority=ChecklistPriority.NORMAL,
            scope=ChecklistScope.PROJECT,
        )

        item = service.create_item(project_id, request)

        assert item is not None
        assert item.content == "Test checklist item"
        assert item.priority == ChecklistPriority.NORMAL
        assert item.scope == ChecklistScope.PROJECT
        assert item.status == ChecklistStatus.OPEN
        assert isinstance(item.id, UUID)

    def test_create_item_with_tags(self, service, project_id):
        """Test creating item with tags."""
        request = ChecklistItemCreate(
            content="Tagged item",
            tags=["urgent", "backend"],
        )

        item = service.create_item(project_id, request)

        assert item.tags == ["urgent", "backend"]

    def test_create_item_with_priority(self, service, project_id):
        """Test creating items with different priorities."""
        for priority in ChecklistPriority:
            request = ChecklistItemCreate(
                content=f"Priority {priority.name} item",
                priority=priority,
            )
            item = service.create_item(project_id, request)
            assert item.priority == priority

    def test_short_id_format(self, service, project_id):
        """Test short ID and ma_ref format."""
        request = ChecklistItemCreate(content="Test item")
        item = service.create_item(project_id, request)

        # short_id should be first 8 chars of UUID
        assert len(item.short_id()) == 8
        assert item.short_id() == str(item.id)[:8]

        # ma_ref should be (ma:xxxxxxxx)
        assert item.ma_ref() == f"(ma:{item.short_id()})"

    def test_collection_name_generation(self, service):
        """Test collection name sanitization."""
        # Normal project ID
        assert service._get_collection_name("my_project") == "memory_anchor_checklist_my_project"

        # Project ID with special characters
        assert service._get_collection_name("my-project.v2") == "memory_anchor_checklist_my-project_v2"

        # Chinese characters are replaced with underscores
        chinese_name = service._get_collection_name("阿默斯海默症")
        assert chinese_name.startswith("memory_anchor_checklist_")
        # 阿默斯海默症 = 6 Chinese chars → 6 underscores + 1 separator = 7 underscores total
        assert chinese_name == "memory_anchor_checklist_______"


class TestChecklistBriefing:
    """Test briefing generation."""

    @pytest.fixture
    def service(self):
        reset_checklist_service()
        return ChecklistService()

    @pytest.fixture
    def project_id(self):
        return "test_briefing_project"

    def test_empty_briefing(self, service, project_id):
        """Test briefing with no items."""
        request = ChecklistBriefingRequest(project_id=project_id)
        briefing = service.get_briefing(request)

        assert "清单简报" in briefing
        assert "没有待办清单项" in briefing

    def test_briefing_with_items(self, service, project_id):
        """Test briefing includes created items."""
        # Create items with different priorities
        service.create_item(
            project_id,
            ChecklistItemCreate(
                content="Critical task",
                priority=ChecklistPriority.CRITICAL,
            ),
        )
        service.create_item(
            project_id,
            ChecklistItemCreate(
                content="Normal task",
                priority=ChecklistPriority.NORMAL,
            ),
        )

        request = ChecklistBriefingRequest(project_id=project_id, include_ids=True)
        briefing = service.get_briefing(request)

        assert "Critical task" in briefing
        assert "Normal task" in briefing
        assert "(ma:" in briefing  # Should include IDs


class TestPlanSync:
    """Test Plan synchronization functionality."""

    @pytest.fixture
    def service(self):
        reset_checklist_service()
        return ChecklistService()

    @pytest.fixture
    def project_id(self):
        return "test_sync_project"

    def test_sync_creates_persist_items(self, service, project_id):
        """Test @persist tag creates new checklist items."""
        plan_md = """
## Tasks
- [ ] Regular task (no persist)
- [ ] Important task @persist
- [ ] Another persistent item @persist
"""
        request = PlanSyncRequest(
            project_id=project_id,
            session_id="test-session-001",
            plan_markdown=plan_md,
        )

        response = service.sync_from_plan(request)

        # Should create 2 items (those with @persist)
        assert len(response.created) == 2
        assert any("Important task" in item.content for item in response.created)
        assert any("Another persistent" in item.content for item in response.created)

    def test_sync_marks_completed(self, service, project_id):
        """Test completed items with ma:ref are marked done."""
        # First create an item
        item = service.create_item(
            project_id,
            ChecklistItemCreate(content="Existing task"),
        )
        short_id = item.short_id()

        # Simulate plan with completed item referencing our checklist
        plan_md = f"""
## Tasks
- [x] Existing task (ma:{short_id})
"""
        request = PlanSyncRequest(
            project_id=project_id,
            session_id="test-session-002",
            plan_markdown=plan_md,
        )

        response = service.sync_from_plan(request)

        # Should mark 1 item as completed
        assert short_id in response.completed


class TestItemUpdate:
    """Test item update functionality."""

    @pytest.fixture
    def service(self):
        reset_checklist_service()
        return ChecklistService()

    @pytest.fixture
    def project_id(self):
        return "test_update_project"

    def test_update_status(self, service, project_id):
        """Test updating item status."""
        item = service.create_item(
            project_id,
            ChecklistItemCreate(content="Task to complete"),
        )

        updated = service.update_item(
            project_id,
            item.id,
            ChecklistItemUpdate(status=ChecklistStatus.DONE),
        )

        assert updated is not None
        assert updated.status == ChecklistStatus.DONE
        assert updated.completed_at is not None

    def test_update_priority(self, service, project_id):
        """Test updating item priority."""
        item = service.create_item(
            project_id,
            ChecklistItemCreate(content="Task to reprioritize"),
        )

        updated = service.update_item(
            project_id,
            item.id,
            ChecklistItemUpdate(priority=ChecklistPriority.CRITICAL),
        )

        assert updated is not None
        assert updated.priority == ChecklistPriority.CRITICAL

    def test_update_nonexistent_item(self, service, project_id):
        """Test updating non-existent item returns None."""
        from uuid import uuid4

        result = service.update_item(
            project_id,
            uuid4(),  # Random UUID
            ChecklistItemUpdate(status=ChecklistStatus.DONE),
        )

        assert result is None


class TestSingleton:
    """Test singleton pattern."""

    def test_get_checklist_service_singleton(self):
        """Test that get_checklist_service returns same instance."""
        reset_checklist_service()

        service1 = get_checklist_service()
        service2 = get_checklist_service()

        assert service1 is service2

    def test_reset_checklist_service(self):
        """Test that reset creates new instance."""
        service1 = get_checklist_service()
        reset_checklist_service()
        service2 = get_checklist_service()

        assert service1 is not service2
