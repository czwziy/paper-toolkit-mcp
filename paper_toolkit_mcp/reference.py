"""
Reference management module for parsing citation placeholders and generating
formatted bibliographies in multiple citation styles.

Supports:
- Placeholder parsing for [@doi:...], [@pmid:...], [@arxiv:...], [@title:...]
- BibTeX and RIS format generation
- GB/T 7714-2015, APA 7th edition, and IEEE citation styles
"""

import logging
import re

logger = logging.getLogger(__name__)


def parse_citation_placeholders(text: str) -> list[dict]:
    """
    Parse citation placeholders from manuscript text.

    Recognizes patterns like:
        [@doi:10.1234/abc.def]
        [@pmid:12345678]
        [@arxiv:2106.12345]
        [@title:Some Paper Title]

    Args:
        text: The manuscript text containing citation placeholders.

    Returns:
        A list of dicts, each with keys:
            - type: The citation type ("doi", "pmid", "arxiv", "title").
            - identifier: The identifier value after the colon.
            - position: The start index of the match in the text.
            - full_match: The entire matched placeholder string.
    """
    pattern = r"\[@(doi|pmid|arxiv|title):([^\]]+)\]"
    results = []

    for match in re.finditer(pattern, text):
        results.append({
            "type": match.group(1),
            "identifier": match.group(2).strip(),
            "position": match.start(),
            "full_match": match.group(0),
        })

    return results


def generate_bibtex(papers: list[dict]) -> str:
    """
    Generate BibTeX formatted bibliography from a list of paper metadata.

    Args:
        papers: A list of dicts, each representing a paper with keys such as:
            - paper_id: Unique identifier used as the BibTeX key.
            - title: Paper title.
            - authors: List of author name strings.
            - year: Publication year (int or str).
            - doi: Digital Object Identifier (optional).
            - source: Journal or conference name (optional).
            - volume: Volume number (optional).
            - issue: Issue number (optional).
            - pages: Page range (optional).
            - url: URL (optional).

    Returns:
        A string containing the BibTeX entries.
    """
    entries = []

    for paper in papers:
        key = paper.get("paper_id", "unknown")
        title = _escape_bibtex(paper.get("title", ""))
        authors = _format_bibtex_authors(paper.get("authors", []))
        year = paper.get("year", "n.d.")

        lines = [
            f"@article{{{key},",
            f"  author = {{{authors}}},",
            f"  title = {{{title}}},",
            f"  year = {{{year}}},",
        ]

        source = paper.get("source", "")
        if source:
            lines.append(f"  journal = {{{_escape_bibtex(source)}}},")

        volume = paper.get("volume", "")
        if volume:
            lines.append(f"  volume = {{{volume}}},")

        issue = paper.get("issue", "")
        if issue:
            lines.append(f"  number = {{{issue}}},")

        pages = paper.get("pages", "")
        if pages:
            lines.append(f"  pages = {{{pages}}},")

        doi = paper.get("doi", "")
        if doi:
            lines.append(f"  doi = {{{doi}}},")

        url = paper.get("url", "")
        if url:
            lines.append(f"  url = {{{url}}},")

        lines[-1] = lines[-1].rstrip(",") + ","
        lines.append("}")

        entries.append("\n".join(lines))

    return "\n\n".join(entries)


def _escape_bibtex(text: str) -> str:
    """Escape special BibTeX characters."""
    return text.replace("{", "\\{").replace("}", "\\}")


def _format_bibtex_authors(authors: list[str]) -> str:
    """Format a list of author names for BibTeX (joined by ' and ')."""
    if not authors:
        return ""
    return " and ".join(_escape_bibtex(a) for a in authors)


