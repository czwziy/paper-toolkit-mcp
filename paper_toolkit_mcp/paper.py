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
from dataclasses import dataclass
from datetime import datetime


@dataclass
class Paper:
    """Standardized paper format with core fields for academic sources"""
    # 核心字段（必填，但允许空值或默认值）
    paper_id: str              # Unique identifier (e.g., arXiv ID, PMID, DOI)
    title: str                 # Paper title
    authors: list[str]         # List of author full-name strings
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
        """Post-initialization to handle default values"""
        if self.authors is None:
            self.authors = []
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
