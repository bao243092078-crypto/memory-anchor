"""
Pytest configuration and fixtures for backend tests.

This module ensures proper test isolation by:
1. Using a dedicated test collection name (set before any imports)
2. Resetting global singletons between tests
3. Configuring Qdrant local mode for tests
"""

import os

import pytest

# Set test collection name BEFORE any imports happen
# This is critical - must be done at module level, before pytest_configure
TEST_COLLECTION_NAME = "memory_anchor_test_notes"
os.environ["MEMORY_ANCHOR_COLLECTION"] = TEST_COLLECTION_NAME


def pytest_configure(config):
    """Set up test environment before any tests are collected."""
    # Ensure test collection is set (redundant but safe)
    os.environ["MEMORY_ANCHOR_COLLECTION"] = TEST_COLLECTION_NAME

    # Clear QDRANT_URL to force local mode for all tests
    # This prevents accidental connections to Qdrant Server
    if "QDRANT_URL" in os.environ:
        del os.environ["QDRANT_URL"]


@pytest.fixture(scope="session", autouse=True)
def cleanup_test_collection():
    """Clean up test collection after all tests."""
    yield
    # Cleanup: delete test collection after all tests
    try:
        # Reset singletons first to ensure fresh instances
        _reset_all_singletons()
        from backend.services.search import SearchService
        s = SearchService()
        # Only delete if it's the test collection
        if s.collection_name == TEST_COLLECTION_NAME:
            collections = s.client.get_collections().collections
            if any(c.name == TEST_COLLECTION_NAME for c in collections):
                s.client.delete_collection(TEST_COLLECTION_NAME)
    except Exception:
        pass


@pytest.fixture(scope="session")
def test_qdrant_path(tmp_path_factory):
    """Provide a session-wide temporary Qdrant path for all tests."""
    return str(tmp_path_factory.mktemp("qdrant"))


@pytest.fixture(autouse=True)
def configure_test_qdrant(test_qdrant_path, monkeypatch):
    """Configure Qdrant local mode for tests by monkeypatching SearchService.

    This ensures all tests use local Qdrant storage instead of requiring
    a Qdrant server or QDRANT_URL environment variable.
    """
    # Clear QDRANT_URL at test level (double insurance)
    monkeypatch.delenv("QDRANT_URL", raising=False)

    from backend.services import search as search_module

    # Store original SearchService class
    OriginalSearchService = search_module.SearchService

    # Create wrapper that injects path parameter
    class TestSearchService(OriginalSearchService):
        def __init__(self, path=None, url=None, prefer_server=True):
            # If no path or url provided, use test path for local mode
            if path is None and url is None:
                path = test_qdrant_path
            super().__init__(path=path, url=url, prefer_server=prefer_server)

    # Monkeypatch the SearchService class
    monkeypatch.setattr(search_module, "SearchService", TestSearchService)

    # Also reset config to ensure clean state
    from backend.config import reset_config
    reset_config()

    yield

    # Restore original SearchService (though reset_singletons handles this)
    monkeypatch.setattr(search_module, "SearchService", OriginalSearchService)


@pytest.fixture(autouse=True)
def reset_singletons():
    """Reset all global singletons before each test to ensure fresh instances."""
    # Reset singletons before test
    _reset_all_singletons()

    yield

    # Reset singletons after test
    _reset_all_singletons()


def _reset_all_singletons():
    """Reset all global singleton instances."""
    # Reset Config (P2 fix: ensure clean config state)
    try:
        from backend.config import reset_config
        reset_config()
    except (ImportError, AttributeError):
        pass

    # Reset MemoryKernel
    try:
        import backend.core.memory_kernel as mk
        mk._kernel_instance = None
    except (ImportError, AttributeError):
        pass

    # Reset SearchService
    try:
        import backend.services.search as ss
        ss._search_service = None
    except (ImportError, AttributeError):
        pass

    # Reset MemoryService
    try:
        import backend.services.memory as ms
        ms._memory_service = None
    except (ImportError, AttributeError):
        pass

    # Reset NotesService
    try:
        import backend.services.notes_service as ns
        ns._notes_service = None
    except (ImportError, AttributeError):
        pass

    # Reset ConstitutionService
    try:
        import backend.services.constitution as cs
        cs._constitution_service = None
    except (ImportError, AttributeError):
        pass

    # Reset ChecklistService
    try:
        import backend.services.checklist_service as cls
        cls._checklist_service = None
    except (ImportError, AttributeError):
        pass

    # Reset LLMProvider
    try:
        import backend.services.llm_provider as lp
        lp._provider = None
    except (ImportError, AttributeError):
        pass

    # Reset MemoryRefiner
    try:
        import backend.services.memory_refiner as mr
        mr._refiner = None
    except (ImportError, AttributeError):
        pass
