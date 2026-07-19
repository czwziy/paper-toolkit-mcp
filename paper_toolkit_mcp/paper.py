# paper_toolkit_mcp/paper.py
"""Standardized paper dataclass.

List and dict fields (authors, categories, keywords, references, extra) are
serialized to JSON strings by ``to_dict()`` so they can be stored in SQLite
TEXT columns and round-tripped losslessly. Storage/merge logic parses these
JSON strings back to native types, merges, and re-serializes — see
``server._dedupe_papers`` and ``cli._dedupe``.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime

# ---------------------------------------------------------------------------
# Author name normalization
# ---------------------------------------------------------------------------

# Pattern: a single uppercase letter, optionally followed by a period
_INITIAL_RE = re.compile(r"^[A-Z]\.?$")

# CJK Unified Ideographs range — used to detect Chinese/Japanese names
_CJK_RE = re.compile(r"[\u4e00-\u9fff]")


def normalize_author_name(name: str) -> str:
    """Normalize an author name to ``Surname, Given`` format.

    Academic sources return author names in inconsistent formats:

    ============  =====================  ============  ====================
    Source        Example input          Detected as   Normalized output
    ============  =====================  ============  ====================
    PubMed        ``"Marshall K"``       Last+Init     ``Marshall, K``
    Semantic      ``"J Jakusova"``       Init+Last     ``Jakusova, J``
    arXiv         ``"Md Sirajus Salekin"`` Given+Last   ``Salekin, Md Sirajus``
    CrossRef      ``"Kenneth Prkachin"``  Given+Last   ``Prkachin, Kenneth``
    ============  =====================  ============  ====================

    Rules (applied in order):

    1. **CJK names**: If the name contains CJK characters, keep as-is
       (surname-first is the natural order).
    2. **Single word**: Return as-is (e.g. ``"Zhang"`` → ``"Zhang"``).
    3. **"LastName Initials"** (PubMed style): Last word is a short initial
       (1–2 chars, no period or with period).  Surname is the *first* word.
       → ``Surname, Initials``
    4. **"Initial Surname"** (Semantic style): First word is a short initial.
       Surname is the *last* word.
       → ``Surname, Initial``
    5. **"Given Surname"** (arXiv/CrossRef/OpenAlex style): Neither first nor
       last word is a short initial.  Surname is the *last* word.
       → ``Surname, Given``

    Args:
        name: Raw author name string from any academic source.

    Returns:
        Normalized name in ``Surname, Given`` format.
    """
    name = name.strip()
    if not name:
        return name

    # Rule 1: CJK names — keep as-is
    if _CJK_RE.search(name):
        return name

    parts = name.split()
    if len(parts) == 1:
        # Rule 2: Single word
        return name

    def _is_initial(word: str) -> bool:
        """Check if a word looks like a name initial (e.g. 'K', 'J.', 'MJ')."""
        # Single letter like "K" or "J"
        if len(word) == 1 and word.isalpha():
            return True
        # Single letter with period like "K." or "J."
        if len(word) == 2 and word[0].isalpha() and word[1] == ".":
            return True
        # Two initials without period like "MJ" or "KJ"
        if len(word) == 2 and word.isalpha() and word.isupper():
            return True
        # Two initials with periods like "M.J."
        if len(word) == 4 and word[0].isalpha() and word[1] == "." and word[2].isalpha() and word[3] == ".":
            return True
        return False

    last_word = parts[-1]
    first_word = parts[0]

    # Rule 3: "LastName Initials" — last word is an initial, first is not
    # e.g. "Marshall K", "McDonnell MJ", "Duignan N"
    if _is_initial(last_word) and not _is_initial(first_word):
        surname = parts[0]
        given = " ".join(parts[1:])
        return f"{surname}, {given}"

    # Rule 4: "Initial Surname" — first word is an initial
    # e.g. "J Jakusova", "M Brozmanova"
    if _is_initial(first_word):
        surname = parts[-1]
        given = " ".join(parts[:-1])
        return f"{surname}, {given}"

    # Rule 5: "Given Surname" — standard Western name
    # e.g. "Kenneth Prkachin", "Md Sirajus Salekin"
    surname = parts[-1]
    given = " ".join(parts[:-1])
    return f"{surname}, {given}"


@dataclass
class Paper:
    """Standardized paper format with core fields for academic sources"""
    # 核心字段（必填，但允许空值或默认值）
    paper_id: str              # Unique identifier (e.g., arXiv ID, PMID, DOI)
    title: str                 # Paper title
    authors: list[str]         # List of author names in "Surname, Given" format
    abstract: str              # Abstract text
    doi: str                   # Digital Object Identifier
    published_date: datetime | None   # Publication date
    pdf_url: str               # Direct PDF link
    url: str                   # URL to paper page
    source: str                # Source platform (e.g., 'arxiv', 'pubmed')

    # 可选字段
    updated_date: datetime | None = None        # Last updated date
    categories: list[str] | None = None         # Subject categories
    keywords: list[str] | None = None           # Keywords
    references: list[str] | None = None         # List of reference IDs/DOIs
    extra: dict | None = None                   # Source-specific extra metadata

    def __post_init__(self):
        """Post-initialization to handle default values and normalize authors"""
        if self.authors is None:
            self.authors = []
        else:
            self.authors = [normalize_author_name(a) for a in self.authors]
        if self.categories is None:
            self.categories = []
        if self.keywords is None:
            self.keywords = []
        if self.references is None:
            self.references = []
        if self.extra is None:
            self.extra = {}

    def to_dict(self) -> dict:
        """Convert paper to dictionary format for serialization.

        List and dict fields are JSON-serialized so they can be stored in
        SQLite TEXT columns and parsed back losslessly by the storage layer.
        Single-value fields (title, abstract, doi, dates, urls) stay as
        plain strings.
        """
        return {
            'paper_id': self.paper_id,
            'title': self.title,
            'authors': json.dumps(self.authors, ensure_ascii=False) if self.authors else '[]',
            'abstract': self.abstract,
            'doi': self.doi,
            'published_date': self.published_date.isoformat() if self.published_date else '',
            'pdf_url': self.pdf_url,
            'url': self.url,
            'source': self.source,
            'updated_date': self.updated_date.isoformat() if self.updated_date else '',
            'categories': json.dumps(self.categories, ensure_ascii=False) if self.categories else '[]',
            'keywords': json.dumps(self.keywords, ensure_ascii=False) if self.keywords else '[]',
            'references': json.dumps(self.references, ensure_ascii=False) if self.references else '[]',
            'extra': json.dumps(self.extra, ensure_ascii=False) if self.extra else '{}',
        }
