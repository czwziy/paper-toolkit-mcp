#!/usr/bin/env python3
"""CLI interface for paper-toolkit — search, download, and read academic papers."""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import shutil
import sys
from typing import Any

from .academic_platforms.arxiv import ArxivSearcher
from .academic_platforms.crossref import CrossRefSearcher
from .academic_platforms.dblp import DBLPSearcher
from .academic_platforms.medrxiv import MedRxivSearcher
from .academic_platforms.openalex import OpenAlexSearcher
from .academic_platforms.pmc import PMCSearcher
from .academic_platforms.pubmed import PubMedSearcher
from .academic_platforms.semantic import SemanticSearcher
from .config import get_env, get_work_dir
from .storage import PaperStorage, _paper_dedup_key

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Searcher registry
# ---------------------------------------------------------------------------

SEARCHERS: dict[str, Any] = {}


def _init_searchers() -> None:
    """Lazily initialize searcher instances."""
    if SEARCHERS:
        return

    SEARCHERS["arxiv"] = ArxivSearcher()
    SEARCHERS["pubmed"] = PubMedSearcher()
    SEARCHERS["medrxiv"] = MedRxivSearcher()
    SEARCHERS["semantic"] = SemanticSearcher()
    SEARCHERS["crossref"] = CrossRefSearcher()
    SEARCHERS["openalex"] = OpenAlexSearcher()
    SEARCHERS["pmc"] = PMCSearcher()
    SEARCHERS["dblp"] = DBLPSearcher()

    # Optional paid connectors
    ieee_key = get_env("IEEE_API_KEY", "")
    if ieee_key:
        from .academic_platforms.ieee import IEEESearcher
        SEARCHERS["ieee"] = IEEESearcher()

    acm_key = get_env("ACM_API_KEY", "")
    if acm_key:
        from .academic_platforms.acm import ACMSearcher
        SEARCHERS["acm"] = ACMSearcher()


ALL_SOURCES = [
    "arxiv", "pubmed", "medrxiv", "semantic", "crossref",
    "openalex", "pmc", "dblp",
]

SOURCE_GROUPS: dict[str, list[str]] = {
    "all": ALL_SOURCES,
    "medical": ["pubmed", "pmc", "medrxiv"],
    "cs": ["arxiv", "dblp", "semantic"],
    "metadata": ["crossref", "openalex"],
}


def _parse_sources(sources: str) -> list[str]:
    if not sources or sources.strip().lower() == "all":
        return [s for s in ALL_SOURCES if s in SEARCHERS]
    normalized = sources.strip().lower()
    if normalized in SOURCE_GROUPS:
        return [s for s in SOURCE_GROUPS[normalized] if s in SEARCHERS]
    parts = [p.strip().lower() for p in sources.split(",") if p.strip()]
    expanded: list[str] = []
    for part in parts:
        if part in SOURCE_GROUPS:
            expanded.extend(SOURCE_GROUPS[part])
        else:
            expanded.append(part)
    seen: set[str] = set()
    result: list[str] = []
    for s in expanded:
        if s in SEARCHERS and s not in seen:
            seen.add(s)
            result.append(s)
    return result


def _filter_by_year(
    papers: list[dict[str, Any]],
    year_from: int | None = None,
    year_to: int | None = None,
) -> list[dict[str, Any]]:
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
    """Merge ``new`` into ``existing`` in place, combining complementary fields."""
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

    new_src = (new.get("source") or "").strip()
    if new_src:
        existing_sources = {s.strip() for s in (existing.get("source") or "").split(",") if s.strip()}
        if new_src not in existing_sources:
            existing_sources.add(new_src)
            existing["source"] = ",".join(sorted(existing_sources))


