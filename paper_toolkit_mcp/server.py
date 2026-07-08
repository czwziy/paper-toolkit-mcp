# paper_toolkit_mcp/server.py
import asyncio
import logging
import os
import re
from typing import Any

import httpx
from mcp.server.fastmcp import FastMCP

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
from .academic_platforms.sci_hub import SciHubFetcher
from .academic_platforms.semantic import SemanticSearcher
from .academic_platforms.ssrn import SSRNSearcher
from .academic_platforms.unpaywall import UnpaywallResolver, UnpaywallSearcher
from .academic_platforms.zenodo import ZenodoSearcher
from .cache import SearchCache
from .config import get_env, get_work_dir
from .pandoc_helper import convert_to_docx, pandoc_available

# from .academic_platforms.hub import SciHubSearcher
from .reference import (
    generate_bibtex,
    generate_reference_list,
    generate_ris,
    parse_citation_placeholders,
    process_manuscript_text,
)

# Initialize MCP server
mcp = FastMCP("paper_toolkit_server")
logger = logging.getLogger(__name__)

# Default download directory, resolved once at import from WORK_DIR (or CWD).
# Used as the default save_path for all download_* / read_* MCP tools so files
# land inside the user's project folder regardless of the server process CWD.
DEFAULT_SAVE_PATH = os.path.join(get_work_dir(), "downloads")

# Instances of searchers
arxiv_searcher = ArxivSearcher()
pubmed_searcher = PubMedSearcher()
biorxiv_searcher = BioRxivSearcher()
medrxiv_searcher = MedRxivSearcher()
google_scholar_searcher = GoogleScholarSearcher()
iacr_searcher = IACRSearcher()
semantic_searcher = SemanticSearcher()
crossref_searcher = CrossRefSearcher()
openalex_searcher = OpenAlexSearcher()
pmc_searcher = PMCSearcher()
core_searcher = CORESearcher()
europepmc_searcher = EuropePMCSearcher()
dblp_searcher = DBLPSearcher()
openaire_searcher = OpenAiresearcher()
citeseerx_searcher = CiteSeerXSearcher()
doaj_searcher = DOAJSearcher()
base_searcher = BASESearcher()
unpaywall_resolver = UnpaywallResolver()
unpaywall_searcher = UnpaywallSearcher(resolver=unpaywall_resolver)
zenodo_searcher = ZenodoSearcher()
hal_searcher = HALSearcher()
ssrn_searcher = SSRNSearcher()
# scihub_searcher = SciHubSearcher()


# Asynchronous helper to adapt synchronous searchers
# Runs blocking requests-based calls in a thread pool to avoid blocking the event loop.
async def async_search(searcher, query: str, max_results: int, **kwargs) -> list[dict]:
    if 'year' in kwargs:
        papers = await asyncio.to_thread(searcher.search, query, max_results=max_results, year=kwargs['year'])
    elif kwargs:
        papers = await asyncio.to_thread(searcher.search, query, max_results=max_results, **kwargs)
    else:
        papers = await asyncio.to_thread(searcher.search, query, max_results=max_results)
    return [paper.to_dict() for paper in papers]


ALL_SOURCES = [
    "arxiv",
    "pubmed",
    "biorxiv",
    "medrxiv",
    "google_scholar",
    "iacr",
    "semantic",
    "crossref",
    "openalex",
    "pmc",
    "core",
    "europepmc",
    "dblp",
    "openaire",
    "citeseerx",
    "doaj",
    "base",
    "zenodo",
    "hal",
    "ssrn",
    "unpaywall",
]


# ---------------------------------------------------------------------------
# Optional paid-platform connectors (disabled by default)
# Set paper_toolkit_mcp_IEEE_API_KEY / paper_toolkit_mcp_ACM_API_KEY to activate
# (legacy IEEE_API_KEY / ACM_API_KEY are also supported).
# ---------------------------------------------------------------------------
_ieee_api_key = get_env("IEEE_API_KEY", "")
_acm_api_key = get_env("ACM_API_KEY", "")

if _ieee_api_key:
    from .academic_platforms.ieee import IEEESearcher
    ieee_searcher: IEEESearcher | None = IEEESearcher()
    ALL_SOURCES.append("ieee")
    logger.info("IEEE Xplore enabled via configured environment key.")
else:
    ieee_searcher = None

if _acm_api_key:
    from .academic_platforms.acm import ACMSearcher
    acm_searcher: ACMSearcher | None = ACMSearcher()
    ALL_SOURCES.append("acm")
    logger.info("ACM Digital Library enabled via configured environment key.")
else:
    acm_searcher = None


def _parse_sources(sources: str) -> list[str]:
    if not sources or sources.strip().lower() == "all":
        return ALL_SOURCES

    normalized = [part.strip().lower() for part in sources.split(",") if part.strip()]
    return [source for source in normalized if source in ALL_SOURCES]


def _paper_unique_key(paper: dict[str, Any]) -> str:
    doi = (paper.get("doi") or "").strip().lower()
    if doi:
        return f"doi:{doi}"

    title = (paper.get("title") or "").strip().lower()
    authors = (paper.get("authors") or "").strip().lower()
    if title:
        return f"title:{title}|authors:{authors}"

    paper_id = (paper.get("paper_id") or "").strip().lower()
    return f"id:{paper_id}"


def _dedupe_papers(papers: list[dict[str, Any]]) -> list[dict[str, Any]]:
    deduped: list[dict[str, Any]] = []
    seen: set[str] = set()

    for paper in papers:
        key = _paper_unique_key(paper)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(paper)

    return deduped


def _safe_filename(filename_hint: str, default: str = "paper") -> str:
    safe = re.sub(r"[^a-zA-Z0-9._-]+", "_", filename_hint).strip("._")
    if not safe:
        return default
    return safe[:120]


async def _download_from_url(pdf_url: str, save_path: str, filename_hint: str = "paper") -> str | None:
    if not pdf_url:
        return None

    os.makedirs(save_path, exist_ok=True)
    output_name = f"{_safe_filename(filename_hint)}.pdf"
    output_path = os.path.join(save_path, output_name)

    try:
        async with httpx.AsyncClient(follow_redirects=True, timeout=30) as client:
            response = await client.get(pdf_url)

        if response.status_code >= 400 or not response.content:
            return None

        content_type = (response.headers.get("content-type") or "").lower()
        is_pdf = "pdf" in content_type or response.content.startswith(b"%PDF") or pdf_url.lower().endswith(".pdf")
        if not is_pdf:
            logger.warning("Resolved URL is not a PDF candidate: %s (content-type=%s)", pdf_url, content_type)
            return None

        with open(output_path, "wb") as file_obj:
            file_obj.write(response.content)

        return output_path
    except Exception as exc:
        logger.warning("Direct URL download failed for %s: %s", pdf_url, exc)
        return None


