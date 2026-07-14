# paper_toolkit_mcp/tools/search.py
"""Search-related MCP tools."""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import TYPE_CHECKING, Any

from .._helpers import (
    _dedupe_papers,
    _filter_by_year,
    _parse_sources,
    _simplify_for_ai,
    async_search,
)

if TYPE_CHECKING:
    from ..academic_platforms.acm import ACMSearcher
    from ..academic_platforms.ieee import IEEESearcher
    from ..storage import PaperStorage

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Module-level state — set by register()
# ---------------------------------------------------------------------------
_storage: PaperStorage | None = None
_searchers: dict[str, Any] = {}
_ieee_searcher: IEEESearcher | None = None
_acm_searcher: ACMSearcher | None = None


# ---------------------------------------------------------------------------
# Individual source search helpers (internal, called by search_papers)
# ---------------------------------------------------------------------------

async def search_arxiv(
    query: str,
    max_results: int = 10,
    sort_by: str = 'relevance',
    sort_order: str = 'descending',
) -> list[dict]:
    """Search academic papers from arXiv.

    Args:
        query: Search query string (e.g., 'machine learning').
        max_results: Maximum number of papers to return (default: 10).
        sort_by: Sort criterion — 'relevance', 'submittedDate', or 'lastUpdatedDate' (default: 'relevance').
        sort_order: Sort direction — 'descending' or 'ascending' (default: 'descending').
    Returns:
        List of paper metadata in dictionary format.
    """
    papers = await async_search(_searchers["arxiv"], query, max_results, sort_by=sort_by, sort_order=sort_order)
    return papers if papers else []


async def search_pubmed(query: str, max_results: int = 10, sort: str = 'relevance') -> list[dict]:
    """Search academic papers from PubMed.

    Args:
        query: Search query string (e.g., 'machine learning').
        max_results: Maximum number of papers to return (default: 10).
        sort: Sort order — 'relevance' or 'pub_date' (default: 'relevance').
    Returns:
        List of paper metadata in dictionary format.
    """
    papers = await async_search(_searchers["pubmed"], query, max_results, sort=sort)
    return papers if papers else []


async def search_medrxiv(query: str, max_results: int = 10) -> list[dict]:
    """Search academic papers from medRxiv.

    Note: medRxiv API filters by category name within the last 30 days, not full-text
    keyword search. Use a category keyword such as 'infectious_diseases',
    'cardiovascular_medicine', 'oncology', etc.

    Args:
        query: Category name to filter by (e.g., 'infectious_diseases', 'oncology').
        max_results: Maximum number of papers to return (default: 10).
    Returns:
        List of paper metadata in dictionary format.
    """
    papers = await async_search(_searchers["medrxiv"], query, max_results)
    return papers if papers else []


async def search_semantic(query: str, year: str | None = None, max_results: int = 10) -> list[dict]:
    """Search academic papers from Semantic Scholar.

    Args:
        query: Search query string (e.g., 'machine learning').
        year: Optional year filter (e.g., '2019', '2016-2020', '2010-', '-2015').
        max_results: Maximum number of papers to return (default: 10).
    Returns:
        List of paper metadata in dictionary format.
    """
    kwargs = {}
    if year is not None:
        kwargs['year'] = year
    papers = await async_search(_searchers["semantic"], query, max_results, **kwargs)
    return papers if papers else []


async def search_crossref(
    query: str,
    max_results: int = 10,
    filter: str | None = None,
    sort: str | None = None,
    order: str | None = None,
) -> list[dict]:
    """Search academic papers from CrossRef database.

    CrossRef is a scholarly infrastructure organization that provides
    persistent identifiers (DOIs) for scholarly content and metadata.

    Args:
        query: Search query string (e.g., 'machine learning', 'climate change').
        max_results: Maximum number of papers to return (default: 10, max: 1000).
        filter: CrossRef filter string (e.g., 'has-full-text:true,from-pub-date:2020').
        sort: Sort field ('relevance', 'published', 'updated', 'deposited', etc.).
        order: Sort order ('asc' or 'desc').
    Returns:
        List of paper metadata in dictionary format.
    """
    extra = {k: v for k, v in {'filter': filter, 'sort': sort, 'order': order}.items() if v is not None}
    papers = await async_search(_searchers["crossref"], query, max_results, **extra)
    return papers if papers else []


async def get_paper_by_doi(doi: str) -> dict:
    """Get paper metadata by DOI with multi-source fallback.

    Tries CrossRef first (richest metadata), then Semantic Scholar
    (best abstract coverage) to backfill missing abstract.
    Only saves to local library when an abstract is available.

    Args:
        doi: Digital Object Identifier (e.g., '10.1038/nature12373').
    Returns:
        Paper metadata dict. Empty dict if not found at all.
    """
    assert _storage is not None, "register() not called"

    # Step 1: CrossRef (richest structured metadata)
    paper = await asyncio.to_thread(_searchers["crossref"].get_paper_by_doi, doi)
    paper_dict: dict[str, Any] = paper.to_dict() if paper else {}

    # Step 2: If abstract missing, try Semantic Scholar
    if paper_dict and not (paper_dict.get("abstract") or "").strip():
        sem_paper = await asyncio.to_thread(
            _searchers["semantic"].get_paper_details, f"DOI:{doi}"
        )
        if sem_paper:
            sem_dict = sem_paper.to_dict()
            if (sem_dict.get("abstract") or "").strip():
                paper_dict["abstract"] = sem_dict["abstract"]
                logger.info("Backfilled abstract for %s via Semantic Scholar", doi)

    # Step 3: Only persist when abstract is present
    if paper_dict and (paper_dict.get("abstract") or "").strip():
        _storage.upsert_papers([paper_dict])
    elif paper_dict:
        logger.warning("Skipping storage for %s: no abstract available", doi)

    return paper_dict