def _dedupe(papers: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Merge duplicate papers, discard those without abstract, upsert to storage."""
    merged: dict[str, dict[str, Any]] = {}

    for paper in papers:
        key = _paper_dedup_key(paper)
        if key not in merged:
            merged[key] = dict(paper)
            continue
        _merge_papers(merged[key], paper)

    deduped = list(merged.values())
    deduped = [p for p in deduped if (p.get("abstract") or "").strip()]

    try:
        storage.upsert_papers(deduped)
    except Exception as exc:
        logger.warning("Failed to upsert papers into storage: %s", exc)

    return deduped


# ---------------------------------------------------------------------------
# Async helpers
# ---------------------------------------------------------------------------

# Default download directory, resolved once at import from WORK_DIR (or CWD).
# Used as the default save_path for the download / read CLI commands so files
# land inside the user's project folder regardless of the process CWD.
DEFAULT_SAVE_PATH = os.path.join(get_work_dir(), "downloads")

# Default cache directory, resolved once at import from WORK_DIR (or CWD).
# Passed explicitly to SearchCache so the cache module stays a pure leaf with
# no dependency on config (per the layered architecture contract).
DEFAULT_CACHE_DIR = os.path.join(get_work_dir(), ".paper_cache")

# Unified SQLite storage for paper metadata and local PDF path tracking.
storage = PaperStorage()

async def _async_search(searcher: Any, query: str, max_results: int, **kwargs) -> list[dict]:
    if kwargs:
        papers = await asyncio.to_thread(searcher.search, query, max_results=max_results, **kwargs)
    else:
        papers = await asyncio.to_thread(searcher.search, query, max_results=max_results)
    return [p.to_dict() for p in papers]


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

async def cmd_search(args: argparse.Namespace) -> int:
    _init_searchers()
    selected = _parse_sources(args.sources)
    if not selected:
        print(json.dumps({"error": "No valid sources selected", "available": sorted(SEARCHERS.keys())}))
        return 1

    # Default: last 5 years. year_from=0 disables.
    year_from = args.year_from
    if year_from is None:
        from datetime import datetime as _dt
        year_from = _dt.now().year - 5
    elif year_from == 0:
        year_from = None

    tasks = {}
    for src in selected:
        searcher = SEARCHERS[src]
        tasks[src] = _async_search(searcher, args.query, args.max_results)

    names = list(tasks.keys())
    results = await asyncio.gather(*tasks.values(), return_exceptions=True)

    merged: list[dict[str, Any]] = []
    errors: dict[str, str] = {}
    source_counts: dict[str, int] = {}

    for name, result in zip(names, results, strict=False):
        if isinstance(result, BaseException):
            errors[name] = str(result)
            source_counts[name] = 0
        else:
            papers_list: list[dict[str, Any]] = result
            source_counts[name] = len(papers_list)
            for p in papers_list:
                if not p.get("source"):
                    p["source"] = name
                merged.append(p)

    merged = _filter_by_year(merged, year_from, args.year_to)
    deduped = _dedupe(merged)
    simplified = [_simplify_for_ai(p) for p in deduped]

    output = {
        "query": args.query,
        "sources_used": names,
        "source_results": source_counts,
        "errors": errors,
        "total": len(simplified),
        "papers": simplified,
    }
    print(json.dumps(output, indent=2, default=str, ensure_ascii=False))
    return 0


async def cmd_download(args: argparse.Namespace) -> int:
    _init_searchers()
    source = args.source.strip().lower()

    if source not in SEARCHERS:
        print(json.dumps({"error": f"Unknown source: {source}", "available": sorted(SEARCHERS.keys())}))
        return 1

    # Check local PDF cache first.
    dedup_key = _paper_dedup_key({"doi": "", "title": "", "paper_id": args.paper_id})
    local_pdf = storage.get_local_pdf(dedup_key)
    if local_pdf:
        print(json.dumps({"status": "ok", "path": local_pdf, "cached": True}))
        return 0

    searcher = SEARCHERS[source]
    try:
        result = await asyncio.to_thread(searcher.download_pdf, args.paper_id, args.save_path)
        if isinstance(result, str) and os.path.exists(result):
            storage.set_local_pdf(dedup_key, result)
        print(json.dumps({"status": "ok", "path": result}))
        return 0
    except Exception as e:
        print(json.dumps({"status": "error", "message": str(e)}))
        return 1


async def cmd_read(args: argparse.Namespace) -> int:
    _init_searchers()
    source = args.source.strip().lower()

    if source not in SEARCHERS:
        print(json.dumps({"error": f"Unknown source: {source}", "available": sorted(SEARCHERS.keys())}))
        return 1

    searcher = SEARCHERS[source]
    try:
        text = await asyncio.to_thread(searcher.read_paper, args.paper_id, args.save_path)
        print(text)
        return 0
    except Exception as e:
        print(json.dumps({"status": "error", "message": str(e)}))
        return 1


async def cmd_download_by_key(args: argparse.Namespace) -> int:
    paper = storage.get_by_cite_key(args.cite_key.strip())
    if not paper:
        print(json.dumps({"error": f"cite_key '{args.cite_key}' not found in library"}))
        return 1

    dedup_key = paper["dedup_key"]
    local_pdf = storage.get_local_pdf(dedup_key)
    if local_pdf:
        print(json.dumps({"status": "ok", "path": local_pdf, "cached": True}))
        return 0

    _init_searchers()
    source = (paper.get("source") or "").split(",")[0].strip()
    if source not in SEARCHERS:
        print(json.dumps({"error": f"Source '{source}' not available", "paper_id": paper.get("paper_id", "")}))
        return 1

    searcher = SEARCHERS[source]
    try:
        result = await asyncio.to_thread(searcher.download_pdf, paper["paper_id"], args.save_path)
        if isinstance(result, str) and os.path.exists(result):
            storage.set_local_pdf(dedup_key, result)
        print(json.dumps({"status": "ok", "path": result}))
        return 0
    except Exception as e:
        print(json.dumps({"status": "error", "message": str(e)}))
        return 1


async def cmd_read_by_key(args: argparse.Namespace) -> int:
    paper = storage.get_by_cite_key(args.cite_key.strip())
    if not paper:
        print(json.dumps({"error": f"cite_key '{args.cite_key}' not found in library"}))
        return 1

    dedup_key = paper["dedup_key"]
    cached_text = storage.get_fulltext(dedup_key)
    if cached_text:
        print(cached_text)
        return 0

    _init_searchers()
    source = (paper.get("source") or "").split(",")[0].strip()
    if source not in SEARCHERS:
        print(json.dumps({"error": f"Source '{source}' not available"}))
        return 1

    searcher = SEARCHERS[source]
    try:
        text = await asyncio.to_thread(searcher.read_paper, paper["paper_id"], args.save_path)
        if text:
            storage.set_fulltext(dedup_key, text)
        print(text)
        return 0
    except Exception as e:
        print(json.dumps({"status": "error", "message": str(e)}))
        return 1


async def cmd_sources(args: argparse.Namespace) -> int:
    _init_searchers()
    print(json.dumps({"sources": sorted(SEARCHERS.keys())}, indent=2))
    return 0


async def cmd_manuscript(args: argparse.Namespace) -> int:
    """Process a Markdown manuscript with citation placeholders."""
    from .cache import SearchCache
    from .pandoc_helper import convert_to_docx, pandoc_available
    from .reference import (
        generate_bibtex,
        generate_reference_list,
        generate_ris,
        get_paper_by_identifier,
        parse_citation_placeholders,
        process_manuscript_text,
    )

    markdown_path = args.file
    if not os.path.exists(markdown_path):
        print(json.dumps({"error": f"File not found: {markdown_path}"}))
        return 1

    with open(markdown_path, encoding="utf-8") as f:
        markdown_content = f.read()

    cache = SearchCache(cache_dir=DEFAULT_CACHE_DIR, ttl_hours=args.cache_ttl)
    output_dir = args.output or os.path.dirname(markdown_path) or get_work_dir()
    os.makedirs(output_dir, exist_ok=True)
    base_name = os.path.splitext(os.path.basename(markdown_path))[0]

    placeholders = parse_citation_placeholders(markdown_content)
    if not placeholders:
        print(json.dumps({"status": "no_citations_found", "message": "No citation placeholders found."}))
        return 0

    unique_citations = {}
    for p in placeholders:
        key = f"{p['type']}:{p['identifier']}"
        if key not in unique_citations:
            unique_citations[key] = p

    papers = []
    failed = []

    for key, placeholder in unique_citations.items():
        try:
            paper = get_paper_by_identifier(placeholder["type"], placeholder["identifier"], cache=cache)
            if paper:
                paper["citation_key"] = key
                papers.append(paper)
            else:
                failed.append({
                    "placeholder": placeholder["full_match"],
                    "identifier": placeholder["identifier"],
                    "type": placeholder["type"],
                    "error": "Paper not found",
                })
        except Exception as e:
            failed.append({
                "placeholder": placeholder["full_match"],
                "identifier": placeholder["identifier"],
                "type": placeholder["type"],
                "error": str(e),
            })

    if not papers:
        print(json.dumps({"status": "error", "message": "No papers could be retrieved.", "failed": failed}))
        return 1

    ref_list = generate_reference_list(papers, style=args.style)
    processed = process_manuscript_text(markdown_content, papers)

    formatted_md_path = os.path.join(output_dir, f"{base_name}_formatted.md")
    with open(formatted_md_path, "w", encoding="utf-8") as f:
        f.write(processed["formatted_text"])

    ref_list_path = os.path.join(output_dir, f"{base_name}_references.txt")
    with open(ref_list_path, "w", encoding="utf-8") as f:
        f.write(f"## References\n\n{ref_list}")

    output_files = {
        "formatted_markdown": formatted_md_path,
        "reference_list": ref_list_path,
    }

    if args.generate_bib:
        bib_content = generate_bibtex(papers)
        bib_path = os.path.join(output_dir, "refs.bib")
        with open(bib_path, "w", encoding="utf-8") as f:
            f.write(bib_content)
        output_files["bibtex"] = bib_path

    if args.generate_ris:
        ris_content = generate_ris(papers)
        ris_path = os.path.join(output_dir, "refs.ris")
        with open(ris_path, "w", encoding="utf-8") as f:
            f.write(ris_content)
        output_files["ris"] = ris_path

    if args.generate_docx:
        if pandoc_available():
            try:
                csl_file = None
                csl_dir = os.path.join(os.path.dirname(__file__), "..", "csl")
                style_to_csl = {
                    "gb7714": "chinese-gb7714-2015-numeric.csl",
                    "apa": "apa.csl",
                    "ieee": "ieee.csl",
                    "vancouver": "vancouver.csl",
                    "harvard": "harvard-cite-them-right.csl",
                }
                csl_name = style_to_csl.get(args.style, "chinese-gb7714-2015-numeric.csl")
                potential_csl = os.path.join(csl_dir, csl_name)
                if os.path.exists(potential_csl):
                    csl_file = potential_csl

                docx_path = os.path.join(output_dir, f"{base_name}_final.docx")
                result = convert_to_docx(
                    formatted_md_path,
                    docx_path,
                    bib_path=output_files.get("bibtex"),
                    csl_file=csl_file,
                )
                if result["success"]:
                    output_files["docx"] = docx_path
                else:
                    output_files["docx_error"] = result.get("error", "Unknown error")
            except Exception as e:
                output_files["docx_error"] = str(e)
        else:
            output_files["docx_skipped"] = "pandoc not installed"

    report = {
        "total_placeholders": len(placeholders),
        "unique_citations": len(unique_citations),
        "successful": len(papers),
        "failed": len(failed),
        "citation_style": args.style,
        "output_files": output_files,
    }
    if failed:
        report["failed_items"] = failed

    print(json.dumps({"status": "completed", "report": report}, indent=2, ensure_ascii=False))
    return 0


async def cmd_cache_list(args: argparse.Namespace) -> int:
    """List cached search results."""
    from .cache import SearchCache
    cache = SearchCache(cache_dir=DEFAULT_CACHE_DIR)
    print(json.dumps({
        "stats": cache.get_stats(),
        "items": cache.list_cache(),
    }, indent=2, ensure_ascii=False))
    return 0


async def cmd_cache_clear(args: argparse.Namespace) -> int:
    """Clear all cached search results."""
    from .cache import SearchCache
    cache = SearchCache(cache_dir=DEFAULT_CACHE_DIR)
    count = cache.clear()
    print(json.dumps({"status": "cleared", "entries_cleared": count}, indent=2))
    return 0


async def cmd_library(args: argparse.Namespace) -> int:
    """Search or list papers in the local SQLite library."""
    if args.library_command == "stats":
        print(json.dumps(storage.get_stats(), indent=2, ensure_ascii=False))
    elif args.library_command == "search":
        results = storage.search_local(args.keyword, limit=args.limit)
        print(json.dumps(results, indent=2, ensure_ascii=False, default=str))
    elif args.library_command == "list":
        results = storage.list_papers(source=args.source, limit=args.limit)
        print(json.dumps(results, indent=2, ensure_ascii=False, default=str))
    return 0


# ---------------------------------------------------------------------------
# Writing templates
# ---------------------------------------------------------------------------

# Packaged templates directory (shipped with the package as data files).
_TEMPLATES_DIR = os.path.join(os.path.dirname(__file__), "writing_templates")

_HARNESS_TEMPLATES_DIR = os.path.join(os.path.dirname(__file__), "harness_templates")
# User-visible target directory (under WORK_DIR).
_TEMPLATES_TARGET = os.path.join(get_work_dir(), ".paper_toolkit", "writing_templates")


def _list_available_templates() -> list[str]:
    """Scan the packaged templates directory for .md files."""
    if not os.path.isdir(_TEMPLATES_DIR):
        return []
    return sorted(
        f[:-3] for f in os.listdir(_TEMPLATES_DIR) if f.endswith(".md")
    )


def cmd_init_templates(args: argparse.Namespace) -> int:
    """Initialize writing templates into the working directory.

    Without --type: list available templates.
    With --type <name>: copy the template to .paper_toolkit/writing_templates/.
    With --all: copy all templates.
    --force: overwrite existing files.
    """
    available = _list_available_templates()
    if not available:
        print(json.dumps({"error": "No templates found in package"}, indent=2))
        return 1

    if not args.template_type and not args.all:
        # List mode
        installed = []
        if os.path.isdir(_TEMPLATES_TARGET):
            installed = [
                f[:-3] for f in os.listdir(_TEMPLATES_TARGET) if f.endswith(".md")
            ]
        print(json.dumps({
            "available": available,
            "installed": installed,
            "target_dir": _TEMPLATES_TARGET,
        }, indent=2, ensure_ascii=False))
        return 0

    to_install = available if args.all else [args.template_type]
    for tpl in to_install:
        if tpl not in available:
            print(json.dumps({"error": f"Unknown template: {tpl}", "available": available}, indent=2))
            return 1

    os.makedirs(_TEMPLATES_TARGET, exist_ok=True)
    installed_list = []
    for tpl in to_install:
        src = os.path.join(_TEMPLATES_DIR, f"{tpl}.md")
        dst = os.path.join(_TEMPLATES_TARGET, f"{tpl}.md")
        if os.path.exists(dst) and not args.force:
            installed_list.append({"template": tpl, "status": "skipped", "reason": "already exists (use --force)"})
            continue
        shutil.copy2(src, dst)
        installed_list.append({"template": tpl, "status": "installed", "path": dst})

    print(json.dumps({
        "status": "completed",
        "installed": installed_list,
        "target_dir": _TEMPLATES_TARGET,
    }, indent=2, ensure_ascii=False))
    return 0


# ---------------------------------------------------------------------------
# harness init
# ---------------------------------------------------------------------------

def _copy_tree(src: str, dst: str, *, force: bool = False) -> list[dict]:
    """Recursively copy *src* into *dst*, returning a manifest of actions."""
    actions: list[dict] = []
    for root, _dirs, files in os.walk(src):
        rel = os.path.relpath(root, src)
        target_dir = os.path.join(dst, rel) if rel != "." else dst
        for fname in files:
            src_file = os.path.join(root, fname)
            dst_file = os.path.join(target_dir, fname)
            if os.path.exists(dst_file) and not force:
                actions.append({"file": os.path.relpath(dst_file, dst), "status": "skipped"})
                continue
            os.makedirs(target_dir, exist_ok=True)
            shutil.copy2(src_file, dst_file)
            actions.append({"file": os.path.relpath(dst_file, dst), "status": "created"})
    return actions


def cmd_harness_init(args: argparse.Namespace) -> int:
    """Initialize .harness/ directory in the current project."""
    if not os.path.isdir(_HARNESS_TEMPLATES_DIR):
        print(json.dumps({"error": "Harness templates not found in package"}, indent=2))
        return 1

    target = os.path.join(os.getcwd(), ".harness")
    if os.path.isdir(target) and not args.force:
        existing = []
        for root, _dirs, files in os.walk(target):
            for f in files:
                existing.append(os.path.relpath(os.path.join(root, f), target))
        print(json.dumps({
            "status": "already_exists",
            "target_dir": target,
            "existing_files": existing,
            "hint": "Use --force to overwrite",
        }, indent=2, ensure_ascii=False))
        return 0

    actions = _copy_tree(_HARNESS_TEMPLATES_DIR, target, force=args.force)
    print(json.dumps({
        "status": "initialized",
        "target_dir": target,
        "files": actions,
        "next_steps": [
            "Review and edit .harness/specs/manuscript-spec.yaml for your paper",
            "Run: python .harness/verify.py <your_manuscript.md>",
        ],
    }, indent=2, ensure_ascii=False))
    return 0


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="paper-toolkit",
        description="Search, download, and read academic papers from 20+ sources.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # search
    p_search = sub.add_parser("search", help="Search for papers across academic platforms")
    p_search.add_argument("query", help="Search query")
    p_search.add_argument("-n", "--max-results", type=int, default=5, help="Max results per source (default: 5)")
    p_search.add_argument("-s", "--sources", default="all",
                          help="Sources: 'all', 'medical', 'cs', 'metadata', or comma-separated names")
    p_search.add_argument("--year-from", type=int, default=None,
                          help="Earliest year (default: current-5, pass 0 to disable)")
    p_search.add_argument("--year-to", type=int, default=None,
                          help="Latest year")

    # download
    p_dl = sub.add_parser("download", help="Download a paper PDF")
    p_dl.add_argument("source", help="Source platform (e.g. arxiv, semantic)")
    p_dl.add_argument("paper_id", help="Paper identifier")
    p_dl.add_argument("-o", "--save-path", default=DEFAULT_SAVE_PATH,
                      help="Save directory (default: <WORK_DIR>/downloads)")

    # download-by-key (recommended way: use cite_key from search results)
    p_dlk = sub.add_parser("download-by-key", help="Download a paper PDF by cite_key")
    p_dlk.add_argument("cite_key", help="The cite_key from search results (e.g. Kxq)")
    p_dlk.add_argument("-o", "--save-path", default=DEFAULT_SAVE_PATH,
                       help="Save directory (default: <WORK_DIR>/downloads)")

    # read
    p_read = sub.add_parser("read", help="Download and extract text from a paper")
    p_read.add_argument("source", help="Source platform (e.g. arxiv, semantic)")
    p_read.add_argument("paper_id", help="Paper identifier")
    p_read.add_argument("-o", "--save-path", default=DEFAULT_SAVE_PATH,
                        help="Save directory (default: <WORK_DIR>/downloads)")

    # read-by-key
    p_rdk = sub.add_parser("read-by-key", help="Download and extract text by cite_key")
    p_rdk.add_argument("cite_key", help="The cite_key from search results")
    p_rdk.add_argument("-o", "--save-path", default=DEFAULT_SAVE_PATH,
                       help="Save directory (default: <WORK_DIR>/downloads)")

    # sources
    sub.add_parser("sources", help="List available sources")

    # manuscript
    p_ms = sub.add_parser("manuscript", help="Process manuscript with citation placeholders")
    p_ms.add_argument("file", help="Path to Markdown file")
    p_ms.add_argument("-o", "--output", default=None, help="Output directory (default: same as input)")
    p_ms.add_argument("-s", "--style", default="gb7714",
                      help="Citation style (gb7714, apa, ieee, vancouver, harvard)")
    p_ms.add_argument("--no-bib", dest="generate_bib", action="store_false",
                      help="Do not generate BibTeX file")
    p_ms.add_argument("--no-ris", dest="generate_ris", action="store_false",
                      help="Do not generate RIS file")
    p_ms.add_argument("--no-docx", dest="generate_docx", action="store_false",
                      help="Do not generate Word document")
    p_ms.add_argument("--cache-ttl", type=int, default=24,
                      help="Cache TTL in hours (default: 24)")
    p_ms.set_defaults(generate_bib=True, generate_ris=True, generate_docx=True)

    # cache
    p_cache = sub.add_parser("cache", help="Manage search cache")
    cache_sub = p_cache.add_subparsers(dest="cache_command")
    cache_sub.add_parser("list", help="List cached items")
    cache_sub.add_parser("clear", help="Clear all cache")

    # library (SQLite)
    p_lib = sub.add_parser("library", help="Manage local paper library (SQLite)")
    lib_sub = p_lib.add_subparsers(dest="library_command")
    lib_sub.add_parser("stats", help="Show library statistics")
    p_lib_search = lib_sub.add_parser("search", help="Search local library by keyword")
    p_lib_search.add_argument("keyword", help="Search keyword")
    p_lib_search.add_argument("-n", "--limit", type=int, default=50, help="Max results")
    p_lib_list = lib_sub.add_parser("list", help="List papers in library")
    p_lib_list.add_argument("-s", "--source", default="", help="Filter by source")
    p_lib_list.add_argument("-n", "--limit", type=int, default=100, help="Max results")

    # init-templates: install writing templates to working directory
    p_init = sub.add_parser("init-templates", help="Install writing templates to working directory")
    p_init.add_argument("-t", "--type", dest="template_type", default="",
                        help="Template name (e.g. nursing_chinese_review). Without this, lists available.")
    p_init.add_argument("--all", action="store_true", help="Install all available templates")
    p_init.add_argument("--force", action="store_true", help="Overwrite existing files")

    # harness: academic manuscript harness management
    p_harness = sub.add_parser("harness", help="Academic manuscript harness management")
    harness_sub = p_harness.add_subparsers(dest="harness_command")
    p_harness_init = harness_sub.add_parser("init", help="Initialize .harness/ in current project")
    p_harness_init.add_argument("--force", action="store_true", help="Overwrite existing files")

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    dispatch = {
        "search": cmd_search,
        "download": cmd_download,
        "download-by-key": cmd_download_by_key,
        "read": cmd_read,
        "read-by-key": cmd_read_by_key,
        "sources": cmd_sources,
        "manuscript": cmd_manuscript,
    }

    if args.command == "init-templates":
        # Synchronous command — no asyncio needed (just file copy)
        exit_code = cmd_init_templates(args)
    elif args.command == "harness":
        if args.harness_command == "init":
            exit_code = cmd_harness_init(args)
        else:
            parser.parse_args(["harness", "--help"])
            exit_code = 0
    elif args.command == "cache":
        if args.cache_command == "list":
            exit_code = asyncio.run(cmd_cache_list(args))
        elif args.cache_command == "clear":
            exit_code = asyncio.run(cmd_cache_clear(args))
        else:
            parser.parse_args(["cache", "--help"])
            exit_code = 0
    elif args.command == "library":
        if args.library_command in ("stats", "search", "list"):
            exit_code = asyncio.run(cmd_library(args))
        else:
            parser.parse_args(["library", "--help"])
            exit_code = 0
    else:
        exit_code = asyncio.run(dispatch[args.command](args))

    sys.exit(exit_code)


if __name__ == "__main__":
    main()
