"""API routes for Memory Anchor"""

from backend.api.constitution import router as constitution_router
from backend.api.notes import router as notes_router
from backend.api.search import router as search_router

__all__ = ["notes_router", "search_router", "constitution_router"]