async def _try_repository_fallback(doi: str, title: str, save_path: str) -> tuple[str | None, str]:
    repository_searchers = [
        ("openaire", openaire_searcher),
        ("core", core_searcher),
        ("europepmc", europepmc_searcher),
        ("pmc", pmc_searcher),
    ]

    query_candidates = [(doi or "").strip(), (title or "").strip()]
    query_candidates = [candidate for candidate in query_candidates if candidate]
    if not query_candidates:
        return None, "no DOI/title provided for repository fallback"

    repository_errors: list[str] = []

    for repo_name, searcher in repository_searchers:
        for query in query_candidates:
            try:
                papers = await asyncio.to_thread(searcher.search, query, max_results=3)
            except Exception as exc:
                repository_errors.append(f"{repo_name}:{exc}")
                continue

            if not papers:
                continue

            for paper in papers:
                pdf_url = (getattr(paper, "pdf_url", "") or "").strip()
                if not pdf_url:
                    continue

                paper_id = (getattr(paper, "paper_id", "") or query).strip()
                downloaded = await _download_from_url(pdf_url, save_path, f"{repo_name}_{paper_id}")
                if downloaded:
                    return downloaded, ""

    return None, "; ".join(repository_errors)


@mcp.tool()
async def search_papers(
    query: str,
    max_results_per_source: int = 5,
    sources: str = "all",
    year: str | None = None,
) -> dict[str, Any]:
    """Unified top-level search across all configured academic platforms.

    Args:
        query: Search query string.
        max_results_per_source: Max results to fetch from each selected source.
        sources: Comma-separated source names or 'all'.
            Available: arxiv,pubmed,biorxiv,medrxiv,google_scholar,iacr,semantic,crossref,openalex,pmc,core,europepmc,dblp,openaire,citeseerx,doaj,base,zenodo,hal,ssrn,unpaywall
        year: Optional year filter for Semantic Scholar only.
    Returns:
        Aggregated dictionary with per-source stats, errors, and deduplicated papers.
    """
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
        elif source == "biorxiv":
            task_map[source] = search_biorxiv(query, max_results_per_source)
        elif source == "medrxiv":
            task_map[source] = search_medrxiv(query, max_results_per_source)
        elif source == "google_scholar":
            task_map[source] = search_google_scholar(query, max_results_per_source)
        elif source == "iacr":
            task_map[source] = search_iacr(query, max_results_per_source, fetch_details=False)
        elif source == "semantic":
            task_map[source] = search_semantic(query, year=year, max_results=max_results_per_source)
        elif source == "crossref":
            task_map[source] = search_crossref(query, max_results=max_results_per_source)
        elif source == "openalex":
            task_map[source] = search_openalex(query, max_results_per_source)
        elif source == "pmc":
            task_map[source] = search_pmc(query, max_results_per_source)
        elif source == "core":
            task_map[source] = search_core(query, max_results_per_source)
        elif source == "europepmc":
            task_map[source] = search_europepmc(query, max_results_per_source)
        elif source == "dblp":
            task_map[source] = search_dblp(query, max_results_per_source)
        elif source == "openaire":
            task_map[source] = search_openaire(query, max_results_per_source)
        elif source == "citeseerx":
            task_map[source] = search_citeseerx(query, max_results_per_source)
        elif source == "doaj":
            task_map[source] = search_doaj(query, max_results_per_source)
        elif source == "base":
            task_map[source] = search_base(query, max_results_per_source)
        elif source == "zenodo":
            task_map[source] = search_zenodo(query, max_results_per_source)
        elif source == "hal":
            task_map[source] = search_hal(query, max_results_per_source)
        elif source == "ssrn":
            task_map[source] = search_ssrn(query, max_results_per_source)
        elif source == "unpaywall":
            task_map[source] = search_unpaywall(query, max_results_per_source)
        elif source == "ieee":
            if ieee_searcher is not None:
                task_map[source] = async_search(ieee_searcher, query, max_results_per_source)
        elif source == "acm":
            if acm_searcher is not None:
                task_map[source] = async_search(acm_searcher, query, max_results_per_source)

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

    deduped_papers = _dedupe_papers(merged_papers)

    return {
        "query": query,
        "sources_requested": sources,
        "sources_used": source_names,
        "source_results": source_results,
        "errors": errors,
        "papers": deduped_papers,
        "total": len(deduped_papers),
        "raw_total": len(merged_papers),
    }


# Tool definitions
@mcp.tool()
async def search_arxiv(query: str, max_results: int = 10, sort_by: str = 'relevance', sort_order: str = 'descending') -> list[dict]:
    """Search academic papers from arXiv.

    Args:
        query: Search query string (e.g., 'machine learning').
        max_results: Maximum number of papers to return (default: 10).
        sort_by: Sort criterion — 'relevance', 'submittedDate', or 'lastUpdatedDate' (default: 'relevance').
        sort_order: Sort direction — 'descending' or 'ascending' (default: 'descending').
    Returns:
        List of paper metadata in dictionary format.
    """
    papers = await async_search(arxiv_searcher, query, max_results, sort_by=sort_by, sort_order=sort_order)
    return papers if papers else []


@mcp.tool()
async def search_pubmed(query: str, max_results: int = 10, sort: str = 'relevance') -> list[dict]:
    """Search academic papers from PubMed.

    Args:
        query: Search query string (e.g., 'machine learning').
        max_results: Maximum number of papers to return (default: 10).
        sort: Sort order — 'relevance' or 'pub_date' (default: 'relevance').
    Returns:
        List of paper metadata in dictionary format.
    """
    papers = await async_search(pubmed_searcher, query, max_results, sort=sort)
    return papers if papers else []


@mcp.tool()
async def search_biorxiv(query: str, max_results: int = 10) -> list[dict]:
    """Search academic papers from bioRxiv.

    Note: bioRxiv API filters by category name within the last 30 days, not full-text
    keyword search. Use a category keyword such as 'bioinformatics', 'neuroscience',
    'cell biology', etc.

    Args:
        query: Category name to filter by (e.g., 'bioinformatics', 'neuroscience').
        max_results: Maximum number of papers to return (default: 10).
    Returns:
        List of paper metadata in dictionary format.
    """
    papers = await async_search(biorxiv_searcher, query, max_results)
    return papers if papers else []


@mcp.tool()
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
    papers = await async_search(medrxiv_searcher, query, max_results)
    return papers if papers else []


@mcp.tool()
async def search_google_scholar(query: str, max_results: int = 10) -> list[dict]:
    """Search academic papers from Google Scholar.

    Args:
        query: Search query string (e.g., 'machine learning').
        max_results: Maximum number of papers to return (default: 10).
    Returns:
        List of paper metadata in dictionary format.
    """
    papers = await async_search(google_scholar_searcher, query, max_results)
    return papers if papers else []


