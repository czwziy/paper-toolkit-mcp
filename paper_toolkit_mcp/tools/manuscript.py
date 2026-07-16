# paper_toolkit_mcp/tools/manuscript.py
"""Manuscript processing, writing templates, and reference export MCP tools."""
import asyncio
import json
import logging
import os
import re
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Module-level state — set by register()
# ---------------------------------------------------------------------------
_default_cache_dir = ""
_storage = None  # PaperStorage instance, set by register()

# Packaged templates directory (shipped with the package as data files).
_PACKAGED_TEMPLATES_DIR = os.path.join(os.path.dirname(__file__), "..", "writing_templates")


def _get_user_templates_dir() -> str:
    """Resolve user templates directory (lazily, to avoid import-time config dependency)."""
    from ..config import get_work_dir
    return os.path.join(get_work_dir(), ".paper_toolkit", "writing_templates")


def _list_writing_templates() -> list[str]:
    """List all available writing template names (from packaged + user dirs)."""
    names: set[str] = set()
    for tpl_dir in (_PACKAGED_TEMPLATES_DIR, _get_user_templates_dir()):
        if os.path.isdir(tpl_dir):
            for f in os.listdir(tpl_dir):
                if f.endswith(".md"):
                    names.add(f[:-3])
    return sorted(names)


# ---------------------------------------------------------------------------
# MCP tools
# ---------------------------------------------------------------------------

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
    from ..cache import SearchCache
    from ..config import get_work_dir
    from ..pandoc_helper import convert_to_docx, pandoc_available
    from ..reference import (
        generate_bibtex,
        generate_reference_list,
        generate_ris,
        get_paper_by_identifier,
        parse_citation_placeholders,
        process_manuscript_text,
    )

    cache = SearchCache(cache_dir=_default_cache_dir, ttl_hours=cache_ttl_hours)

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
                    csl_dir = os.path.join(os.path.dirname(__file__), "..", "..", "csl")
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
    from ..cache import SearchCache
    from ..reference import get_paper_by_identifier

    cache = SearchCache(cache_dir=_default_cache_dir, ttl_hours=cache_ttl_hours)

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
    from ..cache import SearchCache
    from ..reference import (
        generate_bibtex,
        generate_reference_list,
        generate_ris,
        get_paper_by_identifier,
    )

    cache = SearchCache(cache_dir=_default_cache_dir, ttl_hours=cache_ttl_hours)
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
            logger.warning("Failed to fetch paper %s: %s", id_value, e)

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


async def get_writing_template(category: str = "") -> dict[str, Any]:
    """Get a writing template to guide academic paper writing.

    Templates contain structure rules, citation format requirements, and
    workflow guidance for specific paper types (e.g. nursing Chinese review).
    User-customized templates (in .paper_toolkit/writing_templates/) take
    priority over packaged defaults.

    Args:
        category: Template name (e.g. "nursing_chinese_review").
            If empty, lists all available templates.
    Returns:
        Dict with template content or available template list.
    """
    if not category:
        return {
            "available": _list_writing_templates(),
            "hint": "Pass a template name to get its full content.",
        }

    user_dir = _get_user_templates_dir()

    # Try user-customized version first, then fall back to packaged default
    for tpl_dir in (user_dir, _PACKAGED_TEMPLATES_DIR):
        path = os.path.join(tpl_dir, f"{category}.md")
        if os.path.isfile(path):
            try:
                with open(path, encoding="utf-8") as f:
                    content = f.read()
                return {
                    "category": category,
                    "content": content,
                    "source": "user" if tpl_dir == user_dir else "packaged",
                    "path": path,
                }
            except OSError as exc:
                return {"error": f"Failed to read template: {exc}"}

    return {
        "error": f"Template not found: {category}",
        "available": _list_writing_templates(),
    }


# ---------------------------------------------------------------------------
# cite_key based tools — work with papers.db cite_key references
# ---------------------------------------------------------------------------

_CITE_KEY_RE = re.compile(r"\[@([a-zA-Z0-9]+)\]")


def _extract_cite_keys(text: str) -> list[str]:
    """Extract unique cite_keys from text in order of first appearance.

    Matches patterns like [@Kxq], [@JHw], [@vEw].
    Returns a list of unique cite_keys in order of first appearance.
    """
    seen: set[str] = set()
    keys: list[str] = []
    for m in _CITE_KEY_RE.finditer(text):
        key = m.group(1)
        if key not in seen:
            seen.add(key)
            keys.append(key)
    return keys


