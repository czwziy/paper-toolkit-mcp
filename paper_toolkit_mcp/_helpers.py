# paper_toolkit_mcp/_helpers.py
"""Pure helper functions and constants for paper search aggregation.

This module is part of the entry layer — it contains stateless utility
functions shared by server.py and the tools/ subpackage.
"""
import asyncio
import json
import logging
import re
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Source configuration
# ---------------------------------------------------------------------------
# Mutable list — server.py may append "ieee" / "acm" at import time.
ALL_SOURCES: list[str] = [
    "arxiv",
    "pubmed",
    "medrxiv",
    "semantic",
    "crossref",
    "openalex",
    "pmc",
    "dblp",
]

# Preset source groups — AI can pass "medical" / "cs" / "metadata" instead of
# listing individual sources. Resolved by _parse_sources.
SOURCE_GROUPS: dict[str, list[str]] = {
    "all": ALL_SOURCES,
    "medical": ["pubmed", "pmc", "medrxiv"],
    "cs": ["arxiv", "dblp", "semantic"],
    "metadata": ["crossref", "openalex"],
}


# ---------------------------------------------------------------------------
# Async search adapter
# ---------------------------------------------------------------------------
# Runs blocking requests-based calls in a thread pool to avoid blocking the
# event loop.
async def async_search(searcher, query: str, max_results: int, **kwargs) -> list[dict]:
    if 'year' in kwargs:
        papers = await asyncio.to_thread(searcher.search, query, max_results=max_results, year=kwargs['year'])
    elif kwargs:
        papers = await asyncio.to_thread(searcher.search, query, max_results=max_results, **kwargs)
    else:
        papers = await asyncio.to_thread(searcher.search, query, max_results=max_results)
    return [paper.to_dict() for paper in papers]


# ---------------------------------------------------------------------------
# Source parsing
# ---------------------------------------------------------------------------

def _parse_sources(sources: str) -> list[str]:
    if not sources or sources.strip().lower() == "all":
        return ALL_SOURCES

    normalized = sources.strip().lower()
    # Check if it's a preset group name
    if normalized in SOURCE_GROUPS:
        return [s for s in SOURCE_GROUPS[normalized] if s in ALL_SOURCES]

    # Otherwise treat as comma-separated list
    parts = [part.strip().lower() for part in sources.split(",") if part.strip()]
    # Expand any group names within the comma list
    expanded: list[str] = []
    for part in parts:
        if part in SOURCE_GROUPS:
            expanded.extend(SOURCE_GROUPS[part])
        else:
            expanded.append(part)
    # Dedupe while preserving order, filter to valid sources
    seen: set[str] = set()
    result: list[str] = []
    for s in expanded:
        if s in ALL_SOURCES and s not in seen:
            seen.add(s)
            result.append(s)
    return result


# ---------------------------------------------------------------------------
# Paper filtering & simplification
# ---------------------------------------------------------------------------

def _filter_by_year(
    papers: list[dict[str, Any]],
    year_from: int | None = None,
    year_to: int | None = None,
) -> list[dict[str, Any]]:
    """Filter papers by publication year (post-hoc, works for all sources)."""
    if not year_from and not year_to:
        return papers
    result: list[dict[str, Any]] = []
    for p in papers:
        date_str = (p.get("published_date") or "").strip()
        if not date_str:
            continue
        try:
            year = int(date_str[:4])
        except (ValueError, IndexError):
            continue
        if year_from and year < year_from:
            continue
        if year_to and year > year_to:
            continue
        result.append(p)
    return result


def _simplify_for_ai(paper: dict[str, Any]) -> dict[str, Any]:
    """Return only the fields AI needs for writing: cite_key + abstract + title + year + source.

    DOI, paper_id, PDF URL etc. stay in the database — AI never sees them.
    """
    date_str = (paper.get("published_date") or "").strip()
    year: int | str = ""
    if date_str:
        try:
            year = int(date_str[:4])
        except (ValueError, IndexError):
            pass
    return {
        "cite_key": paper.get("cite_key", ""),
        "title": paper.get("title", ""),
        "abstract": (paper.get("abstract") or "").strip(),
        "year": year,
        "source": paper.get("source", ""),
    }


# ---------------------------------------------------------------------------
# Paper merging utilities
# ---------------------------------------------------------------------------

