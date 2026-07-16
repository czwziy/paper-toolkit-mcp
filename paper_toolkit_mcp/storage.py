"""SQLite-backed unified paper storage with cite_key and PDF path tracking.

All search results are upserted into a single SQLite database under
``WORK_DIR/papers.db``. Each paper gets a short, opaque ``cite_key``
(3-letter random, e.g. ``Kxq``) that AI uses for citation — it never
touches DOI/paper_id directly.

The ``citation_scores`` table caches multi-model citation verification
results, keyed by (cite_key, sentence_hash, model_name) for incremental
updates.
"""
from __future__ import annotations

import hashlib
import os
import random
import sqlite3
import string
from datetime import datetime
from typing import Any

from .config import get_work_dir

DEFAULT_DB_PATH = os.path.join(get_work_dir(), "papers.db")


def _paper_dedup_key(paper: dict[str, Any]) -> str:
    """Generate a stable dedup key from DOI > title+authors > paper_id."""
    doi = (paper.get("doi") or "").strip().lower()
    if doi:
        return f"doi:{doi}"
    title = (paper.get("title") or "").strip().lower()
    authors = (paper.get("authors") or "").strip().lower()
    if title:
        return f"title:{title}|authors:{authors}"
    return f"id:{(paper.get('paper_id') or '').strip().lower()}"


def _generate_cite_key(existing_keys: set[str]) -> str:
    """Generate a unique 3-letter random cite_key (a-zA-Z).

    Upgrades to 4 letters if 3-letter space is exhausted (52^3 = 140 608).
    """
    chars = string.ascii_letters
    for length in (3, 4, 5):
        for _ in range(50_000):
            key = "".join(random.choices(chars, k=length))
            if key not in existing_keys:
                return key
    raise RuntimeError("cite_key space exhausted (tried up to 5 letters)")


