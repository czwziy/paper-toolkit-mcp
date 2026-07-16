"""Citation verification via multi-model LLM scoring.

Loads model configurations from a JSON file, calls each configured LLM
in parallel to score the match between a citing sentence and the referenced
paper's title+abstract, and caches results in ``papers.db`` via
``PaperStorage``.

This module is a leaf-layer dependency — it does not import from any
upper layer (tools, server). ``PaperStorage`` and ``config`` instances
are injected by the caller.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import re
from dataclasses import dataclass, field
from typing import Any

import httpx

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Default prompt template
# ---------------------------------------------------------------------------

DEFAULT_PROMPT_TEMPLATE = """\
你是一个学术论文引用审核专家。请评估以下论文语句与所引用文献的吻合程度。

【论文语句】
{sentence}

【引用文献】
标题：{title}
摘要：{abstract}

评分标准：
5 - 语句内容与文献高度吻合，引用完全合理
4 - 语句内容与文献基本吻合，引用合理
3 - 语句内容与文献部分相关，引用尚可但有偏差
2 - 语句内容与文献关联较弱，引用可能不当
1 - 语句内容与文献完全不匹配，疑似幻觉引用

请以JSON格式回复：{{"score": <1-5>, "reason": "<简短理由>"}}
"""

DEFAULT_SCORE_RANGE = (1, 5)

# ---------------------------------------------------------------------------
# Configuration data classes
# ---------------------------------------------------------------------------


@dataclass
class ModelConfig:
    """Configuration for a single LLM scorer."""

    name: str
    provider: str  # "openai" | "anthropic" | "openai_compatible"
    api_key_env: str
    base_url: str
    model: str
    timeout: int = 30  # seconds


@dataclass
class VerifierConfig:
    """Full verifier configuration loaded from JSON."""

    models: list[ModelConfig] = field(default_factory=list)
    prompt_template: str = DEFAULT_PROMPT_TEMPLATE
    score_range: tuple[int, int] = DEFAULT_SCORE_RANGE
    max_concurrency: int = 5


# ---------------------------------------------------------------------------
# Configuration loading
# ---------------------------------------------------------------------------

_CONFIG_DIR_NAME = ".harness"
_CONFIG_FILE_NAME = "verifier_models.json"


def _default_config_path(work_dir: str | None = None) -> str:
    """Resolve the default config file path.

    Looks for ``.harness/verifier_models.json`` inside the project directory.
    The ``.harness/`` directory is created by ``harness_init``, so the
    verifier config naturally lives alongside other harness files.
    """
    if work_dir is None:
        from .config import get_work_dir

        work_dir = get_work_dir()
    return os.path.join(work_dir, _CONFIG_DIR_NAME, _CONFIG_FILE_NAME)


def load_verifier_config(config_path: str | None = None) -> VerifierConfig:
    """Load verifier configuration from a JSON file.

    If the file does not exist, returns an empty config (no models configured).
    """
    path = config_path or _default_config_path()
    if not os.path.isfile(path):
        logger.debug("Verifier config not found at %s — no models configured.", path)
        return VerifierConfig()

    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning("Failed to load verifier config from %s: %s", path, exc)
        return VerifierConfig()

    models = []
    for item in data.get("models", []):
        try:
            models.append(ModelConfig(
                name=item["name"],
                provider=item.get("provider", "openai_compatible"),
                api_key_env=item["api_key_env"],
                base_url=item.get("base_url", "https://api.openai.com/v1"),
                model=item["model"],
                timeout=item.get("timeout", 30),
            ))
        except KeyError as exc:
            logger.warning("Skipping model entry with missing field: %s", exc)

    score_range = tuple(data.get("score_range", list(DEFAULT_SCORE_RANGE)))
    if len(score_range) != 2:
        score_range = DEFAULT_SCORE_RANGE

    return VerifierConfig(
        models=models,
        prompt_template=data.get("prompt_template", DEFAULT_PROMPT_TEMPLATE),
        score_range=score_range,  # type: ignore[arg-type]
        max_concurrency=data.get("max_concurrency", 5),
    )


def write_default_config(config_path: str | None = None) -> str:
    """Write a template verifier config file if one does not exist.

    Returns the path to the config file.
    """
    path = config_path or _default_config_path()
    if os.path.isfile(path):
        return path

    os.makedirs(os.path.dirname(path), exist_ok=True)
    template = {
        "models": [
            {
                "name": "example-model",
                "provider": "openai_compatible",
                "api_key_env": "YOUR_API_KEY_ENV_VAR",
                "base_url": "https://api.openai.com/v1",
                "model": "gpt-4o",
                "timeout": 30,
            },
        ],
        "prompt_template": DEFAULT_PROMPT_TEMPLATE,
        "score_range": [1, 5],
        "max_concurrency": 5,
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(template, f, indent=2, ensure_ascii=False)
    logger.info("Created default verifier config at %s", path)
    return path


# ---------------------------------------------------------------------------
# LLM API callers
# ---------------------------------------------------------------------------

_JSON_BLOCK_RE = re.compile(r"\{[^{}]*\}", re.DOTALL)


def _parse_score_response(text: str, score_range: tuple[int, int]) -> dict[str, Any]:
    """Extract score and reason from LLM response text.

    Tries to parse JSON; falls back to regex extraction of a numeric score.
    """
    # Try direct JSON parse
    try:
        obj = json.loads(text.strip())
        if isinstance(obj, dict) and "score" in obj:
            score = int(obj["score"])
            if score_range[0] <= score <= score_range[1]:
                return {"score": score, "reason": obj.get("reason", "")}
    except (json.JSONDecodeError, ValueError, TypeError):
        pass

    # Try extracting JSON block from markdown code fence or surrounding text
    for match in _JSON_BLOCK_RE.finditer(text):
        try:
            obj = json.loads(match.group())
            if isinstance(obj, dict) and "score" in obj:
                score = int(obj["score"])
                if score_range[0] <= score <= score_range[1]:
                    return {"score": score, "reason": obj.get("reason", "")}
        except (json.JSONDecodeError, ValueError, TypeError):
            continue

    # Fallback: find first integer in score range
    for match in re.finditer(r"\b(\d)\b", text):
        num = int(match.group(1))
        if score_range[0] <= num <= score_range[1]:
            return {"score": num, "reason": text.strip()[:200]}

    return {"score": 0, "reason": f"Failed to parse score from response: {text[:200]}"}


async def _call_openai_compatible(
    client: httpx.AsyncClient,
    model_cfg: ModelConfig,
    prompt: str,
    api_key: str,
) -> str:
    """Call an OpenAI-compatible chat completion API."""
    url = f"{model_cfg.base_url.rstrip('/')}/chat/completions"
    payload = {
        "model": model_cfg.model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.1,
        "max_tokens": 256,
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    resp = await client.post(url, json=payload, headers=headers, timeout=model_cfg.timeout)
    resp.raise_for_status()
    data = resp.json()
    content = data["choices"][0]["message"]["content"]
    return content


async def _call_anthropic(
    client: httpx.AsyncClient,
    model_cfg: ModelConfig,
    prompt: str,
    api_key: str,
) -> str:
    """Call the Anthropic messages API."""
    url = f"{model_cfg.base_url.rstrip('/')}/messages"
    payload = {
        "model": model_cfg.model,
        "max_tokens": 256,
        "messages": [{"role": "user", "content": prompt}],
    }
    headers = {
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
        "Content-Type": "application/json",
    }
    resp = await client.post(url, json=payload, headers=headers, timeout=model_cfg.timeout)
    resp.raise_for_status()
    data = resp.json()
    content = data["content"][0]["text"]
    return content


async def _call_model(
    client: httpx.AsyncClient,
    model_cfg: ModelConfig,
    prompt: str,
    api_key: str,
    score_range: tuple[int, int],
) -> dict[str, Any]:
    """Call a single model and return parsed score dict."""
    try:
        if model_cfg.provider == "anthropic":
            raw = await _call_anthropic(client, model_cfg, prompt, api_key)
        else:
            raw = await _call_openai_compatible(client, model_cfg, prompt, api_key)
        result = _parse_score_response(raw, score_range)
        result["model_name"] = model_cfg.name
        result["raw_response"] = raw[:500]
        return result
    except Exception as exc:
        logger.warning("Model %s call failed: %s", model_cfg.name, exc)
        return {
            "model_name": model_cfg.name,
            "score": 0,
            "reason": f"API call failed: {exc}",
            "raw_response": "",
        }


# ---------------------------------------------------------------------------
# Core verification logic
# ---------------------------------------------------------------------------


def _resolve_api_key(api_key_env: str) -> str:
    """Resolve an API key from environment variable name."""
    from .config import get_env

    key = get_env(api_key_env, "")
    if not key:
        # Also try without prefix
        key = os.environ.get(api_key_env, "")
    return key


async def verify_single(
    sentence: str,
    cite_key: str,
    paper_title: str,
    paper_abstract: str,
    config: VerifierConfig,
    storage: Any,  # PaperStorage, typed as Any to avoid import
    force_refresh: bool = False,
) -> dict[str, Any]:
    """Verify a single citation by scoring with all configured models.

    Args:
        sentence: The citing sentence from the manuscript.
        cite_key: The cite_key of the referenced paper.
        paper_title: Title of the referenced paper.
        paper_abstract: Abstract of the referenced paper.
        config: Verifier configuration with model list.
        storage: PaperStorage instance for caching.
        force_refresh: If True, ignore cached scores and re-verify.

    Returns:
        Dict with scores per model, average, and verdict.
    """
    if not config.models:
        return {
            "cite_key": cite_key,
            "sentence": sentence,
            "error": "No models configured. Create verifier_models.json first.",
        }

    # Check cache
    if not force_refresh:
        cached = storage.get_cached_scores(cite_key, sentence)
        if cached and len(cached) >= len(config.models):
            # All models have cached scores
            cached_scores = {r["model_name"]: r["score"] for r in cached}
            cached_details = {r["model_name"]: r for r in cached}
            avg = sum(cached_scores.values()) / len(cached_scores) if cached_scores else 0
            return {
                "cite_key": cite_key,
                "sentence": sentence,
                "scores": cached_scores,
                "avg_score": round(avg, 2),
                "verdict": _verdict(avg, config.score_range),
                "details": cached_details,
                "from_cache": True,
            }

    # Delete stale cache if force_refresh
    if force_refresh:
        storage.delete_scores(cite_key, sentence)

    # Build prompt
    prompt = config.prompt_template.format(
        sentence=sentence,
        title=paper_title,
        abstract=paper_abstract,
    )

    # Call models in parallel with concurrency limit
    semaphore = asyncio.Semaphore(config.max_concurrency)
    results: list[dict[str, Any]] = []

    async def _limited_call(model_cfg: ModelConfig) -> dict[str, Any]:
        api_key = _resolve_api_key(model_cfg.api_key_env)
        if not api_key:
            return {
                "model_name": model_cfg.name,
                "score": 0,
                "reason": f"API key not found: env var {model_cfg.api_key_env} is empty",
                "raw_response": "",
            }
        async with semaphore:
            async with httpx.AsyncClient() as client:
                return await _call_model(client, model_cfg, prompt, api_key, config.score_range)

    tasks = [_limited_call(m) for m in config.models]
    results = await asyncio.gather(*tasks, return_exceptions=False)

    # Cache results and build response
    scores: dict[str, int] = {}
    details: dict[str, dict[str, Any]] = {}
    for r in results:
        name = r.get("model_name", "unknown")
        score = r.get("score", 0)
        scores[name] = score
        details[name] = r
        # Cache non-zero scores
        if score > 0:
            storage.upsert_score(
                cite_key=cite_key,
                sentence=sentence,
                model_name=name,
                score=score,
                rationale=r.get("reason", ""),
            )

    avg = sum(scores.values()) / len(scores) if scores else 0
    return {
        "cite_key": cite_key,
        "sentence": sentence,
        "scores": scores,
        "avg_score": round(avg, 2),
        "verdict": _verdict(avg, config.score_range),
        "details": details,
        "from_cache": False,
    }


def _verdict(avg_score: float, score_range: tuple[int, int]) -> str:
    """Determine verdict from average score."""
    lo, hi = score_range
    mid = (lo + hi) / 2
    threshold_low = mid - (hi - lo) / 4
    if avg_score >= mid:
        return "match"
    elif avg_score >= threshold_low:
        return "partial"
    else:
        return "mismatch"


# ---------------------------------------------------------------------------
# Manuscript-level verification
# ---------------------------------------------------------------------------

_CITE_KEY_RE = re.compile(r"\[@([a-zA-Z0-9]+)\]")


def extract_citation_sentences(text: str) -> list[dict[str, str]]:
    """Extract (sentence, cite_key) pairs from manuscript text.

    For each [@cite_key] occurrence, captures the surrounding sentence
    (text from the previous sentence-ending punctuation to the next).
    """
    results: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()

    for match in _CITE_KEY_RE.finditer(text):
        cite_key = match.group(1)
        start = match.start()

        # Look backward for sentence start (., !, ?, newline, or BOF)
        sent_start = 0
        for i in range(start - 1, -1, -1):
            if text[i] in ".!?\n":
                sent_start = i + 1
                break

        # Look forward for sentence end
        sent_end = len(text)
        for i in range(match.end(), len(text)):
            if text[i] in ".!?\n":
                sent_end = i + 1
                break

        sentence = text[sent_start:sent_end].strip()
        if not sentence:
            continue

        pair = (sentence, cite_key)
        if pair not in seen:
            seen.add(pair)
            results.append({"sentence": sentence, "cite_key": cite_key})

    return results


async def verify_manuscript(
    manuscript_path: str,
    config: VerifierConfig,
    storage: Any,
    force_refresh: bool = False,
) -> dict[str, Any]:
    """Verify all citations in a manuscript file.

    Args:
        manuscript_path: Path to the manuscript Markdown file.
        config: Verifier configuration.
        storage: PaperStorage instance.
        force_refresh: If True, re-verify all citations.

    Returns:
        Dict with total/verified/cached counts and per-citation results.
    """
    if not os.path.isfile(manuscript_path):
        return {"error": f"File not found: {manuscript_path}"}

    with open(manuscript_path, encoding="utf-8") as f:
        content = f.read()

    pairs = extract_citation_sentences(content)
    if not pairs:
        return {
            "status": "no_citations_found",
            "message": "No [@cite_key] references found in the manuscript.",
        }

    if not config.models:
        return {
            "error": "No models configured. Create verifier_models.json first.",
        }

    results: list[dict[str, Any]] = []
    cached_count = 0
    failed_keys: list[str] = []

    for pair in pairs:
        cite_key = pair["cite_key"]
        sentence = pair["sentence"]

        # Look up paper in storage
        row = storage.get_by_cite_key(cite_key)
        if row is None:
            failed_keys.append(cite_key)
            results.append({
                "cite_key": cite_key,
                "sentence": sentence,
                "error": f"Paper not found in local library: {cite_key}",
            })
            continue

        title = row.get("title", "")
        abstract = row.get("abstract", "")

        result = await verify_single(
            sentence=sentence,
            cite_key=cite_key,
            paper_title=title,
            paper_abstract=abstract,
            config=config,
            storage=storage,
            force_refresh=force_refresh,
        )
        if result.get("from_cache"):
            cached_count += 1
        results.append(result)

    # Summary
    mismatch_count = sum(1 for r in results if r.get("verdict") == "mismatch")
    partial_count = sum(1 for r in results if r.get("verdict") == "partial")
    match_count = sum(1 for r in results if r.get("verdict") == "match")

    return {
        "status": "completed",
        "total": len(pairs),
        "verified": len(results),
        "cached": cached_count,
        "match": match_count,
        "partial": partial_count,
        "mismatch": mismatch_count,
        "unresolved_keys": failed_keys if failed_keys else None,
        "results": results,
    }


# ---------------------------------------------------------------------------
# Config validation
# ---------------------------------------------------------------------------


async def validate_config(config: VerifierConfig) -> dict[str, Any]:
    """Test connectivity for each configured model.

    Returns a dict with per-model status (ok / error).
    """
    if not config.models:
        return {
            "status": "no_models",
            "message": "No models configured. Create verifier_models.json with at least 2 models.",
        }

    model_statuses: list[dict[str, Any]] = []

    for model_cfg in config.models:
        api_key = _resolve_api_key(model_cfg.api_key_env)
        if not api_key:
            model_statuses.append({
                "name": model_cfg.name,
                "provider": model_cfg.provider,
                "status": "error",
                "error": f"API key env var '{model_cfg.api_key_env}' is empty",
            })
            continue

        # Send a minimal request to test connectivity
        try:
            async with httpx.AsyncClient() as client:
                if model_cfg.provider == "anthropic":
                    url = f"{model_cfg.base_url.rstrip('/')}/messages"
                    payload = {
                        "model": model_cfg.model,
                        "max_tokens": 10,
                        "messages": [{"role": "user", "content": "Hi"}],
                    }
                    headers = {
                        "x-api-key": api_key,
                        "anthropic-version": "2023-06-01",
                        "Content-Type": "application/json",
                    }
                else:
                    url = f"{model_cfg.base_url.rstrip('/')}/chat/completions"
                    payload = {
                        "model": model_cfg.model,
                        "messages": [{"role": "user", "content": "Hi"}],
                        "max_tokens": 10,
                    }
                    headers = {
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json",
                    }
                resp = await client.post(url, json=payload, headers=headers, timeout=model_cfg.timeout)
                resp.raise_for_status()
                model_statuses.append({
                    "name": model_cfg.name,
                    "provider": model_cfg.provider,
                    "status": "ok",
                })
        except Exception as exc:
            model_statuses.append({
                "name": model_cfg.name,
                "provider": model_cfg.provider,
                "status": "error",
                "error": str(exc)[:200],
            })

    ok_count = sum(1 for s in model_statuses if s["status"] == "ok")
    return {
        "status": "ok" if ok_count >= 2 else "insufficient",
        "models_ok": ok_count,
        "models_total": len(config.models),
        "message": (
            f"{ok_count}/{len(config.models)} models reachable."
            if ok_count >= 2
            else f"Only {ok_count}/{len(config.models)} models reachable. At least 2 recommended."
        ),
        "details": model_statuses,
    }
