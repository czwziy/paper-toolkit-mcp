# paper_toolkit_mcp/tools/download.py
"""Download and read MCP tools."""
from __future__ import annotations

import asyncio
import logging
import os
from typing import TYPE_CHECKING

import httpx

from .._helpers import _safe_filename

if TYPE_CHECKING:
    from ..academic_platforms.unpaywall import UnpaywallResolver
    from ..storage import PaperStorage

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Module-level state — set by register()
# ---------------------------------------------------------------------------
_storage: PaperStorage | None = None
_searchers: dict = {}
_unpaywall_resolver: UnpaywallResolver | None = None
_default_save_path = ""


# ---------------------------------------------------------------------------
# Internal download helpers
# ---------------------------------------------------------------------------

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
        ("openaire", _searchers.get("openaire")),
        ("core", _searchers.get("core")),
        ("europepmc", _searchers.get("europepmc")),
        ("pmc", _searchers.get("pmc")),
    ]

    query_candidates = [(doi or "").strip(), (title or "").strip()]
    query_candidates = [candidate for candidate in query_candidates if candidate]
    if not query_candidates:
        return None, "no DOI/title provided for repository fallback"

    repository_errors: list[str] = []

    for repo_name, searcher in repository_searchers:
        if searcher is None:
            continue
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


# ---------------------------------------------------------------------------
# Individual source download/read helpers (internal)
# ---------------------------------------------------------------------------

async def download_arxiv(paper_id: str, save_path: str = "") -> str:
    """Download PDF of an arXiv paper."""
    return await asyncio.to_thread(_searchers["arxiv"].download_pdf, paper_id, save_path or _default_save_path)


async def download_pubmed(paper_id: str, save_path: str = "") -> str:
    """Attempt to download PDF of a PubMed paper."""
    try:
        return _searchers["pubmed"].download_pdf(paper_id, save_path or _default_save_path)
    except NotImplementedError as e:
        return str(e)


async def download_medrxiv(paper_id: str, save_path: str = "") -> str:
    """Download PDF of a medRxiv paper."""
    return _searchers["medrxiv"].download_pdf(paper_id, save_path or _default_save_path)


async def read_arxiv_paper(paper_id: str, save_path: str = "") -> str:
    """Read and extract text content from an arXiv paper PDF."""
    try:
        return _searchers["arxiv"].read_paper(paper_id, save_path or _default_save_path)
    except Exception as e:
        print(f"Error reading paper {paper_id}: {e}")
        return ""


async def read_pubmed_paper(paper_id: str, save_path: str = "") -> str:
    """Read and extract text content from a PubMed paper."""
    return _searchers["pubmed"].read_paper(paper_id, save_path or _default_save_path)


async def read_medrxiv_paper(paper_id: str, save_path: str = "") -> str:
    """Read and extract text content from a medRxiv paper PDF."""
    try:
        return _searchers["medrxiv"].read_paper(paper_id, save_path or _default_save_path)
    except Exception as e:
        print(f"Error reading paper {paper_id}: {e}")
        return ""


async def download_semantic(paper_id: str, save_path: str = "./downloads") -> str:
    """Download PDF of a Semantic Scholar paper."""
    return _searchers["semantic"].download_pdf(paper_id, save_path)


async def read_semantic_paper(paper_id: str, save_path: str = "./downloads") -> str:
    """Read and extract text content from a Semantic Scholar paper."""
    try:
        return _searchers["semantic"].read_paper(paper_id, save_path)
    except Exception as e:
        print(f"Error reading paper {paper_id}: {e}")
        return ""


async def download_crossref(paper_id: str, save_path: str = "") -> str:
    """Attempt to download PDF of a CrossRef paper."""
    try:
        return _searchers["crossref"].download_pdf(paper_id, save_path or _default_save_path)
    except NotImplementedError as e:
        return str(e)


async def read_crossref_paper(paper_id: str, save_path: str = "") -> str:
    """Attempt to read and extract text content from a CrossRef paper."""
    return _searchers["crossref"].read_paper(paper_id, save_path or _default_save_path)


