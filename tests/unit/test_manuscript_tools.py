# tests/unit/test_manuscript_tools.py
"""Unit tests for manuscript.py cite_key based tools (generate_ref_list, generate_human_review)."""
import asyncio
import os
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from paper_toolkit_mcp.tools.manuscript import (
    _CITE_KEY_RE,
    _extract_cite_keys,
    _format_author_year,
    _paper_to_ref_dict,
    generate_human_review,
    generate_ref_list,
)


def _create_temp_md(content: str) -> str:
    """Create a temp markdown file with content, return path. Caller must unlink."""
    fd, path = tempfile.mkstemp(suffix=".md")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(content)
    return path


class TestExtractCiteKeys(unittest.TestCase):
    def test_single_cite_key(self):
        text = "研究表明[@Kxq]该方法有效。"
        keys = _extract_cite_keys(text)
        self.assertEqual(keys, ["Kxq"])

    def test_multiple_cite_keys(self):
        text = "研究[@JHw]表明[@gKZ]，方法[@vEw]有效。"
        keys = _extract_cite_keys(text)
        self.assertEqual(keys, ["JHw", "gKZ", "vEw"])

    def test_duplicate_cite_keys_preserve_order(self):
        text = "研究[@Kxq]表明[@JHw]，再次引用[@Kxq]。"
        keys = _extract_cite_keys(text)
        self.assertEqual(keys, ["Kxq", "JHw"])

    def test_no_cite_keys(self):
        text = "这是一段没有引用的文本。"
        keys = _extract_cite_keys(text)
        self.assertEqual(keys, [])

    def test_multi_cite_same_bracket(self):
        """Test [@id1; @id2] format — should not match (different format)."""
        text = "研究[@vme; @dnr]表明。"
        keys = _extract_cite_keys(text)
        self.assertEqual(keys, [])

    def test_cite_key_regex_pattern(self):
        """Test the regex directly for edge cases."""
        m = _CITE_KEY_RE.search("[@Kxq]")
        self.assertIsNotNone(m)
        self.assertEqual(m.group(1), "Kxq")

        m = _CITE_KEY_RE.search("[@123]")
        self.assertIsNotNone(m)
        self.assertEqual(m.group(1), "123")

        m = _CITE_KEY_RE.search("[@Ab3]")
        self.assertIsNotNone(m)
        self.assertEqual(m.group(1), "Ab3")


class TestPaperToRefDict(unittest.TestCase):
    def test_basic_conversion(self):
        row = {
            "paper_id": "10.1234/test",
            "cite_key": "Kxq",
            "title": "Test Paper Title",
            "authors": '["Smith, J", "Doe, A"]',
            "published_date": "2023-06-15",
            "source": "pubmed",
            "doi": "10.1234/test",
            "url": "https://example.com",
            "abstract": "Test abstract",
        }
        result = _paper_to_ref_dict(row)
        self.assertEqual(result["title"], "Test Paper Title")
        self.assertEqual(result["authors"], ["Smith, J", "Doe, A"])
        self.assertEqual(result["year"], "2023")
        self.assertEqual(result["doi"], "10.1234/test")

    def test_authors_as_list(self):
        row = {
            "authors": ["Smith, J", "Doe, A"],
            "published_date": "2022",
        }
        result = _paper_to_ref_dict(row)
        self.assertEqual(result["authors"], ["Smith, J", "Doe, A"])
        self.assertEqual(result["year"], "2022")

    def test_empty_authors(self):
        row = {"authors": "[]", "published_date": ""}
        result = _paper_to_ref_dict(row)
        self.assertEqual(result["authors"], [])
        self.assertEqual(result["year"], "")

    def test_invalid_json_authors(self):
        row = {"authors": "not json", "published_date": "2021-01-01"}
        result = _paper_to_ref_dict(row)
        self.assertEqual(result["authors"], [])
        self.assertEqual(result["year"], "2021")