def _paper_to_ref_dict(row: dict[str, Any]) -> dict[str, Any]:
    """Convert a papers.db row dict to a reference.py-compatible dict.

    papers.db stores authors/categories/keywords as JSON strings;
    reference.py expects authors as list[str] and year as a field.
    """
    authors = row.get("authors", "[]")
    if isinstance(authors, str):
        try:
            authors = json.loads(authors)
        except (json.JSONDecodeError, TypeError):
            authors = []
    if not isinstance(authors, list):
        authors = []

    # Extract year from published_date (format: "YYYY-MM-DD" or "YYYY")
    year = ""
    pub_date = row.get("published_date", "")
    if pub_date:
        year = pub_date[:4] if len(pub_date) >= 4 else pub_date

    return {
        "paper_id": row.get("paper_id", ""),
        "cite_key": row.get("cite_key", ""),
        "title": row.get("title", ""),
        "authors": authors,
        "year": year,
        "source": row.get("source", ""),
        "doi": row.get("doi", ""),
        "url": row.get("url", ""),
        "abstract": row.get("abstract", ""),
    }


def _format_author_year(paper: dict[str, Any]) -> str:
    """Format as '第一作者(年份)' for human review copy.

    For Chinese names, use the full first author name.
    For Western names, use 'Surname'.
    """
    authors = paper.get("authors", [])
    year = paper.get("year", "") or "n.d."
    if not authors:
        return f"Unknown({year})"

    first_author = str(authors[0]).strip()
    # Western name: "Given Family" → "Family"
    # Chinese name: keep full name
    parts = first_author.split()
    if len(parts) >= 2:
        # Heuristic: if the first part looks like a Western given name
        # (starts with uppercase, short), use the last part as surname
        surname = parts[-1]
    else:
        surname = first_author

    return f"{surname}({year})"


async def generate_ref_list(
    manuscript_path: str,
    citation_style: str = "gb7714",
    output_path: str | None = None,
) -> dict[str, Any]:
    """Generate a formatted reference list from a manuscript's cite_key citations.

    Scans the manuscript for [@cite_key] references, looks up each paper
    in the local papers.db database, and generates a formatted reference
    list appended to the manuscript or saved to a separate file.

    This tool is designed for the final stage of manuscript preparation,
    when the manuscript text is finalized and the reference list needs
    to be generated.

    Args:
        manuscript_path: Path to the manuscript Markdown file containing
            [@cite_key] citations (e.g., [@Kxq], [@JHw]).
        citation_style: Citation style for the reference list.
            One of "gb7714" (GB/T 7714-2015), "apa" (APA 7th), "ieee" (IEEE).
            Defaults to "gb7714".
        output_path: Optional path to save the output. If not provided,
            saves as "<manuscript_name>_with_refs.md" in the same directory.

    Returns:
        Dict with status, report, and output file path.
    """
    from ..reference import format_citation_gb7714, format_citation_apa, format_citation_ieee

    if _storage is None:
        return {"error": "Storage not initialized. This tool requires papers.db access."}

    if not os.path.exists(manuscript_path):
        return {"error": f"File not found: {manuscript_path}"}

    with open(manuscript_path, encoding="utf-8") as f:
        content = f.read()

    cite_keys = _extract_cite_keys(content)
    if not cite_keys:
        return {
            "status": "no_citations_found",
            "message": "No [@cite_key] references found in the manuscript.",
        }

    # Look up each cite_key in papers.db
    papers: list[dict[str, Any]] = []
    failed_keys: list[str] = []
    key_to_index: dict[str, int] = {}

    for key in cite_keys:
        row = _storage.get_by_cite_key(key)
        if row is None:
            failed_keys.append(key)
            continue
        paper = _paper_to_ref_dict(row)
        key_to_index[key] = len(papers) + 1  # 1-based numbering
        papers.append(paper)

    # Generate reference list
    formatters = {
        "gb7714": format_citation_gb7714,
        "apa": format_citation_apa,
        "ieee": format_citation_ieee,
    }
    formatter = formatters.get(citation_style, format_citation_gb7714)

    ref_lines: list[str] = []
    for i, paper in enumerate(papers, start=1):
        citation = formatter(paper)
        ref_lines.append(f"[{i}] {citation}")

    ref_section = "\n".join(ref_lines)

    # Replace [@cite_key] with [N] in the text
    processed_text = content
    for key, idx in key_to_index.items():
        # Replace all occurrences of [@key] with [idx]
        processed_text = processed_text.replace(f"[@{key}]", f"[{idx}]")

    # Append reference section
    processed_text += f"\n\n## 参考文献\n\n{ref_section}"

    # Determine output path
    if output_path is None:
        base_dir = os.path.dirname(manuscript_path) or "."
        base_name = os.path.splitext(os.path.basename(manuscript_path))[0]
        output_path = os.path.join(base_dir, f"{base_name}_with_refs.md")

    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(processed_text)

    report = {
        "total_cite_keys": len(cite_keys),
        "resolved": len(papers),
        "unresolved": len(failed_keys),
        "citation_style": citation_style,
    }
    if failed_keys:
        report["unresolved_keys"] = failed_keys

    return {
        "status": "completed",
        "report": report,
        "output_file": output_path,
    }


