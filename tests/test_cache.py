# tests/test_cache.py
import unittest
import tempfile
import shutil
import os
import time
from datetime import datetime, timedelta
from unittest.mock import patch

from paper_toolkit_mcp.cache import SearchCache


class TestSearchCache(unittest.TestCase):
    def setUp(self):
        """Create a temporary directory for cache tests."""
        self.test_dir = tempfile.mkdtemp(prefix="cache_test_")
        self.cache = SearchCache(cache_dir=self.test_dir, ttl_hours=24)
    
    def tearDown(self):
        """Clean up temporary directory."""
        shutil.rmtree(self.test_dir, ignore_errors=True)
    
    def test_cache_set_and_get(self):
        """Test basic cache set and get operations."""
        papers = [
            {"title": "Test Paper 1", "paper_id": "1"},
            {"title": "Test Paper 2", "paper_id": "2"},
        ]
        
        cache_path = self.cache.set("machine learning", "arxiv", papers, max_results=5)
        self.assertTrue(os.path.exists(cache_path))
        
        retrieved = self.cache.get("machine learning", "arxiv", max_results=5)
        self.assertIsNotNone(retrieved)
        self.assertEqual(len(retrieved), 2)
        self.assertEqual(retrieved[0]["title"], "Test Paper 1")
    
    def test_cache_miss(self):
        """Test cache miss for non-existent key."""
        result = self.cache.get("nonexistent query", "arxiv")
        self.assertIsNone(result)
    
    def test_cache_ttl_expired(self):
        """Test that expired cache entries are not returned."""
        papers = [{"title": "Expired Paper", "paper_id": "1"}]
        
        self.cache.set("query", "source", papers)
        
        cache_files = list(os.listdir(self.test_dir))
        if cache_files:
            cache_file = os.path.join(self.test_dir, cache_files[0])
            with open(cache_file, "r", encoding="utf-8") as f:
                import json
                cached = json.load(f)
                cached["timestamp"] = (datetime.now() - timedelta(hours=25)).isoformat()
                with open(cache_file, "w", encoding="utf-8") as f:
                    json.dump(cached, f)
        
        result = self.cache.get("query", "source")
        self.assertIsNone(result)
    
    def test_cache_different_params(self):
        """Test that different parameters create different cache keys."""
        papers1 = [{"title": "5 results", "paper_id": "1"}]
        papers2 = [{"title": "10 results", "paper_id": "1"}, {"title": "10 results", "paper_id": "2"}]
        
        self.cache.set("query", "source", papers1, max_results=5)
        self.cache.set("query", "source", papers2, max_results=10)
        
        result5 = self.cache.get("query", "source", max_results=5)
        result10 = self.cache.get("query", "source", max_results=10)
        
        self.assertEqual(len(result5), 1)
        self.assertEqual(len(result10), 2)
    
    def test_cache_clear(self):
        """Test clearing all cache."""
        self.cache.set("query1", "source", [{"title": "1"}])
        self.cache.set("query2", "source", [{"title": "2"}])
        
        count = self.cache.clear()
        self.assertGreaterEqual(count, 2)
        
        remaining = len(os.listdir(self.test_dir))
        self.assertEqual(remaining, 0)
    
    def test_list_cache(self):
        """Test listing cache items."""
        self.cache.set("query1", "arxiv", [{"title": "1"}])
        self.cache.set("query2", "pubmed", [{"title": "2"}])
        
        items = self.cache.list_cache()
        self.assertEqual(len(items), 2)
        
        sources = [item["source"] for item in items]
        self.assertIn("arxiv", sources)
        self.assertIn("pubmed", sources)
    
    def test_get_stats(self):
        """Test getting cache statistics."""
        self.cache.set("query1", "source", [{"title": "1"}])
        
        stats = self.cache.get_stats()
        self.assertIn("total_entries", stats)
        self.assertIn("valid_entries", stats)
        self.assertIn("total_cached_papers", stats)
        self.assertEqual(stats["total_entries"], 1)
        self.assertEqual(stats["total_cached_papers"], 1)
    
    def test_cache_file_format(self):
        """Test that cache files are valid JSON."""
        papers = [{"title": "Test", "paper_id": "1", "authors": "Author"}]
        cache_path = self.cache.set("query", "source", papers)
        
        import json
        with open(cache_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        self.assertIn("timestamp", data)
        self.assertIn("query", data)
        self.assertIn("source", data)
        self.assertIn("papers", data)
        self.assertEqual(data["paper_count"], 1)


if __name__ == "__main__":
    unittest.main()