async def read_dblp_paper(paper_id: str, save_path: str = "") -> str:
    """Attempt to read and extract text content from a dblp paper."""
    return _searchers["dblp"].read_paper(paper_id, save_path or _default_save_path)


async def download_dblp(paper_id: str, save_path: str = "") -> str:
    """Download PDF for a paper from dblp."""
    return _searchers["dblp"].download_pdf(paper_id, save_path or _default_save_path)


async def read_openalex_paper(paper_id: str, save_path: str = "") -> str:
    """Attempt to read and extract text content from an OpenAlex paper."""
    return _searchers["openalex"].read_paper(paper_id, save_path or _default_save_path)


async def download_openalex(paper_id: str, save_path: str = "") -> str:
    """Download PDF for a paper from OpenAlex."""
    return await asyncio.to_thread(_searchers["openalex"].download_pdf, paper_id, save_path or _default_save_path)


# ---------------------------------------------------------------------------
# MCP tools
# ---------------------------------------------------------------------------

async def download_paper(
    source: str,
    paper_id: str,
    doi: str = "",
    title: str = "",
    save_path: str = "",
    use_scihub: bool = True,
    scihub_base_url: str = "https://sci-hub.se",
) -> str:
    """Try source-native download, OA repositories, Unpaywall, then optional Sci-Hub.

    Args:
        source: Source name (arxiv, medrxiv, semantic, crossref, pubmed, pmc, dblp, openalex).
        paper_id: Source-native paper identifier.
        doi: Optional DOI used for repository/unpaywall/Sci-Hub fallback.
        title: Optional title used for repository/Sci-Hub fallback when DOI is unavailable.
        save_path: Directory to save downloaded files.
        use_scihub: Whether to fallback to Sci-Hub after OA attempts fail.
        scihub_base_url: Sci-Hub mirror URL for fallback.
    Returns:
        Download path on success or explanatory error message.
    """
    from ..academic_platforms.sci_hub import SciHubFetcher
    from ..storage import _paper_dedup_key

    assert _storage is not None, "register() not called"
    assert _unpaywall_resolver is not None, "register() not called"

    source_name = source.strip().lower()
    effective_save = save_path or _default_save_path

    # Check local PDF cache first — avoid re-downloading already-fetched papers.
    dedup_key = _paper_dedup_key({"doi": doi, "title": title, "paper_id": paper_id})
    local_pdf = _storage.get_local_pdf(dedup_key)
    if local_pdf:
        return local_pdf

    primary_downloaders = {
        "arxiv": _searchers["arxiv"].download_pdf,
        "medrxiv": _searchers["medrxiv"].download_pdf,
        "semantic": _searchers["semantic"].download_pdf,
        "pubmed": _searchers["pubmed"].download_pdf,
        "crossref": _searchers["crossref"].download_pdf,
        "pmc": _searchers["pmc"].download_pdf,
        "dblp": _searchers["dblp"].download_pdf,
        "openalex": _searchers["openalex"].download_pdf,
    }

    attempt_errors: list[str] = []
    primary_error = ""
    if source_name in primary_downloaders:
        try:
            primary_result = await asyncio.to_thread(primary_downloaders[source_name], paper_id, effective_save)
            if isinstance(primary_result, str) and os.path.exists(primary_result):
                _storage.set_local_pdf(dedup_key, primary_result)
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

    repository_result, repository_error = await _try_repository_fallback(doi, title, effective_save)
    if repository_result:
        _storage.set_local_pdf(dedup_key, repository_result)
        return repository_result
    if repository_error:
        attempt_errors.append(f"repositories: {repository_error}")

    normalized_doi = (doi or "").strip()
    if normalized_doi:
        unpaywall_url = await asyncio.to_thread(_unpaywall_resolver.resolve_best_pdf_url, normalized_doi)
        if unpaywall_url:
            unpaywall_result = await _download_from_url(unpaywall_url, effective_save, f"unpaywall_{normalized_doi}")
            if unpaywall_result:
                _storage.set_local_pdf(dedup_key, unpaywall_result)
                return unpaywall_result
            attempt_errors.append("unpaywall: resolved OA URL but download failed")
        else:
            attempt_errors.append("unpaywall: no OA URL found (or paper_toolkit_mcp_UNPAYWALL_EMAIL/UNPAYWALL_EMAIL missing)")
    else:
        attempt_errors.append("unpaywall: DOI not provided")

    if not use_scihub:
        return "Download failed after OA fallback chain. Details: " + " | ".join(attempt_errors)

    fallback_identifier = (doi or "").strip() or (title or "").strip() or paper_id
    fetcher = SciHubFetcher(base_url=scihub_base_url, output_dir=effective_save)
    fallback_result = await asyncio.to_thread(fetcher.download_pdf, fallback_identifier)
    if fallback_result:
        _storage.set_local_pdf(dedup_key, fallback_result)
        return fallback_result

    return "Download failed after OA fallback chain and Sci-Hub fallback. Details: " + " | ".join(attempt_errors)