# Backward compat alias
get_crossref_paper_by_doi = get_paper_by_doi


async def search_openalex(query: str, max_results: int = 10) -> list[dict]:
    """Search academic papers from OpenAlex.

    Args:
        query: Search query string (e.g., 'machine learning').
        max_results: Maximum number of papers to return (default: 10).
    Returns:
        List of paper metadata in dictionary format.
    """
    papers = await async_search(_searchers["openalex"], query, max_results)
    return papers if papers else []


async def search_pmc(query: str, max_results: int = 10) -> list[dict]:
    """Search academic papers from PubMed Central (PMC).

    Args:
        query: Search query string (e.g., 'machine learning').
        max_results: Maximum number of papers to return (default: 10).
    Returns:
        List of paper metadata in dictionary format.
    """
    papers = await async_search(_searchers["pmc"], query, max_results)
    return papers if papers else []


async def search_dblp(query: str, max_results: int = 10) -> list[dict]:
    """Search academic papers from dblp computer science bibliography.

    Args:
        query: Search query string (e.g., 'machine learning').
        max_results: Maximum number of papers to return (default: 10).
    Returns:
        List of paper metadata in dictionary format.
    """
    papers = await async_search(_searchers["dblp"], query, max_results)
    return papers if papers else []


# ---------------------------------------------------------------------------
# Unified search MCP tool
# ---------------------------------------------------------------------------

async def search_papers(
    query: str,
    max_results_per_source: int = 5,
    sources: str = "all",
    year_from: int | None = None,
    year_to: int | None = None,
) -> dict[str, Any]:
    """Unified top-level search across all configured academic platforms.

    Returns only cite_key + title + abstract + year + source for each paper.
    Papers without abstract are discarded. Defaults to last 5 years.

    Args:
        query: Search query string.
        max_results_per_source: Max results to fetch from each selected source.
        sources: Source names, preset group, or 'all'.
            Groups: medical (pubmed,pmc,medrxiv), cs (arxiv,dblp,semantic),
            metadata (crossref,openalex). Or comma-separated individual names.
        year_from: Earliest publication year (default: current year - 5).
            Pass 0 to disable year filtering.
        year_to: Latest publication year (default: none).
    Returns:
        Aggregated dict with per-source stats, errors, and simplified papers.
    """
    if year_from is None:
        year_from = datetime.now().year - 5
    elif year_from == 0:
        year_from = None

    selected_sources = _parse_sources(sources)

    if not selected_sources:
        return {
            "query": query,
            "sources_requested": sources,
            "sources_used": [],
            "source_results": {},
            "errors": {"sources": "No valid sources selected."},
            "papers": [],
            "total": 0,
        }

    task_map = {}
    for source in selected_sources:
        if source == "arxiv":
            task_map[source] = search_arxiv(query, max_results_per_source)
        elif source == "pubmed":
            task_map[source] = search_pubmed(query, max_results_per_source)
        elif source == "medrxiv":
            task_map[source] = search_medrxiv(query, max_results_per_source)
        elif source == "semantic":
            task_map[source] = search_semantic(query, max_results=max_results_per_source)
        elif source == "crossref":
            task_map[source] = search_crossref(query, max_results=max_results_per_source)
        elif source == "openalex":
            task_map[source] = search_openalex(query, max_results_per_source)
        elif source == "pmc":
            task_map[source] = search_pmc(query, max_results_per_source)
        elif source == "dblp":
            task_map[source] = search_dblp(query, max_results_per_source)
        elif source == "ieee":
            if _ieee_searcher is not None:
                task_map[source] = async_search(_ieee_searcher, query, max_results_per_source)
        elif source == "acm":
            if _acm_searcher is not None:
                task_map[source] = async_search(_acm_searcher, query, max_results_per_source)

    source_names = list(task_map.keys())
    source_outputs = await asyncio.gather(*task_map.values(), return_exceptions=True)

    source_results: dict[str, int] = {}
    errors: dict[str, str] = {}
    merged_papers: list[dict[str, Any]] = []

    for source_name, output in zip(source_names, source_outputs, strict=False):
        if isinstance(output, BaseException):
            errors[source_name] = str(output)
            source_results[source_name] = 0
            continue

        papers_list: list[dict[str, Any]] = output
        source_results[source_name] = len(papers_list)
        for paper in papers_list:
            if not paper.get("source"):
                paper["source"] = source_name
            merged_papers.append(paper)

    # Year filter (post-hoc, uniform across all sources)
    merged_papers = _filter_by_year(merged_papers, year_from, year_to)

    deduped_papers = _dedupe_papers(merged_papers, _storage)

    # Simplify for AI: only cite_key + title + abstract + year + source
    simplified = [_simplify_for_ai(p) for p in deduped_papers]

    return {
        "query": query,
        "sources_requested": sources,
        "sources_used": source_names,
        "source_results": source_results,
        "errors": errors,
        "papers": simplified,
        "total": len(simplified),
    }


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

def register(mcp, *, storage, searchers: dict, ieee_searcher=None, acm_searcher=None):
    """Register search tools on the MCP server."""
    global _storage, _searchers, _ieee_searcher, _acm_searcher
    _storage = storage
    _searchers = searchers
    _ieee_searcher = ieee_searcher
    _acm_searcher = acm_searcher

    mcp.tool()(search_papers)
    mcp.tool()(get_paper_by_doi)
