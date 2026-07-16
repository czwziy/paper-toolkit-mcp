# tests/unit/test_paper_normalize.py
"""Unit tests for paper.py normalize_author_name and Paper.__post_init__ normalization."""
import unittest

from paper_toolkit_mcp.paper import Paper, normalize_author_name


class TestNormalizeAuthorName(unittest.TestCase):
    # Rule 1: CJK names
    def test_cjk_name_unchanged(self):
        self.assertEqual(normalize_author_name("张三"), "张三")
        self.assertEqual(normalize_author_name("田中太郎"), "田中太郎")

    # Rule 2: Single word
    def test_single_word(self):
        self.assertEqual(normalize_author_name("Zhang"), "Zhang")
        self.assertEqual(normalize_author_name("A"), "A")

    # Rule 3: "LastName Initials" (PubMed style)
    def test_pubmed_single_initial(self):
        self.assertEqual(normalize_author_name("Marshall K"), "Marshall, K")

    def test_pubmed_two_initials(self):
        self.assertEqual(normalize_author_name("McDonnell MJ"), "McDonnell, MJ")

    def test_pubmed_initial_with_period(self):
        self.assertEqual(normalize_author_name("Smith J."), "Smith, J.")

    # Rule 4: "Initial Surname" (Semantic Scholar style)
    def test_semantic_single_initial(self):
        self.assertEqual(normalize_author_name("J Jakusova"), "Jakusova, J")

    def test_semantic_two_initials(self):
        self.assertEqual(normalize_author_name("MJ Smith"), "Smith, MJ")

    def test_semantic_initial_with_period(self):
        self.assertEqual(normalize_author_name("J. Smith"), "Smith, J.")

    # Rule 5: "Given Surname" (arXiv/CrossRef/OpenAlex style)
    def test_given_surname(self):
        self.assertEqual(normalize_author_name("Kenneth Prkachin"), "Prkachin, Kenneth")

    def test_multi_word_given_surname(self):
        self.assertEqual(normalize_author_name("Md Sirajus Salekin"), "Salekin, Md Sirajus")

    def test_three_word_name(self):
        self.assertEqual(normalize_author_name("Jean Pierre Dupont"), "Dupont, Jean Pierre")

    # Edge cases
    def test_empty_string(self):
        self.assertEqual(normalize_author_name(""), "")

    def test_whitespace_only(self):
        self.assertEqual(normalize_author_name("  "), "")

    def test_leading_trailing_whitespace(self):
        self.assertEqual(normalize_author_name("  Smith J  "), "Smith, J")

    def test_two_initials_with_periods(self):
        self.assertEqual(normalize_author_name("M.J. Smith"), "Smith, M.J.")


class TestPaperPostInitNormalization(unittest.TestCase):
    def test_authors_normalized_on_creation(self):
        paper = Paper(
            paper_id="test1",
            title="Test",
            authors=["Marshall K", "J Jakusova", "Kenneth Prkachin"],
            abstract="",
            doi="",
            published_date=None,
            pdf_url="",
            url="",
            source="test",
        )
        self.assertEqual(paper.authors, ["Marshall, K", "Jakusova, J", "Prkachin, Kenneth"])

    def test_cjk_authors_unchanged(self):
        paper = Paper(
            paper_id="test2",
            title="Test",
            authors=["张三", "李四"],
            abstract="",
            doi="",
            published_date=None,
            pdf_url="",
            url="",
            source="test",
        )
        self.assertEqual(paper.authors, ["张三", "李四"])

    def test_none_authors_becomes_empty_list(self):
        paper = Paper(
            paper_id="test3",
            title="Test",
            authors=None,
            abstract="",
            doi="",
            published_date=None,
            pdf_url="",
            url="",
            source="test",
        )
        self.assertEqual(paper.authors, [])

    def test_empty_authors_stays_empty(self):
        paper = Paper(
            paper_id="test4",
            title="Test",
            authors=[],
            abstract="",
            doi="",
            published_date=None,
            pdf_url="",
            url="",
            source="test",
        )
        self.assertEqual(paper.authors, [])


if __name__ == "__main__":
    unittest.main()
