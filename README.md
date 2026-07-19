**English** | [中文](README_zh.md)

# Paper Toolkit MCP

> A comprehensive MCP toolkit for academic paper searching, manuscript processing, and citation management.

![PyPI](https://img.shields.io/pypi/v/paper-toolkit-mcp.svg) ![License](https://img.shields.io/badge/license-MIT-blue.svg) ![Python](https://img.shields.io/badge/python-3.10+-blue.svg)

---

## Features

### Paper Search & Download
- Multi-source search: arXiv, Semantic Scholar, PubMed, Crossref, OpenAlex, PMC, medRxiv, DBLP, Europe PMC, OpenAIRE, SSRN, IEEE, ACM
- PDF download with automatic fallback (Unpaywall → OA repositories → Sci-Hub)
- Text extraction from PDFs

### Reference Management
- SQLite-based local library
- BibTeX/RIS export
- Citation key generation
- Author name auto-normalization (Surname, Given format)

### Manuscript Processing
- Markdown citation placeholder replacement & reference list generation
- Human review copy generation (cite_key → Author(Year) DOI)
- Multiple citation styles: GB/T 7714-2015, APA 7th, IEEE
- Writing templates

### Manuscript Harness
- 30 automated verification rules (R0-R9) with local/global scope
- Chinese language enforcement
- Citation format validation
- Word count checking
- Writing/final mode switching (chapter/draft/final)

### Citation Verification
- Multi-model LLM scoring for citation accuracy
- Incremental caching to avoid re-verification
- Single-citation and full-manuscript batch verification

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
      "command": "paper-toolkit-mcp",
      "env": {
        "paper_toolkit_mcp_WORK_DIR": "/path/to/your/project"
      }
    }
  }
}
```

> **Note**: Set `paper_toolkit_mcp_WORK_DIR` to your project directory so that `papers.db`, downloads, and cache are stored there.

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
| `search_papers` | Multi-source search (supports groups: medical/cs/metadata) |
| `get_paper_by_doi` | Get paper metadata by DOI (CrossRef + Semantic Scholar fallback) |
| `download_paper` | Download PDF (source-native → OA repos → Unpaywall → Sci-Hub) |
| `download_by_cite_key` | Download by citation key |
| `read_by_cite_key` | Download and extract PDF text |

### Library Management

| Tool | Description |
|------|-------------|
| `library_search` | Search local library |
| `library_stats` | Get library statistics |
| `cache_clear` | Clear search cache |

### Manuscript Processing

| Tool | Description |
|------|-------------|
| `process_manuscript` | Process Markdown manuscript, replace citation placeholders & generate outputs |
| `get_paper_metadata` | Get full metadata for a single paper |
| `export_references` | Batch export references (BibTeX/RIS/text) |
| `get_writing_template` | Get writing template |
| `generate_ref_list` | Generate reference list from manuscript cite_keys |
| `generate_human_review` | Generate human review copy (cite_key → Author(Year) DOI) |

### Manuscript Harness

| Tool | Description |
|------|-------------|
| `harness_init` | Initialize harness infrastructure |
| `harness_verify` | Verify manuscript against rules |
| `harness_list_rules` | List all rules (with scope and draft_skip markers) |

### Citation Verification

| Tool | Description |
|------|-------------|
| `verify_citation` | Verify a single citation (multi-model LLM scoring) |
| `verify_manuscript` | Batch verify all citations in a manuscript |
| `verify_config` | Check verifier configuration & model connectivity |

---

## Harness Rules

| Rule | Category | Scope | Description |
|------|----------|-------|-------------|
| R0 | Language | local | Chinese language enforcement |
| R1 | Structure | local | Heading hierarchy, heading length, no lists/bold |
| R2 | Data | local/global | P-value, mean±SD, statistics, data consistency |
| R3 | Sections | global | Required chapters (intro/methods/results/discussion/conclusion) |
| R4 | Terminology | local | Abbreviation consistency, humble phrasing |
| R5 | Citations | local/global | cite_key format, density, total reference count |
| R6 | Position | local | Citation placement, multi-citation format |
| R7 | AI Trace | local | No colon in headings, no self-praise/back-reference, user comments |
| R8 | Word Count | local/global | 3000-8000 words total, paragraph length, abstract length |
| R9 | Tables/Figures | local/global | Three-line table, 300dpi, figure numbering |

> **Scope**: `local` rules can be checked by sub-agents on individual chapters; `global` rules require the full merged manuscript. In draft mode, abstract word count (R8.3) and total reference count (R5.4) are automatically skipped.

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
