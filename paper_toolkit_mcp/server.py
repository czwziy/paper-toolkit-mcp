# paper_toolkit_mcp/server.py
"""MCP server entry point — wires searchers, storage, and tools together.

This module is intentionally thin: it instantiates searchers and storage,
registers MCP tools via the ``tools`` subpackage, and re-exports public
names for backward compatibility (tests access ``server.*``).
"""
import logging
import os

from mcp.server.fastmcp import FastMCP

# Re-export helpers for backward compatibility (tests import from server)
from ._helpers import (  # noqa: F401
    _JSON_DICT_FIELDS,
    _JSON_LIST_FIELDS,
    _STRING_MERGE_FIELDS,
    ALL_SOURCES,
    SOURCE_GROUPS,
    _filter_by_year,
    _merge_json_dict,
    _merge_json_list,
    _merge_papers,
    _parse_sources,
    _safe_filename,
    _simplify_for_ai,
    async_search,
)
from .academic_platforms.arxiv import ArxivSearcher
from .academic_platforms.core import CORESearcher
from .academic_platforms.crossref import CrossRefSearcher
from .academic_platforms.dblp import DBLPSearcher
from .academic_platforms.europepmc import EuropePMCSearcher
from .academic_platforms.medrxiv import MedRxivSearcher
from .academic_platforms.openaire import OpenAiresearcher
from .academic_platforms.openalex import OpenAlexSearcher
from .academic_platforms.pmc import PMCSearcher
from .academic_platforms.pubmed import PubMedSearcher
from .academic_platforms.semantic import SemanticSearcher
from .academic_platforms.unpaywall import UnpaywallResolver
from .config import get_env, get_work_dir
from .storage import PaperStorage

# Initialize MCP server
mcp = FastMCP("paper_toolkit_server")
logger = logging.getLogger(__name__)

# Default download directory, resolved once at import from WORK_DIR (or CWD).
DEFAULT_SAVE_PATH = os.path.join(get_work_dir(), "downloads")

# Default cache directory, resolved once at import from WORK_DIR (or CWD).
DEFAULT_CACHE_DIR = os.path.join(get_work_dir(), ".paper_cache")

# Unified SQLite storage for paper metadata, local PDF paths, and full text.
storage = PaperStorage()

# Instances of searchers
arxiv_searcher = ArxivSearcher()
pubmed_searcher = PubMedSearcher()
medrxiv_searcher = MedRxivSearcher()
semantic_searcher = SemanticSearcher()
crossref_searcher = CrossRefSearcher()
openalex_searcher = OpenAlexSearcher()
pmc_searcher = PMCSearcher()
core_searcher = CORESearcher()
europepmc_searcher = EuropePMCSearcher()
dblp_searcher = DBLPSearcher()
openaire_searcher = OpenAiresearcher()
unpaywall_resolver = UnpaywallResolver()

# Build searchers dict for tools subpackage
_searchers = {
    "arxiv": arxiv_searcher,
    "pubmed": pubmed_searcher,
    "medrxiv": medrxiv_searcher,
    "semantic": semantic_searcher,
    "crossref": crossref_searcher,
    "openalex": openalex_searcher,
    "pmc": pmc_searcher,
    "core": core_searcher,
    "europepmc": europepmc_searcher,
    "dblp": dblp_searcher,
    "openaire": openaire_searcher,
}

# ---------------------------------------------------------------------------
# Optional paid-platform connectors (disabled by default)
# ---------------------------------------------------------------------------
_ieee_api_key = get_env("IEEE_API_KEY", "")
_acm_api_key = get_env("ACM_API_KEY", "")

ieee_searcher = None
if _ieee_api_key:
    from .academic_platforms.ieee import IEEESearcher

    ieee_searcher = IEEESearcher()
    ALL_SOURCES.append("ieee")
    logger.info("IEEE Xplore enabled via configured environment key.")

acm_searcher = None
if _acm_api_key:
    from .academic_platforms.acm import ACMSearcher

    acm_searcher = ACMSearcher()
    ALL_SOURCES.append("acm")
    logger.info("ACM Digital Library enabled via configured environment key.")


# ---------------------------------------------------------------------------
# Register all MCP tools
# ---------------------------------------------------------------------------
def _dedupe_papers(papers):
    """Backward-compatible wrapper that injects *storage*."""
    from ._helpers import _dedupe_papers as _dedupe_papers_base

    return _dedupe_papers_base(papers, storage)


from .tools import register_all  # noqa: E402

register_all(
    mcp,
    storage=storage,
    searchers=_searchers,
    unpaywall_resolver=unpaywall_resolver,
    default_save_path=DEFAULT_SAVE_PATH,
    default_cache_dir=DEFAULT_CACHE_DIR,
    ieee_searcher=ieee_searcher,
    acm_searcher=acm_searcher,
)

# Re-export tool functions for backward compatibility (tests access server.*)
from .tools.download import (  # noqa: E402, F401
    _download_from_url,
    _try_repository_fallback,
    download_paper,
)
from .tools.manuscript import (  # noqa: E402, F401
    _PACKAGED_TEMPLATES_DIR,
    _get_user_templates_dir,
    _list_writing_templates,
    get_writing_template,
)

# Backward compat: tests access server._USER_TEMPLATES_DIR
_USER_TEMPLATES_DIR = _get_user_templates_dir()


def main():
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