async def generate_human_review(
    manuscript_path: str,
    output_path: str | None = None,
) -> dict[str, Any]:
    """Generate a human-review copy with cite_keys replaced by searchable identifiers.

    Replaces each [@cite_key] in the manuscript with a human-readable and
    searchable reference marker in the format:
        [@第一作者(年份) DOI:10.xxxx/xxx]

    This allows human reviewers to:
    1. Quickly identify which paper is being cited
    2. Search for the paper using DOI or author-year combination
    3. Verify that citations are accurate and correctly attributed

    The original [@cite_key] format is machine-friendly but opaque to humans.
    This tool creates a parallel version for manual verification.

    Args:
        manuscript_path: Path to the manuscript Markdown file containing
            [@cite_key] citations.
        output_path: Optional path to save the output. If not provided,
            saves as "<manuscript_name>_human_review.md" in the same directory.

    Returns:
        Dict with status, report, and output file path.
    """
    if _storage is None:
        return {"error": "Storage not initialized. This tool requires papers.db access."}

    if not os.path.exists(manuscript_path):
        return {"error": f"File not found: {manuscript_path}"}

    with open(manuscript_path, encoding="utf-8") as f:
        content = f.read()

    cite_keys = _extract_cite_keys(content)
    if not cite_keys:
        return {
            "status": "no_citations_found",
            "message": "No [@cite_key] references found in the manuscript.",
        }

    # Build replacement map
    replacements: dict[str, str] = {}
    failed_keys: list[str] = []
    resolved_info: list[dict[str, str]] = []

    for key in cite_keys:
        row = _storage.get_by_cite_key(key)
        if row is None:
            failed_keys.append(key)
            replacements[key] = f"[@{key}⚠未找到]"
            continue

        paper = _paper_to_ref_dict(row)
        author_year = _format_author_year(paper)
        doi = paper.get("doi", "")

        if doi:
            human_marker = f"[@{author_year} DOI:{doi}]"
        else:
            # Fallback: use title snippet if no DOI
            title = paper.get("title", "")
            title_snippet = title[:30] + "..." if len(title) > 30 else title
            human_marker = f"[@{author_year} \"{title_snippet}\"]"

        replacements[key] = human_marker
        resolved_info.append({
            "cite_key": key,
            "author_year": author_year,
            "doi": doi,
            "title": paper.get("title", ""),
        })

    # Apply replacements
    processed_text = content
    for key, marker in replacements.items():
        processed_text = processed_text.replace(f"[@{key}]", marker)

    # Determine output path
    if output_path is None:
        base_dir = os.path.dirname(manuscript_path) or "."
        base_name = os.path.splitext(os.path.basename(manuscript_path))[0]
        output_path = os.path.join(base_dir, f"{base_name}_human_review.md")

    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(processed_text)

    report = {
        "total_cite_keys": len(cite_keys),
        "resolved": len(resolved_info),
        "unresolved": len(failed_keys),
    }
    if failed_keys:
        report["unresolved_keys"] = failed_keys
    if resolved_info:
        report["mapping"] = resolved_info

    return {
        "status": "completed",
        "report": report,
        "output_file": output_path,
    }


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

def register(mcp, *, default_cache_dir: str, storage=None):
    """Register manuscript processing tools on the MCP server."""
    global _default_cache_dir, _storage
    _default_cache_dir = default_cache_dir
    _storage = storage

    mcp.tool()(process_manuscript)
    mcp.tool()(get_paper_metadata)
    mcp.tool()(export_references)
    mcp.tool()(get_writing_template)
    mcp.tool()(generate_ref_list)
    mcp.tool()(generate_human_review)