@mcp.tool()
async def search_iacr(
    query: str, max_results: int = 10, fetch_details: bool = True
) -> list[dict]:
    """Search academic papers from IACR ePrint Archive.

    Args:
        query: Search query string (e.g., 'cryptography', 'secret sharing').
        max_results: Maximum number of papers to return (default: 10).
        fetch_details: Whether to fetch detailed information for each paper (default: True).
    Returns:
        List of paper metadata in dictionary format.
    """
    papers = await async_search(iacr_searcher, query, max_results, fetch_details=fetch_details)
    return papers if papers else []


@mcp.tool()
async def download_arxiv(paper_id: str, save_path: str = DEFAULT_SAVE_PATH) -> str:
    """Download PDF of an arXiv paper.

    Args:
        paper_id: arXiv paper ID (e.g., '2106.12345').
        save_path: Directory to save the PDF (default: <WORK_DIR>/downloads).
    Returns:
        Path to the downloaded PDF file.
    """
    return await asyncio.to_thread(arxiv_searcher.download_pdf, paper_id, save_path)


@mcp.tool()
async def download_pubmed(paper_id: str, save_path: str = DEFAULT_SAVE_PATH) -> str:
    """Attempt to download PDF of a PubMed paper.

    Args:
        paper_id: PubMed ID (PMID).
        save_path: Directory to save the PDF (default: <WORK_DIR>/downloads).
    Returns:
        str: Message indicating that direct PDF download is not supported.
    """
    try:
        return pubmed_searcher.download_pdf(paper_id, save_path)
    except NotImplementedError as e:
        return str(e)


@mcp.tool()
async def download_biorxiv(paper_id: str, save_path: str = DEFAULT_SAVE_PATH) -> str:
    """Download PDF of a bioRxiv paper.

    Args:
        paper_id: bioRxiv DOI.
        save_path: Directory to save the PDF (default: <WORK_DIR>/downloads).
    Returns:
        Path to the downloaded PDF file.
    """
    return biorxiv_searcher.download_pdf(paper_id, save_path)


@mcp.tool()
async def download_medrxiv(paper_id: str, save_path: str = DEFAULT_SAVE_PATH) -> str:
    """Download PDF of a medRxiv paper.

    Args:
        paper_id: medRxiv DOI.
        save_path: Directory to save the PDF (default: <WORK_DIR>/downloads).
    Returns:
        Path to the downloaded PDF file.
    """
    return medrxiv_searcher.download_pdf(paper_id, save_path)


@mcp.tool()
async def download_iacr(paper_id: str, save_path: str = DEFAULT_SAVE_PATH) -> str:
    """Download PDF of an IACR ePrint paper.

    Args:
        paper_id: IACR paper ID (e.g., '2009/101').
        save_path: Directory to save the PDF (default: <WORK_DIR>/downloads).
    Returns:
        Path to the downloaded PDF file.
    """
    return iacr_searcher.download_pdf(paper_id, save_path)


@mcp.tool()
async def read_arxiv_paper(paper_id: str, save_path: str = DEFAULT_SAVE_PATH) -> str:
    """Read and extract text content from an arXiv paper PDF.

    Args:
        paper_id: arXiv paper ID (e.g., '2106.12345').
        save_path: Directory where the PDF is/will be saved (default: <WORK_DIR>/downloads).
    Returns:
        str: The extracted text content of the paper.
    """
    try:
        return arxiv_searcher.read_paper(paper_id, save_path)
    except Exception as e:
        print(f"Error reading paper {paper_id}: {e}")
        return ""


@mcp.tool()
async def read_pubmed_paper(paper_id: str, save_path: str = DEFAULT_SAVE_PATH) -> str:
    """Read and extract text content from a PubMed paper.

    Args:
        paper_id: PubMed ID (PMID).
        save_path: Directory where the PDF would be saved (unused).
    Returns:
        str: Message indicating that direct paper reading is not supported.
    """
    return pubmed_searcher.read_paper(paper_id, save_path)


@mcp.tool()
async def read_biorxiv_paper(paper_id: str, save_path: str = DEFAULT_SAVE_PATH) -> str:
    """Read and extract text content from a bioRxiv paper PDF.

    Args:
        paper_id: bioRxiv DOI.
        save_path: Directory where the PDF is/will be saved (default: <WORK_DIR>/downloads).
    Returns:
        str: The extracted text content of the paper.
    """
    try:
        return biorxiv_searcher.read_paper(paper_id, save_path)
    except Exception as e:
        print(f"Error reading paper {paper_id}: {e}")
        return ""


@mcp.tool()
async def read_medrxiv_paper(paper_id: str, save_path: str = DEFAULT_SAVE_PATH) -> str:
    """Read and extract text content from a medRxiv paper PDF.

    Args:
        paper_id: medRxiv DOI.
        save_path: Directory where the PDF is/will be saved (default: <WORK_DIR>/downloads).
    Returns:
        str: The extracted text content of the paper.
    """
    try:
        return medrxiv_searcher.read_paper(paper_id, save_path)
    except Exception as e:
        print(f"Error reading paper {paper_id}: {e}")
        return ""


@mcp.tool()
async def read_iacr_paper(paper_id: str, save_path: str = DEFAULT_SAVE_PATH) -> str:
    """Read and extract text content from an IACR ePrint paper PDF.

    Args:
        paper_id: IACR paper ID (e.g., '2009/101').
        save_path: Directory where the PDF is/will be saved (default: <WORK_DIR>/downloads).
    Returns:
        str: The extracted text content of the paper.
    """
    try:
        return iacr_searcher.read_paper(paper_id, save_path)
    except Exception as e:
        print(f"Error reading paper {paper_id}: {e}")
        return ""


@mcp.tool()
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
    papers = await async_search(semantic_searcher, query, max_results, **kwargs)
    return papers if papers else []


@mcp.tool()
async def download_semantic(paper_id: str, save_path: str = "./downloads") -> str:
    """Download PDF of a Semantic Scholar paper.

    Args:
        paper_id: Semantic Scholar paper ID, Paper identifier in one of the following formats:
            - Semantic Scholar ID (e.g., "649def34f8be52c8b66281af98ae884c09aef38b")
            - DOI:<doi> (e.g., "DOI:10.18653/v1/N18-3011")
            - ARXIV:<id> (e.g., "ARXIV:2106.15928")
            - MAG:<id> (e.g., "MAG:112218234")
            - ACL:<id> (e.g., "ACL:W12-3903")
            - PMID:<id> (e.g., "PMID:19872477")
            - PMCID:<id> (e.g., "PMCID:2323736")
            - URL:<url> (e.g., "URL:https://arxiv.org/abs/2106.15928v1")
        save_path: Directory to save the PDF (default: <WORK_DIR>/downloads).
    Returns:
        Path to the downloaded PDF file.
    """
    return semantic_searcher.download_pdf(paper_id, save_path)