class TestFormatAuthorYear(unittest.TestCase):
    def test_normalized_surname_given(self):
        """Normalized 'Surname, Given' format → use surname."""
        paper = {"authors": ["Smith, John", "Doe, Alice"], "year": "2023"}
        result = _format_author_year(paper)
        self.assertEqual(result, "Smith(2023)")

    def test_legacy_given_surname(self):
        """Legacy 'Given Surname' format → heuristic fallback."""
        paper = {"authors": ["Kenneth Prkachin"], "year": "2023"}
        result = _format_author_year(paper)
        self.assertEqual(result, "Prkachin(2023)")

    def test_legacy_pubmed_style(self):
        """Legacy 'LastName Initials' (PubMed) format → heuristic fallback."""
        paper = {"authors": ["Marshall K"], "year": "2022"}
        result = _format_author_year(paper)
        self.assertEqual(result, "Marshall(2022)")

    def test_cjk_name(self):
        """CJK name → keep full name."""
        paper = {"authors": ["张三"], "year": "2022"}
        result = _format_author_year(paper)
        self.assertEqual(result, "张三(2022)")

    def test_single_name(self):
        paper = {"authors": ["Zhang"], "year": "2022"}
        result = _format_author_year(paper)
        self.assertEqual(result, "Zhang(2022)")

    def test_no_authors(self):
        paper = {"authors": [], "year": "2023"}
        result = _format_author_year(paper)
        self.assertEqual(result, "Unknown(2023)")

    def test_no_year(self):
        paper = {"authors": ["Smith, J"], "year": ""}
        result = _format_author_year(paper)
        self.assertEqual(result, "Smith(n.d.)")


class TestGenerateRefList(unittest.TestCase):
    def _run_async(self, coro):
        return asyncio.run(coro)

    def test_no_storage(self):
        """Should return error when storage is not initialized."""
        with patch("paper_toolkit_mcp.tools.manuscript._storage", None):
            result = self._run_async(generate_ref_list("fake.md"))
            self.assertIn("error", result)

    def test_file_not_found(self):
        """Should return error for non-existent file."""
        mock_storage = MagicMock()
        with patch("paper_toolkit_mcp.tools.manuscript._storage", mock_storage):
            result = self._run_async(generate_ref_list("/nonexistent/file.md"))
            self.assertIn("error", result)
            self.assertIn("not found", result["error"])

    def test_no_cite_keys(self):
        """Should return no_citations_found for file without cite_keys."""
        mock_storage = MagicMock()
        with patch("paper_toolkit_mcp.tools.manuscript._storage", mock_storage):
            path = _create_temp_md("这是一段没有引用的文本。")
            try:
                result = self._run_async(generate_ref_list(path))
                self.assertEqual(result["status"], "no_citations_found")
            finally:
                os.unlink(path)

    def test_successful_generation(self):
        """Should generate reference list with correct numbering."""
        mock_storage = MagicMock()
        mock_storage.get_by_cite_key.side_effect = lambda key: {
            "Kxq": {
                "cite_key": "Kxq",
                "paper_id": "10.1234/a",
                "title": "Paper Alpha",
                "authors": '["Smith, J"]',
                "published_date": "2023-01-01",
                "source": "Nature",
                "doi": "10.1234/a",
                "url": "",
                "abstract": "",
            },
            "JHw": {
                "cite_key": "JHw",
                "paper_id": "10.1234/b",
                "title": "Paper Beta",
                "authors": '["Doe, A"]',
                "published_date": "2022-06-15",
                "source": "Science",
                "doi": "10.1234/b",
                "url": "",
                "abstract": "",
            },
        }.get(key)

        with patch("paper_toolkit_mcp.tools.manuscript._storage", mock_storage):
            path = _create_temp_md("研究[@Kxq]表明[@JHw]有效。")
            try:
                result = self._run_async(generate_ref_list(path))
                self.assertEqual(result["status"], "completed")
                self.assertEqual(result["report"]["resolved"], 2)
                self.assertEqual(result["report"]["unresolved"], 0)

                with open(result["output_file"], encoding="utf-8") as out:
                    content = out.read()
                self.assertIn("[1]", content)
                self.assertIn("[2]", content)
                self.assertIn("参考文献", content)
                self.assertIn("Paper Alpha", content)
                self.assertIn("Paper Beta", content)
                self.assertNotIn("[@Kxq]", content)
                self.assertNotIn("[@JHw]", content)
            finally:
                os.unlink(path)
                if "output_file" in result and os.path.exists(result["output_file"]):
                    os.unlink(result["output_file"])

    def test_unresolved_cite_key(self):
        """Should report unresolved cite_keys."""
        mock_storage = MagicMock()
        mock_storage.get_by_cite_key.return_value = None

        with patch("paper_toolkit_mcp.tools.manuscript._storage", mock_storage):
            path = _create_temp_md("研究[@UNK]表明。")
            try:
                result = self._run_async(generate_ref_list(path))
                self.assertEqual(result["status"], "completed")
                self.assertEqual(result["report"]["unresolved"], 1)
                self.assertIn("UNK", result["report"]["unresolved_keys"])
            finally:
                os.unlink(path)