class PaperStorage:
    """SQLite storage for paper metadata, cite_keys, local PDFs, and full text."""

    def __init__(self, db_path: str | None = None) -> None:
        self.db_path = db_path or DEFAULT_DB_PATH
        os.makedirs(os.path.dirname(self.db_path) or ".", exist_ok=True)
        self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._init_db()
        self._backfill_cite_keys()

    def _init_db(self) -> None:
        self._conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS papers (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                dedup_key       TEXT UNIQUE NOT NULL,
                cite_key        TEXT UNIQUE,
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
                refs            TEXT,
                extra           TEXT,
                local_pdf_path  TEXT,
                fulltext        TEXT,
                fetched_at      TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_doi     ON papers(doi);
            CREATE INDEX IF NOT EXISTS idx_title   ON papers(title);
            CREATE INDEX IF NOT EXISTS idx_source  ON papers(source);
            CREATE INDEX IF NOT EXISTS idx_pdf     ON papers(local_pdf_path);
            """
        )
        # Migration: add cite_key column if missing (for existing DBs)
        cols = {row["name"] for row in self._conn.execute("PRAGMA table_info(papers)")}
        if "cite_key" not in cols:
            self._conn.execute("ALTER TABLE papers ADD COLUMN cite_key TEXT")
            self._conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_cite_key ON papers(cite_key)")
        else:
            self._conn.execute("CREATE INDEX IF NOT EXISTS idx_cite_key ON papers(cite_key)")

        # Citation verification scores table
        self._conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS citation_scores (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                cite_key        TEXT NOT NULL,
                sentence_hash   TEXT NOT NULL,
                sentence_text   TEXT NOT NULL,
                model_name      TEXT NOT NULL,
                score           INTEGER NOT NULL,
                rationale       TEXT,
                created_at      TEXT NOT NULL,
                UNIQUE(cite_key, sentence_hash, model_name)
            );
            CREATE INDEX IF NOT EXISTS idx_cs_cite_key
                ON citation_scores(cite_key);
            CREATE INDEX IF NOT EXISTS idx_cs_sentence
                ON citation_scores(sentence_hash);
            """
        )
        self._conn.commit()

    def _backfill_cite_keys(self) -> None:
        """Assign cite_key to existing rows that don't have one."""
        rows = self._conn.execute(
            "SELECT id FROM papers WHERE cite_key IS NULL OR cite_key = ''"
        ).fetchall()
        if not rows:
            return
        existing = {
            r["cite_key"]
            for r in self._conn.execute("SELECT cite_key FROM papers WHERE cite_key IS NOT NULL")
            if r["cite_key"]
        }
        for row in rows:
            key = _generate_cite_key(existing)
            self._conn.execute(
                "UPDATE papers SET cite_key = ? WHERE id = ?", (key, row["id"])
            )
            existing.add(key)
        self._conn.commit()

    def upsert_paper(self, paper: dict[str, Any]) -> bool:
        """Insert or update a single paper. Returns True if newly inserted.

        Auto-assigns a cite_key on first insert. Papers without abstract
        should be filtered by the caller before calling this method.
        """
        key = _paper_dedup_key(paper)
        now = datetime.now().isoformat()
        row = self._conn.execute(
            "SELECT id, cite_key FROM papers WHERE dedup_key = ?", (key,)
        ).fetchone()

        # Normalize DOI to lowercase+strip so get_by_doi (which lowercases the
        # query) matches consistently — same normalization as _paper_dedup_key.
        doi = (paper.get("doi") or "").strip().lower()
        if not doi:
            doi = row["doi"] if row else ""

        fields = {
            "dedup_key": key,
            "doi": doi,
            "paper_id": paper.get("paper_id", ""),
            "title": paper.get("title", ""),
            "authors": paper.get("authors", "[]"),
            "abstract": paper.get("abstract", ""),
            "published_date": paper.get("published_date", ""),
            "pdf_url": paper.get("pdf_url", ""),
            "url": paper.get("url", ""),
            "source": paper.get("source", ""),
            "updated_date": paper.get("updated_date", ""),
            "categories": paper.get("categories", "[]"),
            "keywords": paper.get("keywords", "[]"),
            "refs": paper.get("references", "[]"),
            "extra": paper.get("extra", "{}"),
            "fetched_at": now,
        }

        if row:
            set_clauses = ", ".join(f"{k} = ?" for k in fields)
            values = list(fields.values()) + [row["id"]]
            # Column names are hardcoded, not user input — no injection risk
            self._conn.execute(
                f"UPDATE papers SET {set_clauses} WHERE id = ?",  # nosec B608
                values,
            )
            cite_key = row["cite_key"]
        else:
            existing_keys = {
                r["cite_key"]
                for r in self._conn.execute("SELECT cite_key FROM papers WHERE cite_key IS NOT NULL")
                if r["cite_key"]
            }
            cite_key = _generate_cite_key(existing_keys)
            fields["cite_key"] = cite_key
            cols = ", ".join(fields.keys())
            placeholders = ", ".join("?" for _ in fields)
            # Column names are hardcoded, not user input — no injection risk
            self._conn.execute(
                f"INSERT INTO papers ({cols}) VALUES ({placeholders})",  # nosec B608
                list(fields.values()),
            )
        self._conn.commit()
        paper["cite_key"] = cite_key
        return row is None

    def upsert_papers(self, papers: list[dict[str, Any]]) -> int:
        """Batch upsert. Returns count of newly inserted papers."""
        new_count = 0
        for p in papers:
            if self.upsert_paper(p):
                new_count += 1
        return new_count

    def get_by_cite_key(self, cite_key: str) -> dict[str, Any] | None:
        row = self._conn.execute(
            "SELECT * FROM papers WHERE cite_key = ? LIMIT 1", (cite_key,)
        ).fetchone()
        return dict(row) if row else None

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

    # ------------------------------------------------------------------
    # Citation verification scores
    # ------------------------------------------------------------------

    @staticmethod
    def sentence_hash(sentence: str) -> str:
        """Stable hash for a sentence, used as cache key."""
        return hashlib.md5(sentence.encode("utf-8")).hexdigest()

    def get_cached_scores(
        self, cite_key: str, sentence: str
    ) -> list[dict[str, Any]]:
        """Return cached scores for a (cite_key, sentence) pair.

        Returns a list of dicts with keys: model_name, score, rationale, created_at.
        """
        s_hash = self.sentence_hash(sentence)
        rows = self._conn.execute(
            "SELECT model_name, score, rationale, created_at "
            "FROM citation_scores WHERE cite_key = ? AND sentence_hash = ?",
            (cite_key, s_hash),
        ).fetchall()
        return [dict(r) for r in rows]

    def upsert_score(
        self,
        cite_key: str,
        sentence: str,
        model_name: str,
        score: int,
        rationale: str = "",
    ) -> None:
        """Insert or update a single citation score record."""
        s_hash = self.sentence_hash(sentence)
        now = datetime.now().isoformat()
        self._conn.execute(
            """
            INSERT INTO citation_scores (cite_key, sentence_hash, sentence_text, model_name, score, rationale, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(cite_key, sentence_hash, model_name)
            DO UPDATE SET score=excluded.score, rationale=excluded.rationale, created_at=excluded.created_at
            """,
            (cite_key, s_hash, sentence, model_name, score, rationale, now),
        )
        self._conn.commit()

    def delete_scores(
        self, cite_key: str, sentence: str | None = None
    ) -> int:
        """Delete cached scores. If sentence is None, delete all for cite_key.

        Returns number of deleted rows.
        """
        if sentence is None:
            cur = self._conn.execute(
                "DELETE FROM citation_scores WHERE cite_key = ?", (cite_key,)
            )
        else:
            s_hash = self.sentence_hash(sentence)
            cur = self._conn.execute(
                "DELETE FROM citation_scores WHERE cite_key = ? AND sentence_hash = ?",
                (cite_key, s_hash),
            )
        self._conn.commit()
        return cur.rowcount

    def get_all_scores(
        self, cite_key: str | None = None, limit: int = 500
    ) -> list[dict[str, Any]]:
        """Return citation scores, optionally filtered by cite_key."""
        if cite_key:
            rows = self._conn.execute(
                "SELECT * FROM citation_scores WHERE cite_key = ? ORDER BY created_at DESC LIMIT ?",
                (cite_key, limit),
            ).fetchall()
        else:
            rows = self._conn.execute(
                "SELECT * FROM citation_scores ORDER BY created_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [dict(r) for r in rows]

    def close(self) -> None:
        self._conn.close()