@mcp.tool()
async def read_semantic_paper(paper_id: str, save_path: str = "./downloads") -> str:
    """Read and extract text content from a Semantic Scholar paper.

    Args:
        paper_id: Semantic Scholar paper ID, Paper identifier in one of the following formats:
            - Semantic Scholar ID (e.g., "649def34f8be52c8b66281af98ae884c09aef38b")
            - DOI:<doi> (e.g., "DOI:10.18653/v1/N18-3011")
            - ARXIV:<id> (e.g., "ARXIV:2106.15928")
            - MAG:<id> (e.g., "MAG:112218234")
            - ACL:<id> (e.g., "ACL:W12-3903")
            - PMID:<id> (e.g., "PMID:19872477")
            - PMCID:<id> (e.g., "PMCID:2323736")
            - URL:<url> (e.g., "URL:https://arxiv.org/abs/2106.15928v1")
        save_path: Directory where the PDF is/will be saved (default: <WORK_DIR>/downloads).
    Returns:
        str: The extracted text content of the paper.
    """
    try:
        return semantic_searcher.read_paper(paper_id, save_path)
    except Exception as e:
        print(f"Error reading paper {paper_id}: {e}")
        return ""


@mcp.tool()
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
    It's one of the largest citation databases covering millions of
    academic papers, journals, books, and other scholarly content.

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
    papers = await async_search(crossref_searcher, query, max_results, **extra)
    return papers if papers else []


@mcp.tool()
async def get_crossref_paper_by_doi(doi: str) -> dict:
    """Get a specific paper from CrossRef by its DOI.

    Args:
        doi: Digital Object Identifier (e.g., '10.1038/nature12373').
    Returns:
        Paper metadata in dictionary format, or empty dict if not found.

    Example:
        get_crossref_paper_by_doi("10.1038/nature12373")
    """
    paper = await asyncio.to_thread(crossref_searcher.get_paper_by_doi, doi)
    return paper.to_dict() if paper else {}


@mcp.tool()
async def download_crossref(paper_id: str, save_path: str = DEFAULT_SAVE_PATH) -> str:
    """Attempt to download PDF of a CrossRef paper.

    Args:
        paper_id: CrossRef DOI (e.g., '10.1038/nature12373').
        save_path: Directory to save the PDF (default: <WORK_DIR>/downloads).
    Returns:
        str: Message indicating that direct PDF download is not supported.

    Note:
        CrossRef is a citation database and doesn't provide direct PDF downloads.
        Use the DOI to access the paper through the publisher's website.
    """
    try:
        return crossref_searcher.download_pdf(paper_id, save_path)
    except NotImplementedError as e:
        return str(e)


@mcp.tool()
async def download_scihub(
    identifier: str,
    save_path: str = DEFAULT_SAVE_PATH,
    base_url: str = "https://sci-hub.se",
) -> str:
    """Download paper PDF via Sci-Hub (optional fallback connector).

    Args:
        identifier: DOI, title, PMID, or paper URL.
        save_path: Directory to save the PDF.
        base_url: Sci-Hub mirror URL.
    Returns:
        Downloaded PDF path on success; error message on failure.
    """
    fetcher = SciHubFetcher(base_url=base_url, output_dir=save_path)
    result = await asyncio.to_thread(fetcher.download_pdf, identifier)
    if result:
        return result
    return "Sci-Hub download failed. Try DOI first, then title, or change mirror URL."


@mcp.tool()
async def download_with_fallback(
    source: str,
    paper_id: str,
    doi: str = "",
    title: str = "",
    save_path: str = DEFAULT_SAVE_PATH,
    use_scihub: bool = True,
    scihub_base_url: str = "https://sci-hub.se",
) -> str:
    """Try source-native download, OA repositories, Unpaywall, then optional Sci-Hub.

    Args:
        source: Source name (arxiv, biorxiv, medrxiv, iacr, semantic, crossref, pubmed, pmc, core, europepmc, citeseerx, doaj, base, zenodo, hal, ssrn).
        paper_id: Source-native paper identifier.
        doi: Optional DOI used for repository/unpaywall/Sci-Hub fallback.
        title: Optional title used for repository/Sci-Hub fallback when DOI is unavailable.
        save_path: Directory to save downloaded files.
        use_scihub: Whether to fallback to Sci-Hub after OA attempts fail.
        scihub_base_url: Sci-Hub mirror URL for fallback.
    Returns:
        Download path on success or explanatory error message.
    """
    source_name = source.strip().lower()

    primary_downloaders = {
        "arxiv": arxiv_searcher.download_pdf,
        "biorxiv": biorxiv_searcher.download_pdf,
        "medrxiv": medrxiv_searcher.download_pdf,
        "iacr": iacr_searcher.download_pdf,
        "semantic": semantic_searcher.download_pdf,
        "pubmed": pubmed_searcher.download_pdf,
        "crossref": crossref_searcher.download_pdf,
        "pmc": pmc_searcher.download_pdf,
        "core": core_searcher.download_pdf,
        "europepmc": europepmc_searcher.download_pdf,
        "citeseerx": citeseerx_searcher.download_pdf,
        "doaj": doaj_searcher.download_pdf,
        "base": base_searcher.download_pdf,
        "zenodo": zenodo_searcher.download_pdf,
        "hal": hal_searcher.download_pdf,
        "ssrn": ssrn_searcher.download_pdf,
    }

    attempt_errors: list[str] = []
    primary_error = ""
    if source_name in primary_downloaders:
        try:
            primary_result = await asyncio.to_thread(primary_downloaders[source_name], paper_id, save_path)
            if isinstance(primary_result, str) and os.path.exists(primary_result):
                return primary_result
            if isinstance(primary_result, str) and primary_result:
                primary_error = primary_result
        except Exception as exc:
            primary_error = str(exc)
            logger.warning("Primary download failed for %s/%s: %s", source_name, paper_id, exc)
    else:
        primary_error = f"Unsupported source '{source_name}' for primary download."

    if primary_error:
        attempt_errors.append(f"primary: {primary_error}")

    repository_result, repository_error = await _try_repository_fallback(doi, title, save_path)
    if repository_result:
        return repository_result
    if repository_error:
        attempt_errors.append(f"repositories: {repository_error}")

    normalized_doi = (doi or "").strip()
    if normalized_doi:
        unpaywall_url = await asyncio.to_thread(unpaywall_resolver.resolve_best_pdf_url, normalized_doi)
        if unpaywall_url:
            unpaywall_result = await _download_from_url(unpaywall_url, save_path, f"unpaywall_{normalized_doi}")
            if unpaywall_result:
                return unpaywall_result
            attempt_errors.append("unpaywall: resolved OA URL but download failed")
        else:
            attempt_errors.append("unpaywall: no OA URL found (or paper_toolkit_mcp_UNPAYWALL_EMAIL/UNPAYWALL_EMAIL missing)")
    else:
        attempt_errors.append("unpaywall: DOI not provided")

    if not use_scihub:
        return "Download failed after OA fallback chain. Details: " + " | ".join(attempt_errors)

    fallback_identifier = (doi or "").strip() or (title or "").strip() or paper_id
    fetcher = SciHubFetcher(base_url=scihub_base_url, output_dir=save_path)
    fallback_result = await asyncio.to_thread(fetcher.download_pdf, fallback_identifier)
    if fallback_result:
        return fallback_result

    return "Download failed after OA fallback chain and Sci-Hub fallback. Details: " + " | ".join(attempt_errors)


