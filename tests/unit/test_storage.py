"""Hermetic unit tests for the SQLite-backed PaperStorage.

Covers the critical new logic: cite_key generation/uniqueness/collision,
upsert dedup merging, dedup_key priority, abstract-required invariant
is enforced by the caller (tested in test_server_helpers), backfill of
legacy rows, PDF path + fulltext tracking, JSON field round-trip.
"""
import json
import os
import shutil
import string
import tempfile
import unittest

from paper_toolkit_mcp.storage import (
    PaperStorage,
    _generate_cite_key,
    _paper_dedup_key,
)


class TestPaperDedupKey(unittest.TestCase):
    def test_doi_takes_priority(self):
        paper = {"doi": "10.1000/test", "title": "T", "authors": "A", "paper_id": "p1"}
        self.assertEqual(_paper_dedup_key(paper), "doi:10.1000/test")

    def test_doi_normalized_lowercase_and_trimmed(self):
        paper = {"doi": "  10.1000/TEST  ", "title": "T"}
        self.assertEqual(_paper_dedup_key(paper), "doi:10.1000/test")

    def test_title_authors_fallback_when_no_doi(self):
        paper = {"title": "Deep Learning", "authors": "LeCun"}
        self.assertEqual(_paper_dedup_key(paper), "title:deep learning|authors:lecun")

    def test_paper_id_last_resort(self):
        paper = {"paper_id": "arxiv:1234"}
        self.assertEqual(_paper_dedup_key(paper), "id:arxiv:1234")

    def test_empty_paper_yields_empty_id_key(self):
        self.assertEqual(_paper_dedup_key({}), "id:")


class TestGenerateCiteKey(unittest.TestCase):
    def test_three_letter_random(self):
        key = _generate_cite_key(set())
        self.assertEqual(len(key), 3)

    def test_only_ascii_letters(self):
        for _ in range(50):
            key = _generate_cite_key(set())
            self.assertTrue(all(c in string.ascii_letters for c in key))

    def test_never_collides_with_existing(self):
        existing = {"abc", "xyz", "Kxq"}
        for _ in range(100):
            key = _generate_cite_key(existing)
            self.assertNotIn(key, existing)

    def test_bulk_generation_all_unique(self):
        existing: set[str] = set()
        for _ in range(500):
            key = _generate_cite_key(existing)
            self.assertNotIn(key, existing)
            existing.add(key)


