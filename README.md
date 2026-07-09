**English** | [中文](README_zh.md)

﻿# Scholar Toolkit MCP

> **Fork Notice**: This is a fork of [openags/paper-toolkit-mcp](https://github.com/openags/paper-toolkit-mcp),
> originally created by [P.S Zhang](https://github.com/openags). This fork extends the project with manuscript
> processing, search caching, and citation export features. Both versions are licensed under MIT.

A comprehensive MCP toolkit for paper searching, manuscript processing, and academic research workflows. The project follows a free-first strategy: prioritize open and public data sources, support optional API keys when they improve stability or coverage, and keep source-specific connectors extensible for advanced users.

**New Features (v0.2.0)**: Manuscript processing with citation placeholders, search caching, BibTeX/RIS export, and one-click Word document generation.

![PyPI](https://img.shields.io/pypi/v/paper-toolkit-mcp.svg) ![License](https://img.shields.io/badge/license-MIT-blue.svg) ![Python](https://img.shields.io/badge/python-3.10+-blue.svg)

---

## Manuscript Processing (New)

### Workflow

1. **Write** your paper in Markdown with citation placeholders
2. **Process** with `paper-toolkit manuscript` command
3. **Import** `refs.ris` to Zotero (optional)
4. **Submit** the generated `draft_final.docx`

### Supported Placeholders

```markdown
[@doi:10.1038/s41591-020-0001-2]
[@pmid:32145678]
[@arxiv:2106.12345]
[@title:Attention Is All You Need]
```

### Usage

```bash
# Basic usage (generates formatted markdown + BibTeX + RIS)
paper-toolkit manuscript draft.md

# With Word document generation (requires pandoc)
paper-toolkit manuscript draft.md --docx

# Specify citation style
paper-toolkit manuscript draft.md -s apa
paper-toolkit manuscript draft.md -s ieee
paper-toolkit manuscript draft.md -s gb7714

# Custom output directory
paper-toolkit manuscript draft.md -o ./output

# Disable specific outputs
paper-toolkit manuscript draft.md --no-bib --no-ris
```

### Citation Styles

| Style | Code | Description |
|-------|------|-------------|
| GB/T 7714-2015 | `gb7714` | Chinese national standard (numeric) |
| APA 7th | `apa` | American Psychological Association |
| IEEE | `ieee` | Institute of Electrical and Electronics Engineers |
| Vancouver | `vancouver` | International Committee of Medical Journal Editors |
| Harvard | `harvard` | Author-date format |

### Output Files

After processing, you get:
- `draft_formatted.md` - Markdown with numbered citations [1], [2], ...
- `draft_final.docx` - Word document (if `--docx` used and pandoc installed)
- `refs.bib` - BibTeX file (can be imported to Zotero/JabRef)
- `refs.ris` - RIS file (Zotero/EndNote/Mendeley compatible)
- `draft_references.txt` - Plain text reference list

---

## Search Caching (New)

### How It Works

- Search results are cached as JSON files in `.paper_cache/`
- Cache location follows your **WORK_DIR** (defaults to the current working directory)
- Follows your project folder — copy the folder, cache moves with it
- TTL (time-to-live) is 24 hours by default

### Cache Location

```
your_project/
├── draft.md
├── refs.bib
└── .paper_cache/          ← Cache is here
    ├── abc123.json        ← Cached search results
    └── def456.json
```

### Manage Cache

```bash
# List cached items
paper-toolkit cache list

# Clear all cache
paper-toolkit cache clear
```

Or via MCP tools: `cache_list()`, `cache_clear()`

---

## CLI Usage

```bash
# Search papers
paper-toolkit search "machine learning" -s arxiv,semantic -n 10

# Download PDF
paper-toolkit download arxiv 2106.12345

# Read paper (extract text)
paper-toolkit read arxiv 2106.12345

# Get paper metadata
paper-toolkit search "attention is all you need" -s crossref -n 1

# Process manuscript
paper-toolkit manuscript draft.md -s gb7714 --docx

# Cache management
paper-toolkit cache list
paper-toolkit cache clear

# List available sources
paper-toolkit sources
```

---

## Table of Contents

- [Overview](#overview)
- [New Features](#new-features-v020)
- [Project Principles](#project-principles)
- [Features](#features)
- [Source Strategy](#source-strategy)
- [Sci-Hub Notice](#sci-hub-notice)
- [Installation](#installation)
  - [Install from PyPI (pip)](#install-from-pypi-pip)
  - [Install from Source (Development)](#install-from-source-development)
  - [Environment Variables](#environment-variables-env-file)
- [Manuscript Processing](#manuscript-processing-new)
- [Search Caching](#search-caching-new)
- [CLI Usage](#cli-usage)
- [Contributing](#contributing)
- [Star History](#star-history)
- [License](#license)
- [TODO](#todo)

---

## New Features (v0.2.0)

### Manuscript Processing

Write your paper in Markdown with citation placeholders, then generate a formatted Word document with references automatically:

```markdown
# Introduction
Deep learning has made significant progress in medical imaging[@doi:10.1038/s41591-020-0001-2].
Transformer architecture revolutionized NLP[@title:Attention Is All You Need].
```

Process it:
```bash
paper-toolkit manuscript draft.md -s gb7714 --docx
```

Output:
- `draft_formatted.md` - Text with numbered citations [1], [2], ...
- `refs.bib` - BibTeX file (for Zotero/EndNote import)
- `refs.ris` - RIS file (Zotero compatible)
- `draft_final.docx` - Word document with formatted references

Supported placeholders: `[@doi:...]`, `[@pmid:...]`, `[@arxiv:...]`, `[@title:...]`

Supported citation styles: GB/T 7714-2015, APA 7th, IEEE, Vancouver, Harvard

### Search Caching

Search results are automatically cached in `.paper_cache/` (under your WORK_DIR, defaults to CWD):
- **Follows your workspace**: Cache is saved in the folder you're working in
- **Portable**: Copy your project folder and cache moves with it
- **Easy management**: Users can manually delete `.paper_cache/` to clear

### MCP Tools Added
- `process_manuscript` - Process manuscript with citations
- `get_paper_metadata` - Get paper metadata by identifier
- `export_references` - Export references in BibTeX/RIS/text format
- `cache_list` / `cache_clear` - Manage search cache

---

## Overview

`paper-toolkit-mcp` is a Python-based tool for searching and downloading academic papers from various platforms. It provides tools for searching papers, downloading PDFs, and extracting text, making it ideal for researchers and AI-driven workflows. It can be used as an MCP server (for Claude Desktop and other MCP clients) or as a Claude Code skill with a CLI interface.

## Project Principles

- **Free-First**: Public and open sources are the default roadmap. Paid or restricted sources are not the core direction of this project.
- **Optional API Keys**: API keys are supported only when they improve stability, rate limits, or metadata quality. The MCP should still be usable without them whenever possible.
- **LLM-Friendly Retrieval**: Search results should be standardized, deduplicated, and as complete as possible for downstream LLM workflows.
- **Source Transparency**: Different sources have different strengths. The MCP should make those tradeoffs explicit instead of pretending every source supports full-text retrieval.

---

## Features

- **Two-Layer Architecture**:
  - **Layer 1 (Unified Tooling)**: High-level `search_papers` for multi-source concurrent search & deduplication, and `download_with_fallback` relying on publisher open access links with sequential fallbacks.
  - **Layer 2 (Platform Connectors)**: Modular connectors for specific academic platforms (arXiv, PubMed, bioRxiv, Semantic Scholar, etc.) equipped with intelligent DOI extraction via regex text analysis or API fields.
- **Multi-Source Support**: Search and download papers from arXiv, PubMed, bioRxiv, medRxiv, Google Scholar, IACR ePrint Archive, Semantic Scholar, Crossref, OpenAlex, PubMed Central (PMC), CORE, Europe PMC, dblp, OpenAIRE, CiteSeerX, DOAJ, BASE, Zenodo, HAL, SSRN, Unpaywall (DOI lookup), and optional Sci-Hub workflows.
- **Standardized Output**: Papers are returned in a consistent dictionary format via the `Paper` class.
- **Free-First Design**: Open and public sources are prioritized before any optional commercial or restricted integrations.
- **Optional API-Key Enhancement**: Sources like Semantic Scholar can work better with a user-provided API key, but are not intended to force paid usage.
- **Discovery + Retrieval Workflow**: Google Scholar and Crossref can be used for discovery and DOI backfilling, while open repositories and publisher links are used for lawful full-text resolution where available.
- **OA-First Fallback Chain**: `download_with_fallback` now follows source-native download → OpenAIRE/CORE/Europe PMC/PMC discovery → Unpaywall DOI resolution → optional Sci-Hub.
- **MCP Integration**: Compatible with MCP clients for LLM context enhancement.
- **Extensible Design**: Easily add new academic platforms by extending the `academic_platforms` module.

## Source Strategy

The long-term goal is not to depend on a single search engine, but to combine multiple free and public sources with clear roles:

- **Open metadata backbone**: Crossref, OpenAlex, Semantic Scholar, dblp, CiteSeerX, SSRN, Unpaywall (DOI-centric OA metadata).
- **Discipline-specific sources**: arXiv, PubMed, PubMed Central, Europe PMC, IACR.
- **Open-access full-text sources**: arXiv, PMC, CORE, OpenAIRE, DOAJ, BASE, Zenodo, HAL, publisher open-access links.
- **Discovery and DOI recovery**: Google Scholar can be useful for finding titles, versions, and DOI clues when other public metadata sources are incomplete.

Recommended free-first roadmap:

1. Keep current public sources stable.
2. Add OpenAlex as a broad free metadata source.
3. Add PubMed Central and Europe PMC for stronger biomedical full-text access.
4. Add CORE and OpenAIRE for repository-based open-access retrieval.
5. Use Google Scholar mainly as a discovery fallback, not as the primary canonical source.

## Platform Capability Matrix

This matrix reflects **verified live-integration results** from functional and end-to-end regression tests in this repository. Columns show the highest capability level observed under normal conditions.

| Platform | Search | Download | Read | Notes |
|---|---|---|---|---|
| arXiv | ✅ | ✅ | ✅ | Open API; reliable |
| PubMed | ✅ | ❌ | ⚠️ info-only | Open API; reliable |
| bioRxiv | ✅ | ✅ | ✅ | Open API; reliable |
| medRxiv | ✅ | ✅ | ✅ | Open API; reliable |
| Google Scholar | ⚠️ | ❌ | ❌ | Bot-detection active; set `paper_toolkit_mcp_GOOGLE_SCHOLAR_PROXY_URL` |
| IACR | ✅ | ✅ | ✅ | Open API; reliable |
| Semantic Scholar | ✅ | ✅ (OA) | ✅ (OA) | Works without key (rate-limited); key improves limits; key rejection (403) retried automatically without key |
| Crossref | ✅ | ❌ | ⚠️ info-only | Open API; reliable |
| OpenAlex | ✅ | ❌ | ⚠️ info-only | Open API; reliable |
| PMC | ✅ | ✅ (OA only) | ✅ (OA only) | OA PDFs only; direct download may be blocked by some proxy environments |
| CORE | ✅ | ✅ (record-dependent) | ✅ (record-dependent) | Free key recommended; connector retries with backoff and falls back to key-less on 401/403 |
| Europe PMC | ✅ | ✅ (OA) | ✅ (OA) | OA PDFs only; direct download may be blocked by some proxy environments |
| dblp | ✅ | ❌ | ⚠️ info-only | Open API; reliable |
| OpenAIRE | ✅ | ❌ | ❌ | Open API; retries 3× with escalating request profiles on transient 403 |
| CiteSeerX | ⚠️ | ✅ (record-dependent) | ⚠️ | API endpoint intermittently unavailable / redirects to web archive |
| DOAJ | ✅ | ⚠️ (URL-dependent) | ⚠️ (URL-dependent) | PDF availability varies by article; free key raises rate limits |
| BASE | ⚠️ | ✅ (record-dependent) | ✅ (record-dependent) | OAI-PMH endpoint requires institutional IP registration; returns empty gracefully otherwise |
| Zenodo | ✅ | ✅ (record-dependent) | ✅ (record-dependent) | Open API; reliable |
| HAL | ✅ | ✅ (record-dependent) | ✅ (record-dependent) | Open API; reliable |
| SSRN | ⚠️ | ⚠️ best-effort | ⚠️ best-effort | 403 bot-detection active; public PDF only |
| Unpaywall | ✅ (DOI lookup) | ❌ | ❌ | **Requires** `paper_toolkit_mcp_UNPAYWALL_EMAIL` |
| Sci-Hub (optional) | ⚠️ fallback-only | ✅ | ❌ | Optional; unstable mirrors; user responsibility |
| **IEEE Xplore** 🔑 | 🚧 skeleton | 🚧 skeleton | 🚧 skeleton | Requires `paper_toolkit_mcp_IEEE_API_KEY` to activate |
| **ACM DL** 🔑 | 🚧 skeleton | 🚧 skeleton | 🚧 skeleton | Requires `paper_toolkit_mcp_ACM_API_KEY` to activate |

> ✅ = reliable in live tests.  ⚠️ = works but subject to upstream instability or access restrictions.  ❌ = not supported.  🔑 = key required.  🚧 = skeleton only.

---

## Credential & API Key Requirements

All keys are **optional** unless noted. Configure them in `.env` (preferred) or as shell exports.

| Environment Variable | Provider | Required? | How to obtain |
|---|---|---|---|
| `paper_toolkit_mcp_UNPAYWALL_EMAIL` | Unpaywall | **Yes** (Unpaywall disabled without it) | Any valid email; register at [unpaywall.org](https://unpaywall.org/products/api) |
| `paper_toolkit_mcp_CORE_API_KEY` | CORE | Recommended | Free at [core.ac.uk/services/api](https://core.ac.uk/services/api) |
| `paper_toolkit_mcp_SEMANTIC_SCHOLAR_API_KEY` | Semantic Scholar | Optional | Free at [semanticscholar.org](https://www.semanticscholar.org/product/api) — improves rate limits |
| `paper_toolkit_mcp_GOOGLE_SCHOLAR_PROXY_URL` | Google Scholar | Optional | Your HTTP/HTTPS proxy URL — bypasses bot-detection |
| `paper_toolkit_mcp_DOAJ_API_KEY` | DOAJ | Optional | Free at [doaj.org](https://doaj.org/apply-for-api-key/) — raises hourly rate limit |
| `paper_toolkit_mcp_ZENODO_ACCESS_TOKEN` | Zenodo | Optional | Free at [zenodo.org](https://zenodo.org/account/settings/applications/) — required for private records |
| `paper_toolkit_mcp_IEEE_API_KEY` | IEEE Xplore | **Required to activate** | Free at [developer.ieee.org](https://developer.ieee.org/) |
| `paper_toolkit_mcp_ACM_API_KEY` | ACM DL | **Required to activate** | See [libraries.acm.org/digital-library/acm-open](https://libraries.acm.org/digital-library/acm-open) |

All variables follow the `paper_toolkit_mcp_<NAME>` prefix scheme. Legacy names without the prefix (e.g. `CORE_API_KEY`, `UNPAYWALL_EMAIL`) are still supported for backward compatibility.

---

## Known Upstream Limitations

Some search failures are caused by external provider instability, not by bugs in this project:

| Source | Symptom | Cause | Workaround |
|---|---|---|---|
| Google Scholar | Returns 0 results / empty HTML | Bot-detection (CAPTCHA) | Set `paper_toolkit_mcp_GOOGLE_SCHOLAR_PROXY_URL` to a proxy |
| Semantic Scholar | 429 rate-limited responses | Anonymous access rate limit | Set `paper_toolkit_mcp_SEMANTIC_SCHOLAR_API_KEY`; if key is rejected (403) connector automatically retries without key |
| CORE | 500 / timeout errors | Unauthenticated rate limiting | Set `paper_toolkit_mcp_CORE_API_KEY` (free); connector retries with exponential backoff and falls back to key-less on 401/403 |
| OpenAIRE | Transient 403 responses | IP-based session rate limiting | Connector retries 3× per profile, escalating: plain session → XML Accept header → raw `requests.get` with Mozilla UA |
| CiteSeerX | 404 via web archive redirect | PSU endpoint intermittently redirects to archive | No workaround; connector returns empty gracefully |
| BASE | Search returns 0 results | OAI-PMH endpoint requires institutional IP registration | Register at [base-search.net](https://www.base-search.net/about/en/) for API access; connector returns empty gracefully otherwise |
| SSRN | HTTP 403 | Bot-detection (Cloudflare) | No workaround; connector tries two endpoints and returns a clear message on failure |
| PMC / Europe PMC | PDF download ProxyError | Local proxy blocking direct HTTPS PDF download | Disable proxy or use `download_with_fallback` instead |
| Unpaywall | Skipped entirely | `UNPAYWALL_EMAIL` env var not set | Set `paper_toolkit_mcp_UNPAYWALL_EMAIL` in `.env` |

## Optional Paid Platform Connectors (Phase 3)

IEEE Xplore and ACM Digital Library connectors are included as **opt-in skeletons**.
They are **disabled by default** — no API calls are made unless you explicitly configure the corresponding keys.

| Platform | Env Var | Status |
|---|---|---|
| IEEE Xplore | `paper_toolkit_mcp_IEEE_API_KEY` | 🚧 skeleton — search registered, download/read raise `NotImplementedError` |
| ACM Digital Library | `paper_toolkit_mcp_ACM_API_KEY` | 🚧 skeleton — search registered, download/read raise `NotImplementedError` |

**How to enable:**

```bash
export paper_toolkit_mcp_IEEE_API_KEY=<your_ieee_key>       # free key at https://developer.ieee.org/
export paper_toolkit_mcp_ACM_API_KEY=<your_acm_key>         # see https://libraries.acm.org/digital-library
```

Once a key is set, the corresponding source is automatically added to `ALL_SOURCES` and its MCP tools (`search_ieee` / `search_acm`, `download_ieee` / `download_acm`, `read_ieee_paper` / `read_acm_paper`) are registered at server startup.

Without a key the connectors log a startup warning only — the rest of the server is unaffected.

## Free Source Expansion (Phase 4)

Three additional free-source connectors are now integrated into the MCP server:

- `zenodo`: Official Zenodo REST API connector (search + record-dependent PDF/read support).
- `hal`: HAL public API connector (search + record-dependent PDF/read support).
- `ssrn`: Discovery-first connector with hardened parser and best-effort download/read when a direct public PDF link is available.
- `unpaywall`: DOI-centric OA metadata source for standalone lookup (`search_unpaywall`) and fallback URL resolution.

SSRN integration remains compliance-first: it only attempts direct public PDF links exposed by SSRN pages. If login/restricted delivery is required, the connector returns a clear message instead of bypassing access controls.

## Sci-Hub Notice

Sci-Hub support can remain available as an optional connector for users who explicitly choose to enable it, but it should not be treated as the default or recommended full-text path.

- Availability is unstable and mirrors change frequently.
- Legal and policy risks vary by jurisdiction.
- README and tool descriptions should clearly state that users are responsible for enabling and using it.
- Open-access and publisher-permitted sources should be tried first whenever possible.

---

## Installation

Choose the method that best fits your workflow. All methods support the same [optional API keys](#credential--api-key-requirements).

---

> **MCP Server Config file locations** (for methods below)
> - **macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`
> - **Windows**: `%APPDATA%\Claude\claude_desktop_config.json`
> - **Linux**: `~/.config/Claude/claude_desktop_config.json`

---

### Install from PyPI (pip)

The recommended way to install is from PyPI:

```bash
pip install paper-toolkit-mcp
```

Verify it works:

```bash
paper-toolkit search "machine learning" -s arxiv,semantic
```

**Claude Desktop / Trae IDE config:**

```json
{
  "mcpServers": {
    "paper-toolkit-mcp": {
      "command": "python",
      "args": ["-m", "paper_toolkit_mcp.server"],
      "env": {
        "paper_toolkit_mcp_UNPAYWALL_EMAIL": "your@email.com",
        "paper_toolkit_mcp_CORE_API_KEY": "",
        "paper_toolkit_mcp_SEMANTIC_SCHOLAR_API_KEY": "",
        "paper_toolkit_mcp_ZENODO_ACCESS_TOKEN": "",
        "paper_toolkit_mcp_GOOGLE_SCHOLAR_PROXY_URL": "",
        "paper_toolkit_mcp_IEEE_API_KEY": "",
        "paper_toolkit_mcp_ACM_API_KEY": ""
      }
    }
  }
}
```

> If `python` is not on your PATH, replace it with the full path (e.g. `/usr/bin/python3` or `C:\Python311\python.exe`). Run `which python3` / `where python` to find it.

---

### Install from Source (Development)

For development or customization, clone the repo and install in editable mode:

```bash
# 1. Clone your forked repo
git clone https://github.com/YOUR_USERNAME/paper-toolkit-mcp.git
cd paper-toolkit-mcp

# 2. Create a virtual environment and install
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e ".[dev]"

# 3. Verify it works
python -m paper_toolkit_mcp.server
# or
paper-toolkit search "machine learning" -s arxiv,semantic
```

**Claude Desktop / Trae IDE config** (replace the path with your actual clone location):

```json
{
  "mcpServers": {
    "paper-toolkit-mcp": {
      "command": "python",
      "args": ["-m", "paper_toolkit_mcp.server"],
      "env": {
        "paper_toolkit_mcp_UNPAYWALL_EMAIL": "your@email.com",
        "paper_toolkit_mcp_CORE_API_KEY": "",
        "paper_toolkit_mcp_SEMANTIC_SCHOLAR_API_KEY": ""
      }
    }
  }
}
```

Run from your project directory, or set the `cwd` appropriately so the `.env` file and `.paper_cache/` resolve relative to the project root.

---

### Environment Variables (`.env` file)

Instead of putting keys directly in the JSON config you can store them in a `.env` file in the project root (auto-loaded on startup):

```bash
cp .env.example .env   # if running from source
# or create ~/.paper-toolkit-mcp.env for global use
```

```dotenv
paper_toolkit_mcp_UNPAYWALL_EMAIL=your@email.com
paper_toolkit_mcp_CORE_API_KEY=
paper_toolkit_mcp_SEMANTIC_SCHOLAR_API_KEY=
paper_toolkit_mcp_ZENODO_ACCESS_TOKEN=
paper_toolkit_mcp_GOOGLE_SCHOLAR_PROXY_URL=
paper_toolkit_mcp_IEEE_API_KEY=
paper_toolkit_mcp_ACM_API_KEY=
```

To use a custom path: `export paper_toolkit_mcp_ENV_FILE=/absolute/path/to/.env`

> Legacy variable names without the `paper_toolkit_mcp_` prefix (e.g. `CORE_API_KEY`, `UNPAYWALL_EMAIL`) are still supported for backward compatibility.

---

## Contributing

We welcome contributions! Here's how to get started:

1. **Fork the Repository**:
   Click "Fork" on GitHub.

2. **Clone and Set Up**:

   ```bash
   git clone https://github.com/yourusername/paper-toolkit-mcp.git
   cd paper-toolkit-mcp
   python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
   pip install -e ".[dev]"
   ```

3. **Make Changes**:

   - Add new platforms in `academic_platforms/`.
   - Update tests in `tests/`.

4. **Submit a Pull Request**:
   Push changes and create a PR on GitHub.

### Testing

```bash
# Hermetic unit tests (run in CI, no network) — includes coverage gate (≥20%)
pytest

# Real-fetch integration tests (local only, requires network)
# Verifies each source actually retrieves abstracts and full text.
pytest tests/integration/test_live_fetch.py -m integration --no-cov
```

---

## Demo

<img src="docs/images/demo.png" alt="Demo" width="800">

## TODO

### Planned Academic Platforms

- [√] arXiv
- [√] PubMed
- [√] bioRxiv
- [√] medRxiv
- [√] Google Scholar
- [√] IACR ePrint Archive
- [√] Semantic Scholar
- [√] Crossref
- [√] PubMed Central (PMC)
- [√] CORE
- [√] Europe PMC
- [√] Sci-Hub warning and enablement docs

### Development Tasks
- [√] Fix Async search bugs and ensure reliable fast MCP events
- [√] End-to-End full pipeline testing script (search, parse, download)
- [√] Establish two-layer federated architecture (Layer 1 tool: `search_papers`)
- [√] Ensure pervasive DOI extraction across metadata fields & abstract fallbacks
- [ ] Citation graph & Paper relation context feature
- [√] Expand full-stack OpenAlex provider

### Priority Free and Open Sources

- [√] PubMed Central (PMC)
- [√] CORE
- [√] OpenAlex
- [√] Europe PMC
- [√] OpenAIRE
- [√] dblp
- [√] CiteSeerX
- [√] DOAJ
- [√] BASE
- [√] Zenodo
- [√] HAL
- [√] SSRN (discovery + best-effort full-text)
- [√] Unpaywall (standalone DOI search source)

### Optional and Non-Core Integrations

- [ ] ResearchGate
- [ ] JSTOR
- [ ] ScienceDirect
- [ ] Springer Link
- [√] IEEE Xplore (optional skeleton — activate with `IEEE_API_KEY`)
- [√] ACM Digital Library (optional skeleton — activate with `ACM_API_KEY`)
- [ ] Web of Science
- [ ] Scopus

---

## Star History

[![Star History Chart](https://api.star-history.com/svg?repos=czwziy/paper-toolkit-mcp&type=Date)](https://star-history.com/#czwziy/paper-toolkit-mcp&Date)

---

## License

This project is licensed under the MIT License. See the LICENSE file for details.

---

Happy researching with `paper-toolkit-mcp`! If you encounter issues, open a GitHub issue.
