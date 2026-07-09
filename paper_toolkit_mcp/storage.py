"""SQLite-backed unified paper storage with PDF path tracking.

Replaces the scattered JSON cache for paper metadata. All search results
are upserted into a single SQLite database under ``WORK_DIR/papers.db``,
enabling cross-query lookup by DOI/title and deduplication across sessions.
"""
from __future__ import annotations

import os
import sqlite3
from datetime import datetime
from typing import Any

from .config import get_work_dir

DEFAULT_DB_PATH = os.path.join(get_work_dir(), "papers.db")


def _paper_dedup_key(paper: dict[str, Any]) -> str:
    """Generate a stable dedup key following the same logic as _paper_unique_key."""
    doi = (paper.get("doi") or "").strip().lower()
    if doi:
        return f"doi:{doi}"
    title = (paper.get("title") or "").strip().lower()
    authors = (paper.get("authors") or "").strip().lower()
    if title:
        return f"title:{title}|authors:{authors}"
    return f"id:{(paper.get('paper_id') or '').strip().lower()}"


class PaperStorage:
    """SQLite storage for paper metadata, local PDF paths, and full text."""

    def __init__(self, db_path: str | None = None) -> None:
        self.db_path = db_path or DEFAULT_DB_PATH
        os.makedirs(os.path.dirname(self.db_path) or ".", exist_ok=True)
        self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._init_db()

    def _init_db(self) -> None:
        self._conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS papers (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                dedup_key       TEXT UNIQUE NOT NULL,
                doi             TEXT,
                paper_id        TEXT NOT NULL,
                title           TEXT NOT NULL,
                authors         TEXT,
                abstract        TEXT,
                published_date  TEXT,
                pdf_url         TEXT,
                url             TEXT,
                source          TEXT NOT NULL,
                updated_date    TEXT,
                categories      TEXT,
                keywords        TEXT,
                citations       INTEGER DEFAULT 0,
                references_ids  TEXT,
                extra           TEXT,
                local_pdf_path  TEXT,
                fulltext        TEXT,
                fetched_at      TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_doi    ON papers(doi);
            CREATE INDEX IF NOT EXISTS idx_title  ON papers(title);
            CREATE INDEX IF NOT EXISTS idx_source ON papers(source);
            CREATE INDEX IF NOT EXISTS idx_pdf    ON papers(local_pdf_path);
            """
        )
        self._conn.commit()

    def upsert_paper(self, paper: dict[str, Any]) -> bool:
        """Insert or update a single paper. Returns True if a new row was inserted."""
        key = _paper_dedup_key(paper)
        now = datetime.now().isoformat()
        row = self._conn.execute(
            "SELECT id FROM papers WHERE dedup_key = ?", (key,)
        ).fetchone()

        doi = (paper.get("doi") or "").strip()
        if not doi:
            doi = row["doi"] if row else ""

        fields = {
            "dedup_key": key,
            "doi": doi,
            "paper_id": paper.get("paper_id", ""),
            "title": paper.get("title", ""),
            "authors": paper.get("authors", ""),
            "abstract": paper.get("abstract", ""),
            "published_date": paper.get("published_date", ""),
            "pdf_url": paper.get("pdf_url", ""),
            "url": paper.get("url", ""),
            "source": paper.get("source", ""),
            "updated_date": paper.get("updated_date", ""),
            "categories": paper.get("categories", ""),
            "keywords": paper.get("keywords", ""),
            "citations": int(paper.get("citations", 0) or 0),
            "references_ids": paper.get("references", ""),
            "extra": paper.get("extra", ""),
            "fetched_at": now,
        }

        if row:
            set_clauses = ", ".join(f"{k} = ?" for k in fields)
            values = list(fields.values()) + [row["id"]]
            self._conn.execute(
                f"UPDATE papers SET {set_clauses} WHERE id = ?", values
            )
        else:
            cols = ", ".join(fields.keys())
            placeholders = ", ".join("?" for _ in fields)
            self._conn.execute(
                f"INSERT INTO papers ({cols}) VALUES ({placeholders})",
                list(fields.values()),
            )
        self._conn.commit()
        return row is None

    def upsert_papers(self, papers: list[dict[str, Any]]) -> int:
        """Batch upsert. Returns count of newly inserted papers."""
        new_count = 0
        for p in papers:
            if self.upsert_paper(p):
                new_count += 1
        return new_count

    def get_by_doi(self, doi: str) -> dict[str, Any] | None:
        row = self._conn.execute(
            "SELECT * FROM papers WHERE doi = ? LIMIT 1", (doi.strip().lower(),)
        ).fetchone()
        return dict(row) if row else None

    def get_by_dedup_key(self, key: str) -> dict[str, Any] | None:
        row = self._conn.execute(
            "SELECT * FROM papers WHERE dedup_key = ? LIMIT 1", (key,)
        ).fetchone()
        return dict(row) if row else None

    def search_local(
        self, keyword: str, limit: int = 50
    ) -> list[dict[str, Any]]:
        """Full-text search across title, authors, abstract in the local library."""
        pattern = f"%{keyword}%"
        rows = self._conn.execute(
            """SELECT * FROM papers
               WHERE title LIKE ? OR authors LIKE ? OR abstract LIKE ?
               ORDER BY fetched_at DESC LIMIT ?""",
            (pattern, pattern, pattern, limit),
        ).fetchall()
        return [dict(r) for r in rows]

    def list_papers(
        self, source: str = "", limit: int = 100, offset: int = 0
    ) -> list[dict[str, Any]]:
        if source:
            rows = self._conn.execute(
                "SELECT * FROM papers WHERE source = ? ORDER BY fetched_at DESC LIMIT ? OFFSET ?",
                (source, limit, offset),
            ).fetchall()
        else:
            rows = self._conn.execute(
                "SELECT * FROM papers ORDER BY fetched_at DESC LIMIT ? OFFSET ?",
                (limit, offset),
            ).fetchall()
        return [dict(r) for r in rows]

    def set_local_pdf(self, dedup_key: str, pdf_path: str) -> bool:
        cur = self._conn.execute(
            "UPDATE papers SET local_pdf_path = ? WHERE dedup_key = ?",
            (pdf_path, dedup_key),
        )
        self._conn.commit()
        return cur.rowcount > 0

    def get_local_pdf(self, dedup_key: str) -> str | None:
        row = self._conn.execute(
            "SELECT local_pdf_path FROM papers WHERE dedup_key = ?", (dedup_key,)
        ).fetchone()
        if row and row["local_pdf_path"]:
            path = row["local_pdf_path"]
            if os.path.exists(path):
                return path
        return None

    def set_fulltext(self, dedup_key: str, text: str) -> bool:
        cur = self._conn.execute(
            "UPDATE papers SET fulltext = ? WHERE dedup_key = ?",
            (text, dedup_key),
        )
        self._conn.commit()
        return cur.rowcount > 0

    def get_fulltext(self, dedup_key: str) -> str | None:
        row = self._conn.execute(
            "SELECT fulltext FROM papers WHERE dedup_key = ?", (dedup_key,)
        ).fetchone()
        return row["fulltext"] if row and row["fulltext"] else None

    def get_stats(self) -> dict[str, Any]:
        total = self._conn.execute("SELECT COUNT(*) FROM papers").fetchone()[0]
        with_pdf = self._conn.execute(
            "SELECT COUNT(*) FROM papers WHERE local_pdf_path IS NOT NULL AND local_pdf_path != ''"
        ).fetchone()[0]
        with_doi = self._conn.execute(
            "SELECT COUNT(*) FROM papers WHERE doi IS NOT NULL AND doi != ''"
        ).fetchone()[0]
        with_fulltext = self._conn.execute(
            "SELECT COUNT(*) FROM papers WHERE fulltext IS NOT NULL AND fulltext != ''"
        ).fetchone()[0]
        by_source = self._conn.execute(
            "SELECT source, COUNT(*) as cnt FROM papers GROUP BY source ORDER BY cnt DESC"
        ).fetchall()
        return {
            "total_papers": total,
            "with_local_pdf": with_pdf,
            "with_doi": with_doi,
            "with_fulltext": with_fulltext,
            "db_path": self.db_path,
            "by_source": {r["source"]: r["cnt"] for r in by_source},
        }

    def close(self) -> None:
        self._conn.close()
