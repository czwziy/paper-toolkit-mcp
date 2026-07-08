"""Base class for all academic paper source searchers."""
from abc import ABC, abstractmethod
from typing import List, Optional
from ..paper import Paper


class PaperSource(ABC):
    """Abstract base class for academic paper sources."""
    
    def __init__(self, cache=None):
        """Initialize searcher with optional cache.
        
        Args:
            cache: Optional SearchCache instance for caching search results.
        """
        self._cache = cache
    
    def search_with_cache(
        self,
        query: str,
        **kwargs,
    ) -> List[Paper]:
        """Search with caching support.

        Checks the cache first (keyed by source, query, and all kwargs); on a
        miss, calls the abstract search() method and caches the result.

        All kwargs (e.g. max_results, year, sort_by) are used BOTH as the
        search() arguments AND as part of the cache key, so searches with
        different parameters never collide in the cache.

        Args:
            query: Search query string.
            **kwargs: Source-specific parameters (e.g., max_results, year).

        Returns:
            List of Paper objects.
        """
        cache = getattr(self, "_cache", None)

        if cache is not None:
            cached_papers = cache.get(query, self.source_name, **kwargs)
            if cached_papers is not None:
                return [Paper.from_dict(p) for p in cached_papers]

        papers = self.search(query, **kwargs)

        if cache is not None and papers:
            paper_dicts = [p.to_dict() for p in papers]
            cache.set(query, self.source_name, paper_dicts, **kwargs)

        return papers
    
    @property
    def source_name(self) -> str:
        """Return the source name for cache key. Override in subclasses."""
        return self.__class__.__name__.replace("Searcher", "").lower()
    
    @abstractmethod
    def search(self, query: str, **kwargs) -> List[Paper]:
        """Search papers matching the query.

        Args:
            query: Search query string.
            **kwargs: Source-specific parameters (e.g., max_results, year).

        Returns:
            List of Paper objects.
        """

    def download_pdf(self, paper_id: str, save_path: str) -> str:
        """Download the PDF for a given paper.

        Args:
            paper_id: Platform-specific paper identifier.
            save_path: Directory to save the downloaded PDF.

        Returns:
            Path to the saved PDF file.

        Raises:
            NotImplementedError: If the source does not support PDF downloads.
        """
        raise NotImplementedError(
            f"{self.__class__.__name__} does not support PDF downloads."
        )

    def read_paper(self, paper_id: str, save_path: str = "./downloads") -> str:
        """Download and extract text from a paper PDF.

        Args:
            paper_id: Platform-specific paper identifier.
            save_path: Directory where the PDF is/will be saved.

        Returns:
            Extracted text content of the paper.

        Raises:
            NotImplementedError: If the source does not support paper reading.
        """
        raise NotImplementedError(
            f"{self.__class__.__name__} does not support reading paper content."
        )
