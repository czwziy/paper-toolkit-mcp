"""Offline tests for server source registration.

Network-dependent server tests live in tests/integration/test_server.py.
These tests verify source registration correctness without touching any external API.
"""
import unittest

from paper_toolkit_mcp import server


class TestServerSourceRegistration(unittest.TestCase):
    def test_all_sources_include_retained_platforms(self):
        """The 8 retained sources after the cleanup must be registered."""
        retained = [
            "arxiv", "pubmed", "medrxiv", "semantic",
            "crossref", "openalex", "pmc", "dblp",
        ]
        for src in retained:
            self.assertIn(src, server.ALL_SOURCES)

    def test_removed_sources_not_in_all_sources(self):
        """Sources removed during cleanup must not appear in ALL_SOURCES."""
        removed = [
            "openaire", "citeseerx", "doaj", "base",
            "zenodo", "hal", "ssrn", "unpaywall",
        ]
        for src in removed:
            self.assertNotIn(src, server.ALL_SOURCES)

    def test_parse_sources_filters_unknown(self):
        # Removed sources and truly invalid names are filtered out;
        # only the retained 'dblp' survives.
        parsed = server._parse_sources(
            "dblp,doaj,base,zenodo,hal,ssrn,unpaywall,invalid"
        )
        self.assertEqual(parsed, ["dblp"])


if __name__ == "__main__":
    unittest.main()