def generate_ris(papers: list[dict]) -> str:
    """
    Generate RIS formatted bibliography from a list of paper metadata.

    RIS format is compatible with reference managers such as Zotero,
    Mendeley, and EndNote.

    Args:
        papers: A list of dicts, each representing a paper with keys such as:
            - paper_id: Unique identifier.
            - title: Paper title.
            - authors: List of author name strings.
            - year: Publication year.
            - doi: Digital Object Identifier (optional).
            - source: Journal or conference name (optional).
            - volume: Volume number (optional).
            - issue: Issue number (optional).
            - pages: Page range (optional).
            - url: URL (optional).
            - abstract: Abstract text (optional).
            - type: RIS document type override (optional).

    Returns:
        A string containing the RIS entries.
    """
    entries = []

    for paper in papers:
        ris_type = paper.get("type", "JOUR")
        lines = [f"TY  - {ris_type}"]

        title = paper.get("title", "")
        if title:
            lines.append(f"TI  - {title}")

        for author in paper.get("authors", []):
            lines.append(f"AU  - {author}")

        year = paper.get("year", "")
        if year:
            lines.append(f"PY  - {year}")

        source = paper.get("source", "")
        if source:
            lines.append(f"T2  - {source}")

        volume = paper.get("volume", "")
        if volume:
            lines.append(f"VL  - {volume}")

        issue = paper.get("issue", "")
        if issue:
            lines.append(f"IS  - {issue}")

        pages = paper.get("pages", "")
        if pages:
            lines.append(f"SP  - {pages}")

        doi = paper.get("doi", "")
        if doi:
            lines.append(f"DO  - {doi}")

        url = paper.get("url", "")
        if url:
            lines.append(f"UR  - {url}")

        abstract = paper.get("abstract", "")
        if abstract:
            lines.append(f"AB  - {abstract}")

        paper_id = paper.get("paper_id", "")
        if paper_id:
            lines.append(f"ID  - {paper_id}")

        lines.append("ER  -")
        entries.append("\n".join(lines))

    return "\n\n".join(entries)


def _normalize_authors(authors) -> list[str]:
    """Normalize authors input to a list of individual author name strings.

    Handles both list of strings and comma-separated string formats.
    """
    if isinstance(authors, str):
        return [a.strip() for a in authors.split(",") if a.strip()]
    if isinstance(authors, list):
        return [str(a).strip() for a in authors if str(a).strip()]
    return []


def _format_author_list_gb7714(authors, max_authors: int = 3) -> str:
    """
    Format author list according to GB/T 7714-2015 rules.

    Surname in full, given name abbreviated. If more than max_authors,
    list the first max_authors followed by ", et al." or ", 等.".
    """
    author_list = _normalize_authors(authors)
    if not author_list:
        return ""

    formatted = []
    for author in author_list:
        parts = author.split()
        if len(parts) == 1:
            formatted.append(parts[0].upper())
        elif len(parts) == 2:
            surname = parts[0].upper()
            initials = parts[1].upper()
            if len(initials) == 1:
                initials = initials + "."
            formatted.append(f"{surname} {initials}")
        else:
            surname = parts[0].upper()
            initials = "".join(p[0].upper() + "." for p in parts[1:])
            formatted.append(f"{surname} {initials}")

    if len(formatted) > max_authors:
        return ", ".join(formatted[:max_authors]) + ", et al."
    return ", ".join(formatted)


def _format_author_list_apa(authors) -> str:
    """Format author list according to APA 7th edition style."""
    author_list = _normalize_authors(authors)
    if not author_list:
        return ""

    formatted = []
    for author in author_list:
        parts = author.split()
        if len(parts) == 1:
            formatted.append(parts[0])
        elif len(parts) == 2:
            surname = parts[0]
            initials = parts[1]
            if len(initials) > 1:
                initials = ". ".join(list(initials)) + "."
            elif len(initials) == 1:
                initials = initials + "."
            formatted.append(f"{surname}, {initials}")
        else:
            surname = parts[0]
            initials = ". ".join(p + "." for p in parts[1:])
            formatted.append(f"{surname}, {initials}")

    if len(formatted) == 1:
        return formatted[0]
    if len(formatted) == 2:
        return f"{formatted[0]}, & {formatted[1]}"
    if len(formatted) <= 7:
        return ", ".join(formatted[:-1]) + ", & " + formatted[-1]
    return ", ".join(formatted[:6]) + ", ... " + formatted[-1]


