"""
Pytest configuration and fixtures for backend tests.

This module ensures proper test isolation by:
1. Using a dedicated test collection name (set before any imports)
2. Resetting global singletons between tests
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