def _merge_json_list(old_json: str, new_json: str) -> str:
    """Merge two JSON-encoded lists, deduplicating while preserving order."""
    try:
        old_list = json.loads(old_json) if old_json else []
    except (json.JSONDecodeError, TypeError):
        old_list = []
    try:
        new_list = json.loads(new_json) if new_json else []
    except (json.JSONDecodeError, TypeError):
        new_list = []
    if not isinstance(old_list, list):
        old_list = []
    if not isinstance(new_list, list):
        new_list = []
    combined = list(dict.fromkeys(old_list + new_list))
    return json.dumps(combined, ensure_ascii=False)


def _merge_json_dict(old_json: str, new_json: str) -> str:
    """Merge two JSON-encoded dicts (new overrides old for same keys)."""
    try:
        old_dict = json.loads(old_json) if old_json else {}
    except (json.JSONDecodeError, TypeError):
        old_dict = {}
    try:
        new_dict = json.loads(new_json) if new_json else {}
    except (json.JSONDecodeError, TypeError):
        new_dict = {}
    if not isinstance(old_dict, dict):
        old_dict = {}
    if not isinstance(new_dict, dict):
        new_dict = {}
    merged = {**old_dict, **new_dict}
    return json.dumps(merged, ensure_ascii=False)


# Fields stored as JSON arrays (authors/categories/keywords/references)
_JSON_LIST_FIELDS = ("authors", "categories", "keywords", "references")
# Fields stored as JSON objects (extra)
_JSON_DICT_FIELDS = ("extra",)
# Plain string fields merged with "first non-empty wins" semantics
_STRING_MERGE_FIELDS = (
    "doi", "paper_id", "title", "abstract", "published_date",
    "pdf_url", "url", "updated_date",
)


def _merge_papers(existing: dict[str, Any], new: dict[str, Any]) -> None:
    """Merge ``new`` into ``existing`` in place, combining complementary fields.

    - JSON list fields: parsed, concatenated, deduplicated, re-serialized
    - JSON dict fields: parsed, merged (new overrides old), re-serialized
    - String fields: first non-empty value wins (empty never overwrites non-empty)
    - source: accumulated as comma-separated set (membership checked exactly)
    """
    for field in _JSON_LIST_FIELDS:
        new_val = new.get(field)
        if not new_val or new_val in ("[]", '""'):
            continue
        old_val = existing.get(field)
        if not old_val or old_val == "[]":
            existing[field] = new_val
        else:
            existing[field] = _merge_json_list(old_val, new_val)

    for field in _JSON_DICT_FIELDS:
        new_val = new.get(field)
        if not new_val or new_val == "{}":
            continue
        old_val = existing.get(field)
        if not old_val or old_val == "{}":
            existing[field] = new_val
        else:
            existing[field] = _merge_json_dict(old_val, new_val)

    for field in _STRING_MERGE_FIELDS:
        new_val = new.get(field)
        if not new_val:
            continue
        old_val = existing.get(field)
        if not old_val:
            existing[field] = new_val

    # source: accumulate via set membership (not substring)
    new_src = (new.get("source") or "").strip()
    if new_src:
        existing_sources = {s.strip() for s in (existing.get("source") or "").split(",") if s.strip()}
        if new_src not in existing_sources:
            existing_sources.add(new_src)
            existing["source"] = ",".join(sorted(existing_sources))


def _dedupe_papers(papers: list[dict[str, Any]], storage=None) -> list[dict[str, Any]]:
    """Merge duplicate papers by DOI/title/id, combining complementary fields.

    Papers without abstract are discarded (not stored, not returned).
    When the same paper appears from multiple sources (e.g. arXiv has PDF,
    CrossRef has journal info), the fields are merged instead of discarding
    duplicates. Results are then upserted into the SQLite storage for
    cross-session lookup (if *storage* is provided).
    """
    from .storage import _paper_dedup_key

    merged: dict[str, dict[str, Any]] = {}

    for paper in papers:
        key = _paper_dedup_key(paper)
        if key not in merged:
            merged[key] = dict(paper)
            continue
        _merge_papers(merged[key], paper)

    deduped = list(merged.values())

    # Discard papers without abstract — they're useless for AI writing
    deduped = [p for p in deduped if (p.get("abstract") or "").strip()]

    if storage is not None:
        try:
            storage.upsert_papers(deduped)
        except Exception as exc:
            logger.warning("Failed to upsert papers into storage: %s", exc)

    return deduped


def _safe_filename(filename_hint: str, default: str = "paper") -> str:
    safe = re.sub(r"[^a-zA-Z0-9._-]+", "_", filename_hint).strip("._")
    if not safe:
        return default
    return safe[:120]