def _format_author_list_ieee(authors) -> str:
    """Format author list according to IEEE style."""
    author_list = _normalize_authors(authors)
    if not author_list:
        return ""

    formatted = []
    for author in author_list:
        parts = author.split()
        if len(parts) == 1:
            formatted.append(parts[0])
        elif len(parts) == 2:
            initials = parts[1]
            surname = parts[0]
            if len(initials) > 1:
                initials = ". ".join(list(initials)) + "."
            elif len(initials) == 1:
                initials = initials + "."
            formatted.append(f"{initials} {surname}")
        else:
            initials = " ".join(p + "." for p in parts[1:])
            surname = parts[0]
            formatted.append(f"{initials} {surname}")

    if len(formatted) == 1:
        return formatted[0]
    if len(formatted) == 2:
        return f"{formatted[0]} and {formatted[1]}"
    return ", ".join(formatted[:-1]) + ", and " + formatted[-1]


def format_citation_gb7714(paper: dict) -> str:
    """
    Format a single paper in GB/T 7714-2015 numeric style.

    Args:
        paper: A dict with paper metadata (title, authors, year, source,
               volume, issue, pages, doi, url).

    Returns:
        A formatted citation string.
    """
    authors = _format_author_list_gb7714(paper.get("authors", []))
    title = paper.get("title", "")
    year = paper.get("year", "n.d.")
    source = paper.get("source", "")
    volume = paper.get("volume", "")
    issue = paper.get("issue", "")
    pages = paper.get("pages", "")
    doi = paper.get("doi", "")
    url = paper.get("url", "")

    citation = f"{authors}. {title}[J]. "

    if source:
        citation += f"{source}"

    if year:
        citation += f", {year}"

    if volume:
        citation += f", {volume}"
        if issue:
            citation += f"({issue})"

    if pages:
        citation += f": {pages}"

    citation += "."

    if doi:
        citation += f" DOI:{doi}."
    elif url:
        citation += f" Available from: {url}."

    return citation


def format_citation_apa(paper: dict) -> str:
    """
    Format a single paper in APA 7th edition style.

    Args:
        paper: A dict with paper metadata (title, authors, year, source,
               volume, issue, pages, doi, url).

    Returns:
        A formatted citation string.
    """
    authors = _format_author_list_apa(paper.get("authors", []))
    year = paper.get("year", "n.d.")
    title = paper.get("title", "")
    source = paper.get("source", "")
    volume = paper.get("volume", "")
    issue = paper.get("issue", "")
    pages = paper.get("pages", "")
    doi = paper.get("doi", "")
    url = paper.get("url", "")

    citation = f"{authors} ({year}). {title}. "

    if source:
        citation += f"*{source}*"

    if volume:
        citation += f", *{volume}*"
        if issue:
            citation += f"({issue})"

    if pages:
        citation += f", {pages}"

    citation += "."

    if doi:
        citation += f" https://doi.org/{doi}"
    elif url:
        citation += f" {url}"

    return citation


def format_citation_ieee(paper: dict) -> str:
    """
    Format a single paper in IEEE style.

    Args:
        paper: A dict with paper metadata (title, authors, year, source,
               volume, issue, pages, doi, url).

    Returns:
        A formatted citation string.
    """
    authors = _format_author_list_ieee(paper.get("authors", []))
    title = paper.get("title", "")
    source = paper.get("source", "")
    year = paper.get("year", "n.d.")
    volume = paper.get("volume", "")
    issue = paper.get("issue", "")
    pages = paper.get("pages", "")
    doi = paper.get("doi", "")
    url = paper.get("url", "")

    citation = f"{authors}, \"{title},\" "

    if source:
        citation += f"*{source}*"

    if volume:
        citation += f", vol. {volume}"
    if issue:
        citation += f", no. {issue}"
    if pages:
        citation += f", pp. {pages}"
    if year:
        citation += f", {year}"

    citation += "."

    if doi:
        citation += f" doi: {doi}."
    elif url:
        citation += f" [Online]. Available: {url}."

    return citation


