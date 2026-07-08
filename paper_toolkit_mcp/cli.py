#!/usr/bin/env python3
"""CLI interface for paper-toolkit — search, download, and read academic papers."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from typing import Any

from .academic_platforms.arxiv import ArxivSearcher
from .academic_platforms.base_search import BASESearcher
from .academic_platforms.biorxiv import BioRxivSearcher
from .academic_platforms.citeseerx import CiteSeerXSearcher
from .academic_platforms.core import CORESearcher
from .academic_platforms.crossref import CrossRefSearcher
from .academic_platforms.dblp import DBLPSearcher
from .academic_platforms.doaj import DOAJSearcher
from .academic_platforms.europepmc import EuropePMCSearcher
from .academic_platforms.google_scholar import GoogleScholarSearcher
from .academic_platforms.hal import HALSearcher
from .academic_platforms.iacr import IACRSearcher
from .academic_platforms.medrxiv import MedRxivSearcher
from .academic_platforms.openaire import OpenAiresearcher
from .academic_platforms.openalex import OpenAlexSearcher
from .academic_platforms.pmc import PMCSearcher
from .academic_platforms.pubmed import PubMedSearcher
from .academic_platforms.semantic import SemanticSearcher
from .academic_platforms.ssrn import SSRNSearcher
from .academic_platforms.unpaywall import UnpaywallResolver, UnpaywallSearcher
from .academic_platforms.zenodo import ZenodoSearcher
from .config import get_env

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
    SEARCHERS["biorxiv"] = BioRxivSearcher()
    SEARCHERS["medrxiv"] = MedRxivSearcher()
    SEARCHERS["google_scholar"] = GoogleScholarSearcher()
    SEARCHERS["iacr"] = IACRSearcher()
    SEARCHERS["semantic"] = SemanticSearcher()
    SEARCHERS["crossref"] = CrossRefSearcher()
    SEARCHERS["openalex"] = OpenAlexSearcher()
    SEARCHERS["pmc"] = PMCSearcher()
    SEARCHERS["core"] = CORESearcher()
    SEARCHERS["europepmc"] = EuropePMCSearcher()
    SEARCHERS["dblp"] = DBLPSearcher()
    SEARCHERS["openaire"] = OpenAiresearcher()
    SEARCHERS["citeseerx"] = CiteSeerXSearcher()
    SEARCHERS["doaj"] = DOAJSearcher()
    SEARCHERS["base"] = BASESearcher()
    unpaywall_resolver = UnpaywallResolver()
    SEARCHERS["unpaywall"] = UnpaywallSearcher(resolver=unpaywall_resolver)
    SEARCHERS["zenodo"] = ZenodoSearcher()
    SEARCHERS["hal"] = HALSearcher()
    SEARCHERS["ssrn"] = SSRNSearcher()

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
    "arxiv", "pubmed", "biorxiv", "medrxiv", "google_scholar", "iacr",
    "semantic", "crossref", "openalex", "pmc", "core", "europepmc",
    "dblp", "openaire", "citeseerx", "doaj", "base", "zenodo", "hal",
    "ssrn", "unpaywall",
]


def _parse_sources(sources: str) -> list[str]:
    if not sources or sources.strip().lower() == "all":
        return [s for s in ALL_SOURCES if s in SEARCHERS]
    normalized = [p.strip().lower() for p in sources.split(",") if p.strip()]
    return [s for s in normalized if s in SEARCHERS]


def _paper_unique_key(paper: dict[str, Any]) -> str:
    doi = (paper.get("doi") or "").strip().lower()
    if doi:
        return f"doi:{doi}"
    title = (paper.get("title") or "").strip().lower()
    authors = (paper.get("authors") or "").strip().lower()
    if title:
        return f"title:{title}|authors:{authors}"
    return f"id:{(paper.get('paper_id') or '').strip().lower()}"


def _dedupe(papers: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    out: list[dict[str, Any]] = []
    for p in papers:
        k = _paper_unique_key(p)
        if k not in seen:
            seen.add(k)
            out.append(p)
    return out


# ---------------------------------------------------------------------------
# Async helpers
# ---------------------------------------------------------------------------

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

    tasks = {}
    for src in selected:
        searcher = SEARCHERS[src]
        extra = {}
        if src == "semantic" and args.year:
            extra["year"] = args.year
        tasks[src] = _async_search(searcher, args.query, args.max_results, **extra)

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

    deduped = _dedupe(merged)

    output = {
        "query": args.query,
        "sources_used": names,
        "source_results": source_counts,
        "errors": errors,
        "total": len(deduped),
        "papers": deduped,
    }
    print(json.dumps(output, indent=2, default=str))
    return 0


async def cmd_download(args: argparse.Namespace) -> int:
    _init_searchers()
    source = args.source.strip().lower()

    if source not in SEARCHERS:
        print(json.dumps({"error": f"Unknown source: {source}", "available": sorted(SEARCHERS.keys())}))
        return 1

    searcher = SEARCHERS[source]
    try:
        result = await asyncio.to_thread(searcher.download_pdf, args.paper_id, args.save_path)
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

    cache = SearchCache(ttl_hours=args.cache_ttl)
    output_dir = args.output or os.path.dirname(markdown_path) or "."
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
    cache = SearchCache()
    print(json.dumps({
        "stats": cache.get_stats(),
        "items": cache.list_cache(),
    }, indent=2, ensure_ascii=False))
    return 0


async def cmd_cache_clear(args: argparse.Namespace) -> int:
    """Clear all cached search results."""
    from .cache import SearchCache
    cache = SearchCache()
    count = cache.clear()
    print(json.dumps({"status": "cleared", "entries_cleared": count}, indent=2))
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
                          help="Comma-separated sources or 'all' (default: all)")
    p_search.add_argument("-y", "--year", default=None,
                          help="Year filter for Semantic Scholar (e.g. '2020', '2018-2022')")

    # download
    p_dl = sub.add_parser("download", help="Download a paper PDF")
    p_dl.add_argument("source", help="Source platform (e.g. arxiv, semantic)")
    p_dl.add_argument("paper_id", help="Paper identifier")
    p_dl.add_argument("-o", "--save-path", default="./downloads", help="Save directory (default: ./downloads)")

    # read
    p_read = sub.add_parser("read", help="Download and extract text from a paper")
    p_read.add_argument("source", help="Source platform (e.g. arxiv, semantic)")
    p_read.add_argument("paper_id", help="Paper identifier")
    p_read.add_argument("-o", "--save-path", default="./downloads", help="Save directory (default: ./downloads)")

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

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    dispatch = {
        "search": cmd_search,
        "download": cmd_download,
        "read": cmd_read,
        "sources": cmd_sources,
        "manuscript": cmd_manuscript,
    }

    if args.command == "cache":
        if args.cache_command == "list":
            exit_code = asyncio.run(cmd_cache_list(args))
        elif args.cache_command == "clear":
            exit_code = asyncio.run(cmd_cache_clear(args))
        else:
            parser.parse_args(["cache", "--help"])
            exit_code = 0
    else:
        exit_code = asyncio.run(dispatch[args.command](args))

    sys.exit(exit_code)


if __name__ == "__main__":
    main()