@mcp.tool()
async def read_crossref_paper(paper_id: str, save_path: str = DEFAULT_SAVE_PATH) -> str:
    """Attempt to read and extract text content from a CrossRef paper.

    Args:
        paper_id: CrossRef DOI (e.g., '10.1038/nature12373').
        save_path: Directory where the PDF is/will be saved (default: <WORK_DIR>/downloads).
    Returns:
        str: Message indicating that direct paper reading is not supported.

    Note:
        CrossRef is a citation database and doesn't provide direct paper content.
        Use the DOI to access the paper through the publisher's website.
    """
    return crossref_searcher.read_paper(paper_id, save_path)


@mcp.tool()
async def search_openalex(query: str, max_results: int = 10) -> list[dict]:
    """Search academic papers from OpenAlex.

    Args:
        query: Search query string (e.g., 'machine learning').
        max_results: Maximum number of papers to return (default: 10).
    Returns:
        List of paper metadata in dictionary format.
    """
    papers = await async_search(openalex_searcher, query, max_results)
    return papers if papers else []


@mcp.tool()
async def search_pmc(query: str, max_results: int = 10) -> list[dict]:
    """Search academic papers from PubMed Central (PMC).

    Args:
        query: Search query string (e.g., 'machine learning').
        max_results: Maximum number of papers to return (default: 10).
    Returns:
        List of paper metadata in dictionary format.
    """
    papers = await async_search(pmc_searcher, query, max_results)
    return papers if papers else []


@mcp.tool()
async def search_core(query: str, max_results: int = 10) -> list[dict]:
    """Search academic papers from CORE.

    Args:
        query: Search query string (e.g., 'machine learning').
        max_results: Maximum number of papers to return (default: 10).
    Returns:
        List of paper metadata in dictionary format.
    """
    papers = await async_search(core_searcher, query, max_results)
    return papers if papers else []


@mcp.tool()
async def search_europepmc(query: str, max_results: int = 10) -> list[dict]:
    """Search academic papers from Europe PMC.

    Args:
        query: Search query string (e.g., 'machine learning').
        max_results: Maximum number of papers to return (default: 10).
    Returns:
        List of paper metadata in dictionary format.
    """
    papers = await async_search(europepmc_searcher, query, max_results)
    return papers if papers else []


@mcp.tool()
async def search_dblp(query: str, max_results: int = 10) -> list[dict]:
    """Search academic papers from dblp computer science bibliography.

    Args:
        query: Search query string (e.g., 'machine learning').
        max_results: Maximum number of papers to return (default: 10).
    Returns:
        List of paper metadata in dictionary format.
    """
    papers = await async_search(dblp_searcher, query, max_results)
    return papers if papers else []


@mcp.tool()
async def search_openaire(query: str, max_results: int = 10) -> list[dict]:
    """Search academic papers from OpenAIRE European Open Access infrastructure.

    Args:
        query: Search query string (e.g., 'machine learning').
        max_results: Maximum number of papers to return (default: 10).
    Returns:
        List of paper metadata in dictionary format.
    """
    papers = await async_search(openaire_searcher, query, max_results)
    return papers if papers else []


@mcp.tool()
async def search_citeseerx(query: str, max_results: int = 10) -> list[dict]:
    """Search academic papers from CiteSeerX digital library.

    Args:
        query: Search query string (e.g., 'machine learning').
        max_results: Maximum number of papers to return (default: 10).
    Returns:
        List of paper metadata in dictionary format.
    """
    papers = await async_search(citeseerx_searcher, query, max_results)
    return papers if papers else []


@mcp.tool()
async def search_doaj(query: str, max_results: int = 10) -> list[dict]:
    """Search academic papers from DOAJ (Directory of Open Access Journals).

    Args:
        query: Search query string (e.g., 'machine learning').
        max_results: Maximum number of papers to return (default: 10).
    Returns:
        List of paper metadata in dictionary format.
    """
    papers = await async_search(doaj_searcher, query, max_results)
    return papers if papers else []


@mcp.tool()
async def search_base(query: str, max_results: int = 10) -> list[dict]:
    """Search academic papers from BASE (Bielefeld Academic Search Engine).

    Args:
        query: Search query string (e.g., 'machine learning').
        max_results: Maximum number of papers to return (default: 10).
    Returns:
        List of paper metadata in dictionary format.
    """
    papers = await async_search(base_searcher, query, max_results)
    return papers if papers else []


@mcp.tool()
async def search_zenodo(query: str, max_results: int = 10) -> list[dict]:
    """Search academic papers from Zenodo open repository.

    Args:
        query: Search query string (e.g., 'machine learning').
        max_results: Maximum number of papers to return (default: 10).
    Returns:
        List of paper metadata in dictionary format.
    """
    papers = await async_search(zenodo_searcher, query, max_results)
    return papers if papers else []


@mcp.tool()
async def search_hal(query: str, max_results: int = 10) -> list[dict]:
    """Search academic papers from HAL open archive.

    Args:
        query: Search query string (e.g., 'machine learning').
        max_results: Maximum number of papers to return (default: 10).
    Returns:
        List of paper metadata in dictionary format.
    """
    papers = await async_search(hal_searcher, query, max_results)
    return papers if papers else []


@mcp.tool()
async def search_ssrn(query: str, max_results: int = 10) -> list[dict]:
    """Search metadata records from SSRN.

    Note: SSRN connector is metadata-only and does not support direct PDF download.

    Args:
        query: Search query string (e.g., 'machine learning').
        max_results: Maximum number of papers to return (default: 10).
    Returns:
        List of paper metadata in dictionary format.
    """
    papers = await async_search(ssrn_searcher, query, max_results)
    return papers if papers else []