def generate_reference_list(papers: list[dict], style: str = "gb7714") -> str:
    """
    Generate a complete numbered reference list in the specified citation style.

    Args:
        papers: A list of dicts, each representing a paper.
        style: Citation style identifier. One of "gb7714", "apa", "ieee".
               Defaults to "gb7714".

    Returns:
        A string with numbered reference entries.

    Raises:
        ValueError: If an unsupported style is provided.
    """
    formatters = {
        "gb7714": format_citation_gb7714,
        "apa": format_citation_apa,
        "ieee": format_citation_ieee,
    }

    if style not in formatters:
        raise ValueError(
            f"Unsupported citation style '{style}'. "
            f"Supported styles: {', '.join(formatters.keys())}"
        )

    formatter = formatters[style]
    lines = []

    for i, paper in enumerate(papers, start=1):
        citation = formatter(paper)
        lines.append(f"[{i}] {citation}")

    return "\n".join(lines)


def process_manuscript(
    text: str, papers: list[dict], style: str = "gb7714"
) -> dict:
    """
    Process manuscript text by replacing citation placeholders with numbered
    citations and generating a formatted reference list.

    This function:
    1. Parses all [@type:identifier] placeholders from the text.
    2. Builds a mapping from (type, identifier) to paper index.
    3. Replaces each placeholder with a numbered citation like [1].
    4. Generates a complete reference list in the chosen style.

    Args:
        text: The manuscript text containing citation placeholders.
        papers: A list of dicts, each representing a paper. Each paper should
                have at minimum a paper_id. It may also have type-specific
                fields like "doi", "pmid", "arxiv", or "title" for matching.
        style: Citation style for the reference list. One of "gb7714", "apa",
               "ieee". Defaults to "gb7714".

    Returns:
        A dict with keys:
            - processed_text: The manuscript text with placeholders replaced
              by numbered citations.
            - reference_list: The formatted reference list string.
            - citation_map: A dict mapping placeholder strings to their
              assigned reference numbers.
            - unresolved: A list of placeholders that could not be matched
              to any paper.
    """
    placeholders = parse_citation_placeholders(text)
    processed_text = text
    citation_map = {}
    unresolved = []

    paper_lookup = {}
    for idx, paper in enumerate(papers, start=1):
        paper_id = str(paper.get("paper_id", ""))
        doi = str(paper.get("doi", "")).lower()
        pmid = str(paper.get("pmid", "")).lower()
        arxiv = str(paper.get("arxiv", "")).lower()
        title = str(paper.get("title", "")).lower()

        if paper_id:
            paper_lookup[("paper_id", paper_id)] = idx
        if doi:
            paper_lookup[("doi", doi)] = idx
        if pmid:
            paper_lookup[("pmid", pmid)] = idx
        if arxiv:
            paper_lookup[("arxiv", arxiv)] = idx
        if title:
            paper_lookup[("title", title)] = idx

    for ph in placeholders:
        ph_type = ph["type"]
        ph_identifier = ph["identifier"]
        ph_full = ph["full_match"]

        matched_idx = paper_lookup.get((ph_type, ph_identifier.lower()))

        if matched_idx is not None:
            if ph_full not in citation_map:
                citation_map[ph_full] = matched_idx
            replacement = f"[{matched_idx}]"
            processed_text = processed_text.replace(ph_full, replacement, 1)
        else:
            unresolved.append(ph_full)

    reference_list = generate_reference_list(papers, style)

    return {
        "processed_text": processed_text,
        "reference_list": reference_list,
        "citation_map": citation_map,
        "unresolved": unresolved,
    }


def process_manuscript_text(text: str, papers: list[dict], style: str = "gb7714") -> dict:
    """Process manuscript text by replacing citation placeholders with numbered citations.

    This is a simplified version that replaces placeholders with [1], [2], etc.
    based on paper order, and appends the reference list at the end.

    Args:
        text: The manuscript text containing citation placeholders.
        papers: A list of dicts, each representing a paper with 'citation_key'.
        style: Citation style for reference list.

    Returns:
        Dict with 'formatted_text' key containing the processed text.
    """
    placeholders = parse_citation_placeholders(text)
    processed_text = text

    paper_lookup = {}
    for idx, paper in enumerate(papers, start=1):
        citation_key = paper.get("citation_key", "")
        if citation_key:
            paper_lookup[citation_key] = idx

    used_citations = {}
    for ph in placeholders:
        ph_key = f"{ph['type']}:{ph['identifier']}"
        ph_full = ph["full_match"]

        if ph_key in paper_lookup and ph_key not in used_citations:
            used_citations[ph_key] = paper_lookup[ph_key]

        if ph_key in used_citations:
            replacement = f"[{used_citations[ph_key]}]"
            processed_text = processed_text.replace(ph_full, replacement, 1)

    ref_list = generate_reference_list(papers, style)
    processed_text += f"\n\n## References\n\n{ref_list}"

    return {"formatted_text": processed_text}