async def download_by_cite_key(
    cite_key: str, save_path: str = ""
) -> str:
    """Download a paper's PDF using its cite_key.

    Looks up the paper in the local library by cite_key, checks for an
    existing local PDF, then falls back to download_paper.

    Args:
        cite_key: The paper's cite_key (e.g. 'Kxq') from search results.
        save_path: Directory to save the PDF (default: <WORK_DIR>/downloads).
    Returns:
        Path to the downloaded PDF, or an error message.
    """
    assert _storage is not None, "register() not called"
    paper = _storage.get_by_cite_key(cite_key)
    if not paper:
        return f"Error: cite_key '{cite_key}' not found in library. Search for the paper first."

    # Check local PDF cache
    dedup_key = paper["dedup_key"]
    local_pdf = _storage.get_local_pdf(dedup_key)
    if local_pdf:
        return local_pdf

    # Route to download_paper using stored metadata
    source = (paper.get("source") or "").split(",")[0].strip()
    return await download_paper(
        source=source,
        paper_id=paper.get("paper_id", ""),
        doi=paper.get("doi", ""),
        title=paper.get("title", ""),
        save_path=save_path,
    )


async def read_by_cite_key(
    cite_key: str, save_path: str = ""
) -> str:
    """Download and extract full text from a paper using its cite_key.

    Checks for cached full text first, then downloads the PDF and extracts
    text via pypdf. The extracted text is cached in the local library.

    Args:
        cite_key: The paper's cite_key (e.g. 'Kxq') from search results.
        save_path: Directory for PDF download (default: <WORK_DIR>/downloads).
    Returns:
        The extracted text content, or an error message.
    """
    assert _storage is not None, "register() not called"
    paper = _storage.get_by_cite_key(cite_key)
    if not paper:
        return f"Error: cite_key '{cite_key}' not found in library."

    dedup_key = paper["dedup_key"]

    # Check cached full text
    cached_text = _storage.get_fulltext(dedup_key)
    if cached_text:
        return cached_text

    # Download PDF
    pdf_path = await download_by_cite_key(cite_key, save_path)
    if not os.path.exists(pdf_path):
        return pdf_path  # error message from download_by_cite_key

    # Extract text
    try:
        from pypdf import PdfReader

        reader = PdfReader(pdf_path)
        text = "\n".join(
            page.extract_text() for page in reader.pages if page.extract_text()
        )
        _storage.set_fulltext(dedup_key, text)
        return text
    except Exception as exc:
        logger.warning("Failed to extract text from %s: %s", pdf_path, exc)
        return f"PDF downloaded to {pdf_path} but text extraction failed: {exc}"


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

def register(
    mcp,
    *,
    storage,
    searchers: dict,
    unpaywall_resolver,
    default_save_path: str,
):
    """Register download/read tools on the MCP server."""
    global _storage, _searchers, _unpaywall_resolver, _default_save_path
    _storage = storage
    _searchers = searchers
    _unpaywall_resolver = unpaywall_resolver
    _default_save_path = default_save_path

    mcp.tool()(download_paper)
    mcp.tool()(download_by_cite_key)
    mcp.tool()(read_by_cite_key)