@mcp.tool()
async def search_unpaywall(query: str, max_results: int = 10) -> list[dict]:
    """Lookup a DOI via Unpaywall and return OA metadata.

    Unpaywall is DOI-centric and does not support generic keyword search.
    This tool extracts the first DOI from `query` and returns at most one record.

    Args:
        query: DOI string or text containing a DOI.
        max_results: Kept for API consistency; Unpaywall returns max 1 record.
    Returns:
        List with one paper metadata dict when DOI is resolvable, else empty list.
    """
    papers = await async_search(unpaywall_searcher, query, max_results)
    return papers if papers else []


@mcp.tool()
async def read_dblp_paper(paper_id: str, save_path: str = DEFAULT_SAVE_PATH) -> str:
    """Attempt to read and extract text content from a dblp paper.

    Note: dblp doesn't provide direct paper content access.
    This function returns an informative message.

    Args:
        paper_id: dblp paper identifier.
        save_path: Directory where the PDF would be saved (unused).
    Returns:
        str: Message indicating that direct paper reading is not supported.
    """
    return dblp_searcher.read_paper(paper_id, save_path)


@mcp.tool()
async def download_dblp(paper_id: str, save_path: str = DEFAULT_SAVE_PATH) -> str:
    """Download PDF for a paper from dblp.

    Note: dblp doesn't provide direct PDF access.
    This function returns an informative message.

    Args:
        paper_id: dblp paper identifier.
        save_path: Directory to save the PDF (default: <WORK_DIR>/downloads).
    Returns:
        str: Message indicating that direct PDF download is not supported.
    """
    return dblp_searcher.download_pdf(paper_id, save_path)


@mcp.tool()
async def read_openaire_paper(paper_id: str, save_path: str = DEFAULT_SAVE_PATH) -> str:
    """Attempt to read and extract text content from an OpenAIRE paper.

    Args:
        paper_id: OpenAIRE paper identifier.
        save_path: Directory where the PDF is/will be saved (default: <WORK_DIR>/downloads).
    Returns:
        str: Extracted text or error message.
    """
    return openaire_searcher.read_paper(paper_id, save_path)


@mcp.tool()
async def download_openaire(paper_id: str, save_path: str = DEFAULT_SAVE_PATH) -> str:
    """Download PDF for a paper from OpenAIRE.

    Args:
        paper_id: OpenAIRE paper identifier.
        save_path: Directory to save the PDF (default: <WORK_DIR>/downloads).
    Returns:
        str: Path to downloaded PDF or error message.
    """
    return openaire_searcher.download_pdf(paper_id, save_path)


@mcp.tool()
async def read_citeseerx_paper(paper_id: str, save_path: str = DEFAULT_SAVE_PATH) -> str:
    """Read and extract text content from a CiteSeerX paper.

    Args:
        paper_id: CiteSeerX paper identifier.
        save_path: Directory where the PDF is/will be saved (default: <WORK_DIR>/downloads).
    Returns:
        str: Extracted text or fallback abstract/error message.
    """
    return citeseerx_searcher.read_paper(paper_id, save_path)


@mcp.tool()
async def download_citeseerx(paper_id: str, save_path: str = DEFAULT_SAVE_PATH) -> str:
    """Download PDF for a paper from CiteSeerX.

    Args:
        paper_id: CiteSeerX paper identifier.
        save_path: Directory to save the PDF (default: <WORK_DIR>/downloads).
    Returns:
        str: Path to downloaded PDF or error message.
    """
    return citeseerx_searcher.download_pdf(paper_id, save_path)


@mcp.tool()
async def read_doaj_paper(paper_id: str, save_path: str = DEFAULT_SAVE_PATH) -> str:
    """Read and extract text content from a DOAJ paper.

    Args:
        paper_id: DOAJ paper identifier.
        save_path: Directory where the PDF is/will be saved (default: <WORK_DIR>/downloads).
    Returns:
        str: Extracted text content.
    """
    return doaj_searcher.read_paper(paper_id, save_path)


@mcp.tool()
async def download_doaj(paper_id: str, save_path: str = DEFAULT_SAVE_PATH) -> str:
    """Download PDF for a paper from DOAJ.

    Args:
        paper_id: DOAJ paper identifier.
        save_path: Directory to save the PDF (default: <WORK_DIR>/downloads).
    Returns:
        str: Path to downloaded PDF.
    """
    return doaj_searcher.download_pdf(paper_id, save_path)


@mcp.tool()
async def read_base_paper(paper_id: str, save_path: str = DEFAULT_SAVE_PATH) -> str:
    """Read and extract text content from a BASE paper.

    Args:
        paper_id: BASE paper identifier.
        save_path: Directory where the PDF is/will be saved (default: <WORK_DIR>/downloads).
    Returns:
        str: Extracted text content.
    """
    return base_searcher.read_paper(paper_id, save_path)


@mcp.tool()
async def download_base(paper_id: str, save_path: str = DEFAULT_SAVE_PATH) -> str:
    """Download PDF for a paper from BASE.

    Args:
        paper_id: BASE paper identifier.
        save_path: Directory to save the PDF (default: <WORK_DIR>/downloads).
    Returns:
        str: Path to downloaded PDF.
    """
    return base_searcher.download_pdf(paper_id, save_path)


@mcp.tool()
async def read_zenodo_paper(paper_id: str, save_path: str = DEFAULT_SAVE_PATH) -> str:
    """Read and extract text content from a Zenodo paper.

    Args:
        paper_id: Zenodo paper identifier.
        save_path: Directory where the PDF is/will be saved (default: <WORK_DIR>/downloads).
    Returns:
        str: Extracted text content.
    """
    return zenodo_searcher.read_paper(paper_id, save_path)


@mcp.tool()
async def download_zenodo(paper_id: str, save_path: str = DEFAULT_SAVE_PATH) -> str:
    """Download PDF for a paper from Zenodo.

    Args:
        paper_id: Zenodo paper identifier.
        save_path: Directory to save the PDF (default: <WORK_DIR>/downloads).
    Returns:
        str: Path to downloaded PDF.
    """
    return zenodo_searcher.download_pdf(paper_id, save_path)


@mcp.tool()
async def read_hal_paper(paper_id: str, save_path: str = DEFAULT_SAVE_PATH) -> str:
    """Read and extract text content from a HAL paper.

    Args:
        paper_id: HAL paper identifier.
        save_path: Directory where the PDF is/will be saved (default: <WORK_DIR>/downloads).
    Returns:
        str: Extracted text content.
    """
    return hal_searcher.read_paper(paper_id, save_path)


