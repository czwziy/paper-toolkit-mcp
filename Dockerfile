# Multi-stage build for smaller image
FROM python:3.12-slim AS builder

WORKDIR /app
COPY pyproject.toml README.md LICENSE ./
COPY paper_toolkit_mcp/ paper_toolkit_mcp/

RUN pip install --no-cache-dir build \
    && python -m build --wheel \
    && pip install --no-cache-dir dist/*.whl

FROM python:3.12-slim

WORKDIR /app
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin/paper-toolkit-mcp /usr/local/bin/paper-toolkit-mcp

# Environment variables (override at runtime with -e)
ENV paper_toolkit_mcp_UNPAYWALL_EMAIL=""
ENV paper_toolkit_mcp_CORE_API_KEY=""
ENV paper_toolkit_mcp_SEMANTIC_SCHOLAR_API_KEY=""
ENV paper_toolkit_mcp_ZENODO_ACCESS_TOKEN=""
ENV paper_toolkit_mcp_DOAJ_API_KEY=""
ENV paper_toolkit_mcp_GOOGLE_SCHOLAR_PROXY_URL=""
ENV paper_toolkit_mcp_IEEE_API_KEY=""
ENV paper_toolkit_mcp_ACM_API_KEY=""

# Use the entry point script
CMD ["paper-toolkit-mcp"]