class TestPaperStorage(unittest.TestCase):
    def setUp(self) -> None:
        self.tmpdir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.tmpdir, "test.db")
        self.storage = PaperStorage(db_path=self.db_path)

    def tearDown(self) -> None:
        self.storage.close()
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _make_paper(self, **overrides) -> dict:
        """Build a paper dict in the real to_dict() format (JSON list/dict fields).

        authors/categories/keywords/references are JSON strings, not Python lists.
        """
        base = {
            "doi": "",
            "paper_id": "p1",
            "title": "Test Paper",
            "authors": '["Author A"]',
            "abstract": "An abstract.",
            "published_date": "2023-01-01",
            "source": "arxiv",
            "categories": "[]",
            "keywords": "[]",
            "references": "[]",
            "extra": "{}",
        }
        base.update(overrides)
        return base

    # --- upsert + cite_key ---

    def test_upsert_assigns_cite_key_on_first_insert(self):
        paper = self._make_paper()
        inserted = self.storage.upsert_paper(paper)
        self.assertTrue(inserted)
        self.assertIn("cite_key", paper)
        self.assertEqual(len(paper["cite_key"]), 3)

    def test_upsert_same_dedup_key_updates_not_inserts(self):
        p1 = self._make_paper(doi="10.1000/x")
        self.storage.upsert_paper(p1)
        original_key = p1["cite_key"]

        p2 = self._make_paper(doi="10.1000/x", title="Updated Title", abstract="New abstract")
        inserted = self.storage.upsert_paper(p2)
        self.assertFalse(inserted)
        self.assertEqual(p2["cite_key"], original_key)

        row = self.storage.get_by_cite_key(original_key)
        self.assertEqual(row["title"], "Updated Title")
        self.assertEqual(row["abstract"], "New abstract")

    def test_cite_key_stable_across_multiple_updates(self):
        p = self._make_paper(doi="10.1/z")
        self.storage.upsert_paper(p)
        stable_key = p["cite_key"]
        for new_abs in ("a", "b", "c"):
            self.storage.upsert_paper(self._make_paper(doi="10.1/z", abstract=new_abs))
        self.assertEqual(
            self.storage.get_by_cite_key(stable_key)["abstract"], "c"
        )

    def test_distinct_papers_get_distinct_cite_keys(self):
        keys: set[str] = set()
        for i in range(50):
            p = self._make_paper(paper_id=f"p{i}", title=f"Paper {i}")
            self.storage.upsert_paper(p)
            self.assertNotIn(p["cite_key"], keys)
            keys.add(p["cite_key"])

    def test_batch_upsert_returns_new_count(self):
        papers = [
            self._make_paper(doi=f"10.0/{i}", paper_id=f"p{i}", title=f"P{i}")
            for i in range(5)
        ]
        new_count = self.storage.upsert_papers(papers)
        self.assertEqual(new_count, 5)
        # re-upsert same set → 0 new
        self.assertEqual(self.storage.upsert_papers(papers), 0)

    # --- lookups ---

    def test_get_by_cite_key_missing_returns_none(self):
        self.assertIsNone(self.storage.get_by_cite_key("NONEXIST"))

    def test_get_by_doi_normalizes(self):
        p = self._make_paper(doi="10.3/A")
        self.storage.upsert_paper(p)
        # lookup with different casing / whitespace
        fetched = self.storage.get_by_doi("  10.3/a  ")
        self.assertIsNotNone(fetched)
        self.assertEqual(fetched["cite_key"], p["cite_key"])

    def test_get_by_dedup_key(self):
        p = self._make_paper(doi="10.3/b")
        self.storage.upsert_paper(p)
        row = self.storage.get_by_dedup_key("doi:10.3/b")
        self.assertIsNotNone(row)
        self.assertEqual(row["title"], "Test Paper")

    # --- JSON field round-trip ---

    def test_json_list_fields_round_trip(self):
        """authors/categories/keywords/references 存取保持 JSON 格式."""
        p = self._make_paper(
            doi="10.5/json",
            authors='["Alice", "Bob"]',
            categories='["cs.AI", "cs.LG"]',
            keywords='["deep learning"]',
            references='["10.1/x", "10.2/y"]',
        )
        self.storage.upsert_paper(p)
        row = self.storage.get_by_cite_key(p["cite_key"])
        self.assertIsNotNone(row)
        # DB 列 refs 存储 references 的 JSON 字符串
        self.assertEqual(json.loads(row["authors"]), ["Alice", "Bob"])
        self.assertEqual(json.loads(row["categories"]), ["cs.AI", "cs.LG"])
        self.assertEqual(json.loads(row["keywords"]), ["deep learning"])
        self.assertEqual(json.loads(row["refs"]), ["10.1/x", "10.2/y"])

    def test_extra_json_dict_round_trip(self):
        """extra 字段存取保持 JSON dict 格式."""
        p = self._make_paper(
            doi="10.6/extra",
            extra='{"publisher": "Elsevier", "oa": "green"}',
        )
        self.storage.upsert_paper(p)
        row = self.storage.get_by_cite_key(p["cite_key"])
        extra = json.loads(row["extra"])
        self.assertEqual(extra["publisher"], "Elsevier")
        self.assertEqual(extra["oa"], "green")

    def test_no_citations_column_exists(self):
        """citations 字段已删除，不应存在于 schema."""
        cols = {row["name"] for row in self.storage._conn.execute("PRAGMA table_info(papers)")}
        self.assertNotIn("citations", cols)
        self.assertNotIn("references_ids", cols)
        self.assertIn("refs", cols)

    # --- PDF path + fulltext ---

    def test_set_and_get_local_pdf_when_file_exists(self):
        p = self._make_paper(doi="10.4/c")
        self.storage.upsert_paper(p)
        key = _paper_dedup_key(p)
        pdf_path = os.path.join(self.tmpdir, "paper.pdf")
        with open(pdf_path, "wb") as f:
            f.write(b"%PDF-1.4 test")
        self.assertTrue(self.storage.set_local_pdf(key, pdf_path))
        self.assertEqual(self.storage.get_local_pdf(key), pdf_path)

    def test_get_local_pdf_returns_none_when_file_missing_on_disk(self):
        p = self._make_paper(doi="10.4/d")
        self.storage.upsert_paper(p)
        key = _paper_dedup_key(p)
        self.storage.set_local_pdf(key, os.path.join(self.tmpdir, "ghost.pdf"))
        self.assertIsNone(self.storage.get_local_pdf(key))

    def test_set_local_pdf_unknown_dedup_key_returns_false(self):
        self.assertFalse(self.storage.set_local_pdf("doi:missing", "/tmp/x.pdf"))

    def test_set_and_get_fulltext(self):
        p = self._make_paper(doi="10.6/e")
        self.storage.upsert_paper(p)
        key = _paper_dedup_key(p)
        self.assertTrue(self.storage.set_fulltext(key, "full text content"))
        self.assertEqual(self.storage.get_fulltext(key), "full text content")

    def test_get_fulltext_missing_returns_none(self):
        p = self._make_paper(doi="10.6/f")
        self.storage.upsert_paper(p)
        self.assertIsNone(self.storage.get_fulltext(_paper_dedup_key(p)))

    # --- search + stats ---

    def test_search_local_matches_title_authors_abstract(self):
        self.storage.upsert_paper(
            self._make_paper(doi="10.9/g", title="Machine Learning Survey",
                             authors='["Alice"]')
        )
        self.assertEqual(len(self.storage.search_local("Machine")), 1)
        self.assertEqual(len(self.storage.search_local("Alice")), 1)
        self.assertEqual(len(self.storage.search_local("nonexistent")), 0)

    def test_get_stats_counts_by_source(self):
        self.storage.upsert_paper(self._make_paper(doi="10.7/a", source="arxiv"))
        self.storage.upsert_paper(self._make_paper(doi="10.8/b", source="pubmed"))
        stats = self.storage.get_stats()
        self.assertEqual(stats["total_papers"], 2)
        self.assertEqual(stats["by_source"]["arxiv"], 1)
        self.assertEqual(stats["by_source"]["pubmed"], 1)
        self.assertEqual(stats["with_doi"], 2)

    def test_list_papers_filters_by_source(self):
        self.storage.upsert_paper(self._make_paper(doi="10.1/a", source="arxiv"))
        self.storage.upsert_paper(self._make_paper(doi="10.2/b", source="pubmed"))
        only_arxiv = self.storage.list_papers(source="arxiv")
        self.assertEqual(len(only_arxiv), 1)
        self.assertEqual(only_arxiv[0]["source"], "arxiv")

    # --- backfill migration ---

    def test_backfill_assigns_cite_keys_to_legacy_rows(self):
        p = self._make_paper(doi="10.10/h")
        self.storage.upsert_paper(p)
        # Simulate a legacy row with no cite_key
        self.storage._conn.execute("UPDATE papers SET cite_key = NULL")
        self.storage._conn.commit()

        # Re-instantiate — __init__ runs _backfill_cite_keys
        self.storage.close()
        self.storage = PaperStorage(db_path=self.db_path)

        rows = self.storage._conn.execute("SELECT cite_key FROM papers").fetchall()
        self.assertGreaterEqual(len(rows), 1)
        for row in rows:
            self.assertIsNotNone(row["cite_key"])
            self.assertEqual(len(row["cite_key"]), 3)


if __name__ == "__main__":
    unittest.main()