@mcp.tool()
async def download_hal(paper_id: str, save_path: str = DEFAULT_SAVE_PATH) -> str:
    """Download PDF for a paper from HAL.

    Args:
        paper_id: HAL paper identifier.
        save_path: Directory to save the PDF (default: <WORK_DIR>/downloads).
    Returns:
        str: Path to downloaded PDF.
    """
    return hal_searcher.download_pdf(paper_id, save_path)


@mcp.tool()
async def read_ssrn_paper(paper_id: str, save_path: str = DEFAULT_SAVE_PATH) -> str:
    """Read paper content from SSRN.

    Note: SSRN connector is metadata-only and read is not supported.

    Args:
        paper_id: SSRN paper identifier.
        save_path: Directory where the PDF is/will be saved (unused).
    Returns:
        str: Error message from metadata-only SSRN connector.
    """
    return ssrn_searcher.read_paper(paper_id, save_path)


@mcp.tool()
async def download_ssrn(paper_id: str, save_path: str = DEFAULT_SAVE_PATH) -> str:
    """Download PDF for a paper from SSRN.

    Note: SSRN connector is metadata-only and download is not supported.

    Args:
        paper_id: SSRN paper identifier.
        save_path: Directory to save the PDF (unused).
    Returns:
        str: Error message from metadata-only SSRN connector.
    """
    return ssrn_searcher.download_pdf(paper_id, save_path)


@mcp.tool()
async def read_openalex_paper(paper_id: str, save_path: str = DEFAULT_SAVE_PATH) -> str:
    """Attempt to read and extract text content from an OpenAlex paper.

    Args:
        paper_id: OpenAlex paper ID.
        save_path: Directory where the PDF is/will be saved (default: <WORK_DIR>/downloads).
    Returns:
        str: Message indicating that direct paper reading is not supported natively.
    """
    return openalex_searcher.read_paper(paper_id, save_path)


@mcp.tool()
async def download_openalex(paper_id: str, save_path: str = DEFAULT_SAVE_PATH) -> str:
    """Download PDF for a paper from OpenAlex.

    Args:
        paper_id: OpenAlex paper ID.
        save_path: Directory to save the PDF (default: <WORK_DIR>/downloads).
    Returns:
        str: Error message, typically OpenAlex relies on extracted pdf_url instead of direct downloads.
    """
    return await asyncio.to_thread(openalex_searcher.download_pdf, paper_id, save_path)


# ---------------------------------------------------------------------------
# Optional IEEE Xplore tools — registered only when API key is set
# ---------------------------------------------------------------------------
if ieee_searcher is not None:
    @mcp.tool()
    async def search_ieee(query: str, max_results: int = 10) -> list[dict]:
        """Search IEEE Xplore for papers.  Requires paper_toolkit_mcp_IEEE_API_KEY (or IEEE_API_KEY).

        Args:
            query: Search query string.
            max_results: Maximum number of results (default: 10).
        Returns:
            List of paper dicts from IEEE Xplore.
        """
        return await async_search(ieee_searcher, query, max_results)

    @mcp.tool()
    async def download_ieee(paper_id: str, save_path: str = DEFAULT_SAVE_PATH) -> str:
        """Download a PDF from IEEE Xplore.  Requires paper_toolkit_mcp_IEEE_API_KEY (or IEEE_API_KEY) and institutional access.

        Args:
            paper_id: IEEE Xplore paper identifier.
            save_path: Directory to save the PDF (default: <WORK_DIR>/downloads).
        Returns:
            str: Path to saved PDF or error message.
        """
        assert ieee_searcher is not None
        return await asyncio.to_thread(ieee_searcher.download_pdf, paper_id, save_path)

    @mcp.tool()
    async def read_ieee_paper(paper_id: str, save_path: str = DEFAULT_SAVE_PATH) -> str:
        """Download and read an IEEE Xplore paper.  Requires paper_toolkit_mcp_IEEE_API_KEY (or IEEE_API_KEY).

        Args:
            paper_id: IEEE Xplore paper identifier.
            save_path: Directory where the PDF is/will be saved (default: <WORK_DIR>/downloads).
        Returns:
            str: Extracted text content.
        """
        assert ieee_searcher is not None
        return ieee_searcher.read_paper(paper_id, save_path)


# ---------------------------------------------------------------------------
# Optional ACM Digital Library tools — registered only when API key is set
# ---------------------------------------------------------------------------
if acm_searcher is not None:
    @mcp.tool()
    async def search_acm(query: str, max_results: int = 10) -> list[dict]:
        """Search ACM Digital Library for papers.  Requires paper_toolkit_mcp_ACM_API_KEY (or ACM_API_KEY).

        Args:
            query: Search query string.
            max_results: Maximum number of results (default: 10).
        Returns:
            List of paper dicts from ACM DL.
        """
        return await async_search(acm_searcher, query, max_results)

    @mcp.tool()
    async def download_acm(paper_id: str, save_path: str = DEFAULT_SAVE_PATH) -> str:
        """Download a PDF from ACM Digital Library.  Requires paper_toolkit_mcp_ACM_API_KEY (or ACM_API_KEY) and institutional access.

        Args:
            paper_id: ACM DL paper identifier.
            save_path: Directory to save the PDF (default: <WORK_DIR>/downloads).
        Returns:
            str: Path to saved PDF or error message.
        """
        assert acm_searcher is not None
        return await asyncio.to_thread(acm_searcher.download_pdf, paper_id, save_path)

    @mcp.tool()
    async def read_acm_paper(paper_id: str, save_path: str = DEFAULT_SAVE_PATH) -> str:
        """Download and read an ACM Digital Library paper.  Requires paper_toolkit_mcp_ACM_API_KEY (or ACM_API_KEY).

        Args:
            paper_id: ACM DL paper identifier.
            save_path: Directory where the PDF is/will be saved (default: <WORK_DIR>/downloads).
        Returns:
            str: Extracted text content.
        """
        assert acm_searcher is not None
        return acm_searcher.read_paper(paper_id, save_path)


# ---------------------------------------------------------------------------
# NEW: Manuscript processing tools
# ---------------------------------------------------------------------------

