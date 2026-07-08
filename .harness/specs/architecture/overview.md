# 架构概览

## 技术栈

- **运行时**：Python 3.10+（支持至 3.13）
- **MCP 框架**：FastMCP（`mcp[cli]>=1.6.0`）
- **HTTP**：requests + httpx（支持 SOCKS 代理）
- **解析**：feedparser（Atom/RSS）、beautifulsoup4 + lxml（HTML）、pypdf（PDF）
- **文档转换**：Pandoc（系统二进制，`pandoc_helper.py` 封装）
- **打包**：hatchling → PyPI 包名 `paper-toolkit-mcp`
- **入口**：`paper-toolkit-mcp`（MCP server）/ `paper-toolkit`（CLI）

## 模块划分

```
paper_toolkit_mcp/
├── server.py              # FastMCP 入口：注册所有 MCP 工具，实例化 searcher
├── cli.py                 # argparse 入口：复用同一批 searcher
├── paper.py               # Paper dataclass（唯一数据载体，最底层依赖）
├── reference.py            # 引用占位符解析 + BibTeX/RIS/CSL 格式化
├── cache.py                # JSON 搜索缓存
├── config.py               # 环境变量加载（paper_toolkit_mcp_ 前缀）
├── utils.py                # DOI 提取等纯函数
├── pandoc_helper.py        # Pandoc 子进程封装
└── academic_platforms/     # 20+ 学术平台搜索器
    ├── base.py             # PaperSource 抽象基类
    ├── oaipmh.py           # OAI-PMH 协议基类
    ├── base_search.py      # BASE 仓储（基于 oaipmh）
    ├── arxiv.py / pubmed.py / biorxiv.py / medrxiv.py / ...
    └── sci_hub.py           # SciHubFetcher（独立下载器，不继承 PaperSource）
```

## 数据流

### 搜索流
```
MCP 工具 / CLI 命令
  → server.py / cli.py 路由到具体 searcher
    → PaperSource.search_with_cache()（命中缓存则返回）
      → 具体 searcher.search()（HTTP 请求 + 解析）
        → 构造 Paper 对象列表
  → 返回 List[Paper] → 序列化为 dict 给 MCP/CLI
```

### 手稿处理流
```
Markdown 源文件
  → reference.process_manuscript_text()
    → parse_citation_placeholders()（识别 [@doi:...] [@pmid:...] 等）
    → 逐个调用 searcher 拉取元数据
    → generate_bibtex() / generate_ris() / format_citation_*()
  → 输出格式化 Markdown + refs.bib + refs.ris
  → （可选）pandoc_helper.convert_to_docx() → draft_final.docx
```

## 部署拓扑

- **PyPI 包**：`pip install paper-toolkit-mcp` → 提供 `paper-toolkit-mcp` 命令
- **Docker**：`Dockerfile` 多阶段构建，`python:3.12-slim` 基础镜像
- **配置**：`.env` 文件（gitignored）或运行时环境变量
- **可选 API key**：Semantic Scholar / CORE / Unpaywall / DOAJ / Zenodo / IEEE / ACM / OpenAIRE / CiteSeerX（无 key 也可用，仅影响特定源覆盖率）

## 测试策略

- `tests/unit/` — hermetic 离线测试，CI 默认运行（mock 所有外部 IO）
- `tests/integration/` — 网络集成测试，手动或 nightly 运行（真实打 arXiv/PubMed 等 API）
- 拆分原则：任何在 import 或 setUp 阶段触网、或断言真实 API 响应的测试 → `integration/`
