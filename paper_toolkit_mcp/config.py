from __future__ import annotations

import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)

_ENV_LOADED = False
ENV_PREFIX = "paper_toolkit_mcp_"


def _work_dir_from_env() -> str:
    """Read WORK_DIR directly from os.environ without triggering env loading.

    Used by _candidate_env_files() so that .env discovery can honor WORK_DIR
    without recursing into load_env_file(). WORK_DIR must therefore be set as a
    real environment variable (e.g. in the MCP server config's env block).
    """
    value = os.getenv(f"{ENV_PREFIX}WORK_DIR", "").strip()
    if not value:
        value = os.getenv("WORK_DIR", "").strip()
    return value


def _candidate_env_files() -> list[Path]:
    explicit_path = os.getenv(f"{ENV_PREFIX}ENV_FILE", "").strip()
    if explicit_path:
        return [Path(explicit_path).expanduser()]

    candidates: list[Path] = []

    work_dir = _work_dir_from_env()
    if work_dir:
        candidates.append(Path(work_dir).expanduser() / ".env")

    cwd_env = Path.cwd() / ".env"
    project_env = Path(__file__).resolve().parent.parent / ".env"
    candidates.append(cwd_env)
    if project_env != cwd_env:
        candidates.append(project_env)

    # Dedupe while preserving order
    seen: set[Path] = set()
    unique: list[Path] = []
    for cand in candidates:
        if cand not in seen:
            seen.add(cand)
            unique.append(cand)
    return unique


def _strip_quotes(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
        return value[1:-1]
    return value


def _load_env_from_file(env_file: Path) -> None:
    for raw_line in env_file.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue

        if line.startswith("export "):
            line = line[7:].strip()

        if "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        if not key:
            continue

        value = _strip_quotes(value.strip())
        os.environ.setdefault(key, value)


def load_env_file(force: bool = False) -> None:
    global _ENV_LOADED

    if _ENV_LOADED and not force:
        return

    for env_file in _candidate_env_files():
        if not env_file.exists() or not env_file.is_file():
            continue

        try:
            _load_env_from_file(env_file)
            logger.debug("Loaded environment values from %s", env_file)
            break
        except Exception as exc:
            logger.warning("Failed to load environment file %s: %s", env_file, exc)

    _ENV_LOADED = True


def get_env(name: str, default: str | None = "") -> str:
    load_env_file()

    normalized = name.strip()
    if not normalized:
        return "" if default is None else str(default)

    keys = [f"{ENV_PREFIX}{normalized}", normalized]
    for key in keys:
        if key in os.environ:
            return os.environ.get(key, "")

    return "" if default is None else str(default)


def get_work_dir() -> str:
    """Return the unified working directory for all outputs.

    Resolved from the ``paper_toolkit_mcp_WORK_DIR`` (or legacy ``WORK_DIR``)
    environment variable, falling back to the current working directory when
    unset. All download paths, the search cache, and the default ``.env``
    lookup are derived from this directory so that files stay inside the user's
    project folder regardless of where the MCP server process is launched.

    Note: for ``.env`` discovery to honor WORK_DIR, WORK_DIR must be set as a
    real environment variable (e.g. via the MCP server config's ``env`` block),
    not only inside a ``.env`` file.
    """
    load_env_file()
    value = _work_dir_from_env()
    return value if value else os.getcwd()