@mcp.tool()
async def process_manuscript(
    markdown_path: str,
    citation_style: str = "gb7714",
    output_dir: str | None = None,
    generate_docx: bool = True,
    include_bibtex: bool = True,
    include_ris: bool = True,
    cache_ttl_hours: int = 24,
) -> dict[str, Any]:
    """Process a Markdown manuscript with citation placeholders and generate formatted outputs.

    Supported placeholder formats:
    - [@doi:10.1234/example]
    - [@pmid:12345678]
    - [@arxiv:2106.12345]
    - [@title:Paper Title Here]

    Args:
        markdown_path: Path to the input Markdown file.
        citation_style: Citation style for reference list (gb7714, apa, ieee).
        output_dir: Output directory (default: same as input file).
        generate_docx: Whether to generate Word document via pandoc.
        include_bibtex: Whether to generate BibTeX file.
        include_ris: Whether to generate RIS file for Zotero import.
        cache_ttl_hours: Cache TTL in hours for search results.

    Returns:
        Dict with paths to generated files and processing report.
    """
    from .reference import get_paper_by_identifier

    cache = SearchCache(ttl_hours=cache_ttl_hours)

    if not os.path.exists(markdown_path):
        return {"error": f"File not found: {markdown_path}"}

    with open(markdown_path, encoding="utf-8") as f:
        markdown_content = f.read()

    if output_dir is None:
        output_dir = os.path.dirname(markdown_path) or get_work_dir()
    os.makedirs(output_dir, exist_ok=True)

    base_name = os.path.splitext(os.path.basename(markdown_path))[0]

    placeholders = parse_citation_placeholders(markdown_content)
    if not placeholders:
        return {
            "status": "no_citations_found",
            "message": "No citation placeholders found in the manuscript.",
            "output_files": {},
        }

    unique_citations = {}
    for p in placeholders:
        key = f"{p['type']}:{p['identifier']}"
        if key not in unique_citations:
            unique_citations[key] = p

    papers = []
    failed = []

    for key, placeholder in unique_citations.items():
        try:
            paper = await asyncio.to_thread(
                get_paper_by_identifier,
                placeholder["type"],
                placeholder["identifier"],
                cache=cache,
            )
            if paper:
                paper["citation_key"] = key
                papers.append(paper)
            else:
                failed.append({
                    "placeholder": placeholder["full_match"],
                    "identifier": placeholder["identifier"],
                    "type": placeholder["type"],
                    "error": "Paper not found or API failed",
                })
        except Exception as e:
            failed.append({
                "placeholder": placeholder["full_match"],
                "identifier": placeholder["identifier"],
                "type": placeholder["type"],
                "error": str(e),
            })

    output_files = {}

    if papers:
        ref_list = generate_reference_list(papers, style=citation_style)

        processed = process_manuscript_text(markdown_content, papers)

        formatted_md_path = os.path.join(output_dir, f"{base_name}_formatted.md")
        with open(formatted_md_path, "w", encoding="utf-8") as f:
            f.write(processed["formatted_text"])
        output_files["formatted_markdown"] = formatted_md_path

        ref_list_path = os.path.join(output_dir, f"{base_name}_references.txt")
        with open(ref_list_path, "w", encoding="utf-8") as f:
            f.write(f"## References\n\n{ref_list}")
        output_files["reference_list"] = ref_list_path

        if include_bibtex:
            bib_content = generate_bibtex(papers)
            bib_path = os.path.join(output_dir, "refs.bib")
            with open(bib_path, "w", encoding="utf-8") as f:
                f.write(bib_content)
            output_files["bibtex"] = bib_path

        if include_ris:
            ris_content = generate_ris(papers)
            ris_path = os.path.join(output_dir, "refs.ris")
            with open(ris_path, "w", encoding="utf-8") as f:
                f.write(ris_content)
            output_files["ris"] = ris_path

        if generate_docx:
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
                    csl_name = style_to_csl.get(citation_style, "chinese-gb7714-2015-numeric.csl")
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
        "citation_style": citation_style,
    }
    if failed:
        report["failed_items"] = failed

    return {
        "status": "completed",
        "report": report,
        "output_files": output_files,
    }


@mcp.tool()
async def get_paper_metadata(
    identifier: str,
    cache_ttl_hours: int = 24,
) -> dict[str, Any]:
    """Get full metadata for a single paper by DOI, PMID, or arXiv ID.

    Args:
        identifier: Paper identifier (e.g., 'doi:10.1038/nature12373', 'pmid:12345', 'arxiv:2106.12345').
        cache_ttl_hours: Cache TTL in hours.

    Returns:
        Paper metadata dict or error.
    """
    from .reference import get_paper_by_identifier

    cache = SearchCache(ttl_hours=cache_ttl_hours)

    parts = identifier.split(":", 1)
    if len(parts) != 2:
        return {"error": "Invalid identifier format. Use 'type:id' (e.g., 'doi:10.1234')"}

    id_type, id_value = parts[0].strip().lower(), parts[1].strip()

    try:
        paper = await asyncio.to_thread(
            get_paper_by_identifier, id_type, id_value, cache=cache
        )
        if paper:
            return paper
        return {"error": f"Paper not found: {identifier}"}
    except Exception as e:
        return {"error": str(e)}


@mcp.tool()
async def export_references(
    identifiers: list[str],
    format: str = "bibtex",
    style: str = "gb7714",
    output_path: str | None = None,
    cache_ttl_hours: int = 24,
) -> str:
    """Export references for multiple papers in the specified format.

    Args:
        identifiers: List of paper identifiers (e.g., ['doi:10.1234', 'pmid:5678']).
        format: Output format (bibtex, ris, text).
        style: Citation style for text format (gb7714, apa, ieee).
        output_path: Optional file path to save output.
        cache_ttl_hours: Cache TTL in hours.

    Returns:
        Formatted references string or saved file path.
    """
    from .reference import get_paper_by_identifier

    cache = SearchCache(ttl_hours=cache_ttl_hours)
    papers = []

    for identifier in identifiers:
        parts = identifier.split(":", 1)
        if len(parts) != 2:
            continue
        id_type, id_value = parts[0].strip().lower(), parts[1].strip()
        try:
            paper = await asyncio.to_thread(
                get_paper_by_identifier, id_type, id_value, cache=cache
            )
            if paper:
                papers.append(paper)
        except Exception as e:
            logger.warning(f"Failed to fetch paper {id_value}: {e}")

    if not papers:
        return "No papers found for the given identifiers."

    if format == "bibtex":
        content = generate_bibtex(papers)
    elif format == "ris":
        content = generate_ris(papers)
    elif format == "text":
        content = generate_reference_list(papers, style=style)
    else:
        return f"Unsupported format: {format}. Use bibtex, ris, or text."

    if output_path:
        os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(content)
        return f"References saved to: {output_path}"

    return content


@mcp.tool()
async def cache_list() -> dict[str, Any]:
    """List all cached search results.

    Returns:
        Dict with cache statistics and list of cached items.
    """
    cache = SearchCache()
    return {
        "stats": cache.get_stats(),
        "items": cache.list_cache(),
    }


@mcp.tool()
async def cache_clear() -> dict[str, Any]:
    """Clear all cached search results.

    Returns:
        Dict with number of cleared entries.
    """
    cache = SearchCache()
    count = cache.clear()
    return {
        "status": "cleared",
        "entries_cleared": count,
    }


def main():
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