class TestGenerateHumanReview(unittest.TestCase):
    def _run_async(self, coro):
        return asyncio.run(coro)

    def test_no_storage(self):
        with patch("paper_toolkit_mcp.tools.manuscript._storage", None):
            result = self._run_async(generate_human_review("fake.md"))
            self.assertIn("error", result)

    def test_successful_replacement(self):
        """Should replace cite_keys with author-year-DOI markers."""
        mock_storage = MagicMock()
        mock_storage.get_by_cite_key.side_effect = lambda key: {
            "Kxq": {
                "cite_key": "Kxq",
                "paper_id": "10.1234/a",
                "title": "Paper Alpha",
                "authors": '["Smith, J"]',
                "published_date": "2023-01-01",
                "source": "Nature",
                "doi": "10.1234/a",
                "url": "",
                "abstract": "",
            },
        }.get(key)

        with patch("paper_toolkit_mcp.tools.manuscript._storage", mock_storage):
            path = _create_temp_md("研究[@Kxq]表明。")
            try:
                result = self._run_async(generate_human_review(path))
                self.assertEqual(result["status"], "completed")
                self.assertEqual(result["report"]["resolved"], 1)

                with open(result["output_file"], encoding="utf-8") as out:
                    content = out.read()
                self.assertIn("Smith(2023)", content)
                self.assertIn("DOI:10.1234/a", content)
                self.assertNotIn("[@Kxq]", content)
            finally:
                os.unlink(path)
                if "output_file" in result and os.path.exists(result["output_file"]):
                    os.unlink(result["output_file"])

    def test_unresolved_cite_key_marker(self):
        """Should mark unresolved cite_keys with warning."""
        mock_storage = MagicMock()
        mock_storage.get_by_cite_key.return_value = None

        with patch("paper_toolkit_mcp.tools.manuscript._storage", mock_storage):
            path = _create_temp_md("研究[@UNK]表明。")
            try:
                result = self._run_async(generate_human_review(path))
                self.assertEqual(result["status"], "completed")
                self.assertEqual(result["report"]["unresolved"], 1)

                with open(result["output_file"], encoding="utf-8") as out:
                    content = out.read()
                self.assertIn("NOT_FOUND", content)
            finally:
                os.unlink(path)
                if "output_file" in result and os.path.exists(result["output_file"]):
                    os.unlink(result["output_file"])

    def test_no_doi_fallback_to_title(self):
        """Should use title snippet when DOI is not available."""
        mock_storage = MagicMock()
        mock_storage.get_by_cite_key.return_value = {
            "cite_key": "Kxq",
            "paper_id": "arxiv:1234",
            "title": "A Very Long Paper Title That Exceeds Thirty Characters",
            "authors": '["Smith, J"]',
            "published_date": "2023-01-01",
            "source": "arxiv",
            "doi": "",
            "url": "",
            "abstract": "",
        }

        with patch("paper_toolkit_mcp.tools.manuscript._storage", mock_storage):
            path = _create_temp_md("研究[@Kxq]表明。")
            try:
                result = self._run_async(generate_human_review(path))
                with open(result["output_file"], encoding="utf-8") as out:
                    content = out.read()
                self.assertIn("A Very Long Paper Title That ", content)
                self.assertIn("...", content)
            finally:
                os.unlink(path)
                if "output_file" in result and os.path.exists(result["output_file"]):
                    os.unlink(result["output_file"])

    def test_mapping_in_report(self):
        """Should include cite_key to author-year mapping in report."""
        mock_storage = MagicMock()
        mock_storage.get_by_cite_key.return_value = {
            "cite_key": "Kxq",
            "paper_id": "10.1234/a",
            "title": "Paper Alpha",
            "authors": '["Smith, J"]',
            "published_date": "2023-01-01",
            "source": "Nature",
            "doi": "10.1234/a",
            "url": "",
            "abstract": "",
        }

        with patch("paper_toolkit_mcp.tools.manuscript._storage", mock_storage):
            path = _create_temp_md("研究[@Kxq]表明。")
            try:
                result = self._run_async(generate_human_review(path))
                self.assertIn("mapping", result["report"])
                mapping = result["report"]["mapping"]
                self.assertEqual(len(mapping), 1)
                self.assertEqual(mapping[0]["cite_key"], "Kxq")
                self.assertEqual(mapping[0]["doi"], "10.1234/a")
            finally:
                os.unlink(path)
                if "output_file" in result and os.path.exists(result["output_file"]):
                    os.unlink(result["output_file"])


if __name__ == "__main__":
    unittest.main()
