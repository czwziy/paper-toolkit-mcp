# tests/test_reference.py
import unittest
import os
import tempfile
from paper_toolkit_mcp.reference import (
    parse_citation_placeholders,
    generate_bibtex,
    generate_ris,
    format_citation_gb7714,
    format_citation_apa,
    format_citation_ieee,
    generate_reference_list,
    process_manuscript_text,
    get_paper_by_identifier,
)


class TestParseCitationPlaceholders(unittest.TestCase):
    def test_parse_doi_placeholder(self):
        text = "研究表明[@doi:10.1038/nature12373]，深度学习取得了进展。"
        results = parse_citation_placeholders(text)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["type"], "doi")
        self.assertEqual(results[0]["identifier"], "10.1038/nature12373")
    
    def test_parse_pmid_placeholder(self):
        text = "根据研究[@pmid:32145678]，该方法有效。"
        results = parse_citation_placeholders(text)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["type"], "pmid")
        self.assertEqual(results[0]["identifier"], "32145678")
    
    def test_parse_arxiv_placeholder(self):
        text = "Transformer架构[@arxiv:2106.12345]改变了NLP。"
        results = parse_citation_placeholders(text)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["type"], "arxiv")
        self.assertEqual(results[0]["identifier"], "2106.12345")
    
    def test_parse_title_placeholder(self):
        text = "正如论文[@title:Attention Is All You Need]所述..."
        results = parse_citation_placeholders(text)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["type"], "title")
        self.assertEqual(results[0]["identifier"], "Attention Is All You Need")
    
    def test_parse_multiple_placeholders(self):
        text = "研究[@doi:10.1234]表明[@pmid:5678]，方法[@arxiv:2106.00001]有效。"
        results = parse_citation_placeholders(text)
        self.assertEqual(len(results), 3)
    
    def test_no_placeholders(self):
        text = "这是一段没有引用的文本。"
        results = parse_citation_placeholders(text)
        self.assertEqual(len(results), 0)


class TestGenerateBibtex(unittest.TestCase):
    def setUp(self):
        self.test_paper = {
            "title": "Attention Is All You Need",
            "authors": "Vaswani A, Shazeer N, Parmar N",
            "year": 2017,
            "source": "arxiv",
            "paper_id": "1706.03762",
            "doi": "10.1234/example",
            "journal": "arXiv preprint",
        }
    
    def test_bibtex_contains_required_fields(self):
        bibtex = generate_bibtex([self.test_paper])
        self.assertIn("@article", bibtex)
        self.assertIn("title", bibtex)
        self.assertIn("author", bibtex)
        self.assertIn("year", bibtex)
        self.assertIn("Attention Is All You Need", bibtex)


class TestGenerateRIS(unittest.TestCase):
    def setUp(self):
        self.test_paper = {
            "title": "Test Paper",
            "authors": "Author A, Author B",
            "year": 2023,
            "source": "pubmed",
            "paper_id": "12345",
            "doi": "10.1234/test",
        }
    
    def test_ris_contains_required_tags(self):
        ris = generate_ris([self.test_paper])
        self.assertIn("TY  -", ris)
        self.assertIn("TI  - Test Paper", ris)
        self.assertIn("ER  -", ris)


class TestCitationFormatting(unittest.TestCase):
    def setUp(self):
        self.journal_paper = {
            "title": "Deep Learning in Medicine",
            "authors": "Smith J, Doe A, Wang L",
            "year": 2023,
            "journal": "Nature Medicine",
            "volume": "29",
            "issue": "3",
            "pages": "456-467",
            "doi": "10.1038/nm1234",
            "source": "pubmed",
        }
        
        self.conference_paper = {
            "title": "Attention Is All You Need",
            "authors": "Vaswani A, Shazeer N",
            "year": 2017,
            "source": "arxiv",
            "paper_id": "1706.03762",
        }
    
    def test_gb7714_journal_format(self):
        formatted = format_citation_gb7714(self.journal_paper)
        self.assertIn("SMITH", formatted)
        self.assertIn("Deep Learning in Medicine", formatted)
    
    def test_gb7714_conference_format(self):
        formatted = format_citation_gb7714(self.conference_paper)
        self.assertIn("VASWANI", formatted)
        self.assertIn("Attention Is All You Need", formatted)
    
    def test_apa_format(self):
        formatted = format_citation_apa(self.journal_paper)
        self.assertIn("Smith", formatted)
        self.assertIn("(2023)", formatted)
    
    def test_ieee_format(self):
        formatted = format_citation_ieee(self.journal_paper)
        self.assertIn("J. Smith", formatted)
        self.assertIn("2023", formatted)


class TestGenerateReferenceList(unittest.TestCase):
    def setUp(self):
        self.papers = [
            {
                "title": "Paper One",
                "authors": "Author A",
                "year": 2023,
                "source": "arxiv",
            },
            {
                "title": "Paper Two",
                "authors": "Author B",
                "year": 2022,
                "source": "pubmed",
            },
        ]
    
    def test_reference_list_numbered(self):
        ref_list = generate_reference_list(self.papers, style="gb7714")
        self.assertIn("[1]", ref_list)
        self.assertIn("[2]", ref_list)
    
    def test_reference_list_contains_all_papers(self):
        ref_list = generate_reference_list(self.papers, style="apa")
        self.assertIn("Paper One", ref_list)
        self.assertIn("Paper Two", ref_list)


class TestProcessManuscriptText(unittest.TestCase):
    def test_replace_placeholders_with_numbers(self):
        text = "研究[@doi:10.1234]表明[@pmid:5678]。"
        papers = [
            {"citation_key": "doi:10.1234", "title": "Paper 1"},
            {"citation_key": "pmid:5678", "title": "Paper 2"},
        ]
        result = process_manuscript_text(text, papers)
        self.assertIn("[1]", result["formatted_text"])
        self.assertIn("[2]", result["formatted_text"])
    
    def test_preserves_unmatched_placeholders(self):
        text = "研究[@doi:10.1234]表明[@doi:9999]。"
        papers = [
            {"citation_key": "doi:10.1234", "title": "Paper 1"},
        ]
        result = process_manuscript_text(text, papers)
        self.assertIn("[1]", result["formatted_text"])
    
    def test_generates_reference_list(self):
        text = "研究[@doi:10.1234]表明。"
        papers = [
            {"citation_key": "doi:10.1234", "title": "Paper 1", "authors": "Author", "year": 2023, "source": "arxiv"},
        ]
        result = process_manuscript_text(text, papers)
        self.assertIn("## References", result["formatted_text"])


class TestGetPaperByIdentifier(unittest.TestCase):
    @unittest.skip("Requires network access to CrossRef API")
    def test_get_by_doi(self):
        paper = get_paper_by_identifier("doi", "10.1038/nature12373")
        self.assertIsNotNone(paper)
        self.assertIn("title", paper)


if __name__ == "__main__":
    unittest.main()
