# paper_toolkit_mcp/tools/verify.py
"""Citation verification MCP tools — multi-model LLM scoring for citation accuracy."""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ..storage import PaperStorage

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Module-level state — set by register()
# ---------------------------------------------------------------------------
_storage: PaperStorage | None = None


# ---------------------------------------------------------------------------
# MCP tools
# ---------------------------------------------------------------------------

async def verify_citation(
    sentence: str,
    cite_key: str,
    force_refresh: bool = False,
) -> dict[str, Any]:
    """Verify a single citation by scoring the match between a sentence and its referenced paper.

    Uses multiple LLM models (configured in verifier_models.json) to
    independently score how well the citing sentence matches the referenced
    paper's title and abstract. Scores range from 1 (mismatch / hallucination)
    to 5 (perfect match). Results are cached in the local database for
    incremental updates.

    Args:
        sentence: The citing sentence from the manuscript.
        cite_key: The cite_key of the referenced paper (e.g., "Kxq").
        force_refresh: If True, ignore cached scores and re-verify with all models.

    Returns:
        Dict with per-model scores, average score, verdict (match/partial/mismatch),
        and detailed reasoning from each model.
    """
    from ..verifier import load_verifier_config, verify_single

    assert _storage is not None, "register() not called"

    # Look up paper in local library
    row = _storage.get_by_cite_key(cite_key)
    if row is None:
        return {
            "cite_key": cite_key,
            "sentence": sentence,
            "error": f"Paper not found in local library: {cite_key}. "
                     "Search and download the paper first.",
        }

    title = row.get("title", "")
    abstract = row.get("abstract", "")
    if not abstract:
        return {
            "cite_key": cite_key,
            "sentence": sentence,
            "error": f"Paper {cite_key} has no abstract — cannot verify.",
        }

    config = load_verifier_config()
    result = await verify_single(
        sentence=sentence,
        cite_key=cite_key,
        paper_title=title,
        paper_abstract=abstract,
        config=config,
        storage=_storage,
        force_refresh=force_refresh,
    )
    return result


async def verify_manuscript(
    manuscript_path: str,
    force_refresh: bool = False,
) -> dict[str, Any]:
    """Verify all citations in a manuscript by multi-model LLM scoring.

    Scans the manuscript for [@cite_key] references, extracts the citing
    sentence for each, and scores the match between each sentence and its
    referenced paper using all configured LLM models. Results are cached
    incrementally — only new or force-refreshed citations are re-verified.

    Args:
        manuscript_path: Path to the manuscript Markdown file containing
            [@cite_key] citations (e.g., [@Kxq], [@JHw]).
        force_refresh: If True, re-verify all citations (ignore cache).

    Returns:
        Dict with total/verified/cached counts, match/partial/mismatch
        breakdown, and per-citation detailed results.
    """
    from ..verifier import load_verifier_config
    from ..verifier import verify_manuscript as _verify_manuscript

    assert _storage is not None, "register() not called"

    config = load_verifier_config()
    result = await _verify_manuscript(
        manuscript_path=manuscript_path,
        config=config,
        storage=_storage,
        force_refresh=force_refresh,
    )
    return result


async def verify_config() -> dict[str, Any]:
    """Check the citation verifier configuration and test model connectivity.

    Validates that the ``.harness/verifier_models.json`` config file exists,
    has at least 2 models configured, and tests API connectivity for each model.

    Returns:
        Dict with configuration status, per-model connectivity results,
        and recommendations.
    """
    from ..verifier import _default_config_path, load_verifier_config, validate_config, write_default_config

    config = load_verifier_config()

    if not config.models:
        # Auto-create default config template
        path = write_default_config()
        return {
            "status": "no_models",
            "message": (
                "No models configured. A template config has been created at: "
                f"{path} — edit it with your model API keys and rerun. "
                "Alternatively, run harness_init to set up the full .harness/ directory."
            ),
            "config_path": path,
        }

    result = await validate_config(config)
    result["config_path"] = _default_config_path()
    return result


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

def register(mcp, *, storage) -> None:
    """Register citation verification tools on the MCP server."""
    global _storage
    _storage = storage

    mcp.tool()(verify_citation)
    mcp.tool()(verify_manuscript)
    mcp.tool()(verify_config)
