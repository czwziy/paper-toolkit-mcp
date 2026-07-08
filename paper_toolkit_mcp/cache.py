"""Search cache module for storing and retrieving paper search results."""
import json
import os
import hashlib
from datetime import datetime, timedelta
from typing import List, Optional, Any
from pathlib import Path

from .config import get_work_dir


class SearchCache:
    """Manages search result caching with TTL support.

    Cache is stored under ``<WORK_DIR>/.paper_cache/`` so it follows the
    user's project folder (set via ``paper_toolkit_mcp_WORK_DIR``). Falls back
    to the current working directory when WORK_DIR is unset.
    """

    def __init__(
        self,
        cache_dir: str = None,
        ttl_hours: int = 24,
    ):
        """Initialize cache.

        Args:
            cache_dir: Cache directory path. If None, uses
                       ``<WORK_DIR>/.paper_cache`` (or CWD/.paper_cache).
            ttl_hours: Cache time-to-live in hours.
        """
        if cache_dir is None:
            self.cache_dir = Path(get_work_dir()) / ".paper_cache"
        else:
            self.cache_dir = Path(cache_dir)
        self.ttl = timedelta(hours=ttl_hours)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
    
    def _get_cache_key(self, query: str, source: str, **kwargs) -> str:
        """Generate cache key from query and parameters."""
        params_str = json.dumps(kwargs, sort_keys=True)
        raw_key = f"{source}:{query}:{params_str}"
        return hashlib.md5(raw_key.encode()).hexdigest()
    
    def _get_cache_path(self, cache_key: str) -> Path:
        """Get cache file path for a given key."""
        return self.cache_dir / f"{cache_key}.json"
    
    def get(
        self,
        query: str,
        source: str,
        **kwargs,
    ) -> Optional[List[dict]]:
        """Get cached search results if available and not expired.
        
        Args:
            query: Search query string.
            source: Source platform name.
            **kwargs: Additional search parameters.
            
        Returns:
            List of paper dicts if cache hit, None otherwise.
        """
        cache_key = self._get_cache_key(query, source, **kwargs)
        cache_path = self._get_cache_path(cache_key)
        
        if not cache_path.exists():
            return None
        
        try:
            with open(cache_path, "r", encoding="utf-8") as f:
                cached = json.load(f)
            
            cached_time = datetime.fromisoformat(cached["timestamp"])
            if datetime.now() - cached_time > self.ttl:
                return None
            
            return cached["papers"]
        except (json.JSONDecodeError, KeyError, ValueError):
            return None
    
    def set(
        self,
        query: str,
        source: str,
        papers: List[dict],
        **kwargs,
    ) -> str:
        """Cache search results.
        
        Args:
            query: Search query string.
            source: Source platform name.
            papers: List of paper dicts to cache.
            **kwargs: Additional search parameters.
            
        Returns:
            Path to cache file.
        """
        cache_key = self._get_cache_key(query, source, **kwargs)
        cache_path = self._get_cache_path(cache_key)
        
        cache_data = {
            "timestamp": datetime.now().isoformat(),
            "query": query,
            "source": source,
            "params": kwargs,
            "paper_count": len(papers),
            "papers": papers,
        }
        
        with open(cache_path, "w", encoding="utf-8") as f:
            json.dump(cache_data, f, ensure_ascii=False, indent=2)
        
        return str(cache_path)
    
    def clear(self) -> int:
        """Clear all cached files.
        
        Returns:
            Number of files cleared.
        """
        count = 0
        for file in self.cache_dir.glob("*.json"):
            try:
                file.unlink()
                count += 1
            except OSError:
                pass
        return count
    
    def list_cache(self) -> List[dict]:
        """List all cached items.
        
        Returns:
            List of cache info dicts.
        """
        caches = []
        for file in self.cache_dir.glob("*.json"):
            try:
                with open(file, "r", encoding="utf-8") as f:
                    cached = json.load(f)
                
                cached_time = datetime.fromisoformat(cached["timestamp"])
                is_expired = datetime.now() - cached_time > self.ttl
                
                caches.append({
                    "file": str(file),
                    "query": cached.get("query", ""),
                    "source": cached.get("source", ""),
                    "paper_count": cached.get("paper_count", 0),
                    "timestamp": cached.get("timestamp", ""),
                    "is_expired": is_expired,
                })
            except (json.JSONDecodeError, KeyError, ValueError):
                pass
        
        return sorted(caches, key=lambda x: x["timestamp"], reverse=True)
    
    def get_stats(self) -> dict:
        """Get cache statistics.
        
        Returns:
            Dict with cache stats.
        """
        caches = self.list_cache()
        total = len(caches)
        expired = sum(1 for c in caches if c["is_expired"])
        total_papers = sum(c["paper_count"] for c in caches)
        
        return {
            "total_entries": total,
            "expired_entries": expired,
            "valid_entries": total - expired,
            "total_cached_papers": total_papers,
            "cache_dir": str(self.cache_dir),
        }
