"""
Pytest configuration and fixtures for backend tests.

This module ensures proper test isolation by:
1. Using a dedicated test collection name
2. Resetting global singletons between tests
"""

import os
import pytest

# Set test collection name BEFORE any imports
# This must be done before importing any backend modules
TEST_COLLECTION_NAME = "memory_anchor_test_notes"


@pytest.fixture(scope="session", autouse=True)
def set_test_collection():
    """Set test collection name for the entire test session."""
    os.environ["MEMORY_ANCHOR_COLLECTION"] = TEST_COLLECTION_NAME
    yield
    # Cleanup: delete test collection after all tests
    try:
        from backend.services.search import SearchService
        s = SearchService()
        collections = s.client.get_collections().collections
        if any(c.name == TEST_COLLECTION_NAME for c in collections):
            s.client.delete_collection(TEST_COLLECTION_NAME)
    except Exception:
        pass


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