def get_paper_by_identifier(
    id_type: str,
    identifier: str,
    cache=None,
) -> dict | None:
    """Get paper metadata by identifier type and value.

    Args:
        id_type: One of 'doi', 'pmid', 'arxiv', 'title'.
        identifier: The identifier value.
        cache: Optional SearchCache instance.

    Returns:
        Dict with paper metadata, or None if not found.
    """
    if id_type == "doi":
        return _get_paper_by_doi(identifier, cache)
    elif id_type == "pmid":
        return _get_paper_by_pmid(identifier, cache)
    elif id_type == "arxiv":
        return _get_paper_by_arxiv(identifier, cache)
    elif id_type == "title":
        return _get_paper_by_title(identifier, cache)
    else:
        return None


def _get_paper_by_doi(doi: str, cache=None) -> dict | None:
    """Get paper by DOI using CrossRef API."""
    import requests

    if cache:
        cached = cache.get(doi, "crossref")
        if cached:
            return cached[0] if cached else None

    try:
        url = f"https://api.crossref.org/works/{doi}"
        resp = requests.get(url, timeout=10)
        if resp.status_code == 200:
            data = resp.json()["message"]
            paper = {
                "title": data.get("title", [""])[0],
                "authors": _extract_authors(data),
                "year": data.get("published-print", {}).get("date-parts", [[None]])[0][0] or
                       data.get("created", {}).get("date-parts", [[None]])[0][0],
                "source": data.get("container-title", [""])[0],
                "doi": doi,
                "volume": data.get("volume", ""),
                "issue": data.get("issue", ""),
                "pages": data.get("page", ""),
                "paper_id": doi,
                "type": get_document_type(data),
            }
            if cache:
                cache.set(doi, "crossref", [paper])
            return paper
    except Exception as e:
        logger.warning(f"Failed to fetch paper metadata: {e}")
    return None


def _get_paper_by_pmid(pmid: str, cache=None) -> dict | None:
    """Get paper by PMID using Entrez API."""
    import requests

    if cache:
        cached = cache.get(pmid, "pubmed")
        if cached:
            return cached[0] if cached else None

    try:
        fetch_url = f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi?db=pubmed&id={pmid}&retmode=xml"
        resp = requests.get(fetch_url, timeout=10)
        if resp.status_code == 200 and "<PubmedArticle>" in resp.text:
            from xml.etree.ElementTree import Element  # nosec B405 - 仅构造占位节点，非解析

            from defusedxml import ElementTree as ET
            root = ET.fromstring(resp.text)
            article = root.find(".//Article")
            if article is not None:
                title = (article.find(".//ArticleTitle") or Element("")).text or ""
                authors = []
                for author in article.findall(".//Author"):
                    lastname = (author.find("LastName") or Element("")).text or ""
                    initials = (author.find("Initials") or Element("")).text or ""
                    if lastname:
                        authors.append(f"{lastname} {initials}".strip())

                year_el = article.find(".//PubDate/Year")
                year = year_el.text if year_el is not None else ""

                journal = (article.find(".//Journal/Title") or Element("")).text or ""
                volume = (article.find(".//JournalIssue/Volume") or Element("")).text or ""
                issue = (article.find(".//JournalIssue/Issue") or Element("")).text or ""
                medline_paging = article.find(".//Pagination/MedlinePgn")
                pages = medline_paging.text if medline_paging is not None else ""

                dois = article.findall(".//ArticleId[@IdType='doi']")
                doi = dois[0].text if dois else ""

                paper = {
                    "title": title,
                    "authors": authors,
                    "year": year,
                    "source": journal,
                    "pmid": pmid,
                    "doi": doi,
                    "volume": volume,
                    "issue": issue,
                    "pages": pages,
                    "paper_id": pmid,
                }
                if cache:
                    cache.set(pmid, "pubmed", [paper])
                return paper
    except Exception as e:
        logger.warning(f"Failed to fetch paper metadata: {e}")
    return None


