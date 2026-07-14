**English** | [中文](README_zh.md)

# Paper Toolkit MCP

> A comprehensive MCP toolkit for academic paper searching, manuscript processing, and citation management.

![PyPI](https://img.shields.io/pypi/v/paper-toolkit-mcp.svg) ![License](https://img.shields.io/badge/license-MIT-blue.svg) ![Python](https://img.shields.io/badge/python-3.10+-blue.svg)

---

## Features

### Paper Search & Download
- Multi-source search: arXiv, Semantic Scholar, PubMed, Crossref, OpenAlex
- PDF download with automatic fallback
- Text extraction from PDFs

### Reference Management
- SQLite-based local library
- BibTeX/RIS export
- Citation key generation

### Manuscript Harness (v0.3.0)
- Automated verification with 27 rules (R0-R9)
- Chinese language enforcement
- Citation format validation
- Word count checking

---

## Quick Start

### Installation

```bash
pip install paper-toolkit-mcp
```

### MCP Configuration

Add to your MCP client config:

```json
{
  "mcpServers": {
    "paper-toolkit-mcp": {
      "command": "paper-toolkit-mcp"
    }
  }
}
```

### API Keys (Optional)

All sources work without API keys. Optional keys improve rate limits:

```bash
# Copy example and fill in available keys
cp .env.example .env
```

See `.env.example` for all available keys.

---

## MCP Tools

### Search & Download

| Tool | Description |
|------|-------------|
| `search_papers` | Search papers from multiple sources |
| `get_paper_by_doi` | Get paper metadata by DOI |
| `download_paper` | Download PDF |
| `download_by_cite_key` | Download by citation key |
| `read_by_cite_key` | Read PDF text |

### Library Management

| Tool | Description |
|------|-------------|
| `library_search` | Search local library |
| `library_stats` | Get library statistics |
| `cache_clear` | Clear search cache |

### Manuscript Harness

| Tool | Description |
|------|-------------|
| `harness_init` | Initialize harness infrastructure |
| `harness_verify` | Verify manuscript against rules |
| `harness_list_rules` | List all verification rules |

---

## Harness Rules

| Rule | Category | Description |
|------|----------|-------------|
| R0 | Language | Chinese language enforcement |
| R1 | Structure | Heading hierarchy, no lists/bold |
| R2 | Data | P-value, mean±SD, statistics |
| R3 | Sections | Required chapters |
| R4 | Terminology | Abbreviation consistency |
| R5 | Citations | cite_key format, density |
| R6 | Position | Citation placement |
| R7 | AI Trace | No self-praise, no back-reference |
| R8 | Word Count | 3000-8000 words total |
| R9 | Tables/Figures | Three-line table, 300dpi |

---

## Development

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Lint
ruff check paper_toolkit_mcp tests

# Type check
mypy paper_toolkit_mcp
```

---

## License

MIT

---

## Links

- [GitHub](https://github.com/czwziy/paper-toolkit-mcp)
- [PyPI](https://pypi.org/project/paper-toolkit-mcp/)
- [Publishing Guide](docs/publishing.md)
