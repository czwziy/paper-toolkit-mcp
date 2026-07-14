# paper_toolkit_mcp/tools/library.py
"""Library and cache MCP tools."""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ..storage import PaperStorage

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Module-level state — set by register()
# ---------------------------------------------------------------------------
_storage: PaperStorage | None = None
_default_cache_dir = ""


# ---------------------------------------------------------------------------
# MCP tools
# ---------------------------------------------------------------------------

async def cache_clear() -> dict[str, Any]:
    """Clear all cached search results.

    Returns:
        Dict with number of cleared entries.
    """
    from ..cache import SearchCache

    cache = SearchCache(cache_dir=_default_cache_dir)
    count = cache.clear()
    return {
        "status": "cleared",
        "entries_cleared": count,
    }


async def library_search(
    keyword: str, limit: int = 50
) -> list[dict[str, Any]]:
    """Search the local paper library (SQLite) by keyword.

    Searches across title, authors, and abstract of all previously fetched
    papers. This is an offline operation — no network calls are made.

    Args:
        keyword: Search keyword (matched against title/authors/abstract).
        limit: Maximum number of results to return (default: 50).
    Returns:
        List of matching paper records from the local library.
    """
    assert _storage is not None, "register() not called"
    return _storage.search_local(keyword, limit=limit)


async def library_stats() -> dict[str, Any]:
    """Get statistics about the local paper library.

    Returns:
        Dict with total paper count, counts by source, PDF/fulltext coverage,
        and the database file path.
    """
    assert _storage is not None, "register() not called"
    return _storage.get_stats()


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

def register(mcp, *, storage, default_cache_dir: str):
    """Register library/cache tools on the MCP server."""
    global _storage, _default_cache_dir
    _storage = storage
    _default_cache_dir = default_cache_dir

    mcp.tool()(cache_clear)
    mcp.tool()(library_search)
    mcp.tool()(library_stats)