def _get_paper_by_arxiv(arxiv_id: str, cache=None) -> dict | None:
    """Get paper by arXiv ID."""
    import re

    import requests

    if cache:
        cached = cache.get(arxiv_id, "arxiv")
        if cached:
            return cached[0] if cached else None

    try:
        url = f"http://export.arxiv.org/api/query?id_list={arxiv_id}"
        resp = requests.get(url, timeout=10)
        if resp.status_code == 200 and "<entry>" in resp.text:
            from xml.etree.ElementTree import Element  # nosec B405 - 仅构造占位节点，非解析

            from defusedxml import ElementTree as ET
            root = ET.fromstring(resp.xml if hasattr(resp, 'xml') else resp.text)
            ns = {"atom": "http://www.w3.org/2005/Atom", "arxiv": "http://arxiv.org/schemas/atom"}

            entry = root.find(".//atom:entry", ns)
            if entry is not None:
                title = (entry.find("atom:title", ns) or Element("")).text or ""
                title = re.sub(r'\s+', ' ', title).strip()

                authors = []
                for author in entry.findall("atom:author", ns):
                    name = (author.find("atom:name", ns) or Element("")).text or ""
                    if name:
                        authors.append(name)

                published = (entry.find("atom:published", ns) or Element("")).text or ""
                year = published[:4] if published else ""

                summary = (entry.find("atom:summary", ns) or Element("")).text or ""

                paper = {
                    "title": title,
                    "authors": authors,
                    "year": year,
                    "source": "arXiv",
                    "arxiv": arxiv_id,
                    "paper_id": arxiv_id,
                    "abstract": summary,
                    "url": f"https://arxiv.org/abs/{arxiv_id}",
                }
                if cache:
                    cache.set(arxiv_id, "arxiv", [paper])
                return paper
    except Exception as e:
        logger.warning(f"Failed to fetch paper metadata: {e}")
    return None


def _get_paper_by_title(title: str, cache=None) -> dict | None:
    """Get paper by title using CrossRef search."""
    import requests

    if cache:
        cached = cache.get(title, "crossref", search_type="title")
        if cached:
            return cached[0] if cached else None

    try:
        url = "https://api.crossref.org/works"
        params: dict[str, str | int] = {"query.title": title, "rows": 1}
        resp = requests.get(url, params=params, timeout=10)
        if resp.status_code == 200:
            items = resp.json()["message"].get("items", [])
            if items:
                data = items[0]
                doi = data.get("DOI", "")
                paper = {
                    "title": data.get("title", [""])[0],
                    "authors": _extract_authors(data),
                    "year": data.get("published-print", {}).get("date-parts", [[None]])[0][0] or
                           data.get("created", {}).get("date-parts", [[None]])[0][0],
                    "source": data.get("container-title", [""])[0],
                    "doi": doi,
                    "volume": data.get("volume", ""),
                    "issue": data.get("issue", ""),
                    "pages": data.get("page", ""),
                    "paper_id": doi or title.replace(" ", "_"),
                    "type": get_document_type(data),
                }
                if cache:
                    cache.set(title, "crossref", [paper], search_type="title")
                return paper
    except Exception as e:
        logger.warning(f"Failed to fetch paper metadata: {e}")
    return None


def _extract_authors(data: dict) -> list[str]:
    """Extract author names from CrossRef API response."""
    authors = []
    for author in data.get("author", []):
        given = author.get("given", "")
        family = author.get("family", "")
        if family:
            authors.append(f"{given} {family}".strip())
    return authors


def get_document_type(data: dict) -> str:
    """Get RIS document type from CrossRef data."""
    type_map = {
        "journal-article": "JOUR",
        "proceedings-article": "CONF",
        "book-chapter": "CHAP",
        "book": "BOOK",
        "dataset": "DATA",
    }
    return type_map.get(data.get("type", "journal-article"), "JOUR")
