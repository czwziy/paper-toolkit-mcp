import unittest
from datetime import datetime
from unittest.mock import patch

from paper_toolkit_mcp import server
from paper_toolkit_mcp.paper import Paper


class TestUnpaywallResolver(unittest.TestCase):
    """Tests for the retained UnpaywallResolver (fallback download chain).

    The ``search_unpaywall`` MCP tool was removed during tool-count reduction,
    but ``server.unpaywall_resolver`` is still used by ``download_with_fallback``
    to resolve open-access PDF URLs.
    """

    def test_get_paper_by_doi_none_without_email(self):
        """When email is not configured, get_paper_by_doi returns None."""
        with patch.object(server.unpaywall_resolver, "email", ""):
            self.assertIsNone(server.unpaywall_resolver.get_paper_by_doi("10.1000/test"))

    def test_get_paper_by_doi_none_without_doi(self):
        """An empty or blank DOI yields None even when email is configured."""
        with patch.object(server.unpaywall_resolver, "email", "test@example.com"):
            self.assertIsNone(server.unpaywall_resolver.get_paper_by_doi(""))
            self.assertIsNone(server.unpaywall_resolver.get_paper_by_doi("   "))

    def test_get_paper_by_doi_maps_record_to_paper(self):
        """get_paper_by_doi maps the raw Unpaywall payload to a Paper object."""
        mock_data = {
            "title": "Unpaywall Record",
            "z_authors": [
                {"given": "Alice", "family": "Example"},
                {"given": "Bob", "family": "Author"},
            ],
            "published_date": "2023-01-01",
            "best_oa_location": {
                "url": "https://example.org/paper",
                "url_for_pdf": "https://example.org/paper.pdf",
                "host_type": "repository",
                "license": "cc-by",
                "version": "publishedVersion",
            },
            "doi_url": "https://doi.org/10.1000/test",
            "is_oa": True,
            "oa_status": "green",
            "journal_name": "Example Journal",
            "publisher": "Example Publisher",
        }

        with patch.object(server.unpaywall_resolver, "email", "test@example.com"), \
             patch.object(server.unpaywall_resolver, "_fetch_doi_record", return_value=mock_data):
            result = server.unpaywall_resolver.get_paper_by_doi("10.1000/test")

        self.assertIsNotNone(result)
        self.assertIsInstance(result, Paper)
        self.assertEqual(result.doi, "10.1000/test")
        self.assertEqual(result.source, "unpaywall")
        self.assertEqual(result.title, "Unpaywall Record")
        self.assertEqual(result.authors, ["Alice Example", "Bob Author"])
        self.assertEqual(result.pdf_url, "https://example.org/paper.pdf")
        self.assertEqual(result.url, "https://example.org/paper")
        self.assertEqual(result.published_date, datetime(2023, 1, 1))

    def test_get_paper_by_doi_returns_none_when_record_missing(self):
        """A 404/None record from _fetch_doi_record yields None."""
        with patch.object(server.unpaywall_resolver, "email", "test@example.com"), \
             patch.object(server.unpaywall_resolver, "_fetch_doi_record", return_value=None):
            self.assertIsNone(server.unpaywall_resolver.get_paper_by_doi("10.1000/missing"))

    def test_resolve_best_pdf_url_none_without_email(self):
        """resolve_best_pdf_url returns None when email is not configured."""
        with patch.object(server.unpaywall_resolver, "email", ""):
            self.assertIsNone(server.unpaywall_resolver.resolve_best_pdf_url("10.1000/test"))

    def test_resolve_best_pdf_url_none_without_doi(self):
        """An empty DOI yields None."""
        with patch.object(server.unpaywall_resolver, "email", "test@example.com"):
            self.assertIsNone(server.unpaywall_resolver.resolve_best_pdf_url(""))
            self.assertIsNone(server.unpaywall_resolver.resolve_best_pdf_url("   "))


if __name__ == "__main__":
    unittest.main()
