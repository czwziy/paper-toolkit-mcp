# paper_toolkit_mcp/tools/__init__.py
"""MCP tool registration subpackage.

Each module (search, download, manuscript, library) defines its MCP tools
at module level and exposes a ``register(mcp, ...)`` function that wires
dependencies and registers the tools with the FastMCP server instance.
"""


def register_all(
    mcp,
    *,
    storage,
    searchers: dict,
    unpaywall_resolver,
    default_save_path: str,
    default_cache_dir: str,
    ieee_searcher=None,
    acm_searcher=None,
) -> None:
    """Register all MCP tools on *mcp*.

    Called once by server.py after searcher instantiation.
    """
    from . import download, harness, library, manuscript, search

    search.register(
        mcp,
        storage=storage,
        searchers=searchers,
        ieee_searcher=ieee_searcher,
        acm_searcher=acm_searcher,
    )
    download.register(
        mcp,
        storage=storage,
        searchers=searchers,
        unpaywall_resolver=unpaywall_resolver,
        default_save_path=default_save_path,
    )
    manuscript.register(mcp, default_cache_dir=default_cache_dir, storage=storage)
    library.register(mcp, storage=storage, default_cache_dir=default_cache_dir)
    harness.register(mcp)
