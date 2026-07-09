# 需求文档（PRD）— paper-toolkit-mcp

| 字段 | 值 |
|---|---|
| 文档版本 | v0.2.0 |
| 创建日期 | 2026-07-09 |
| 状态 | 已实现（Beta） |
| 对应代码版本 | [pyproject.toml](../../pyproject.toml#L7) `version = "0.2.0"` |
| 架构参考 | [architecture/overview.md](architecture/overview.md)、[architecture/boundaries.md](architecture/boundaries.md) |
| 工程约束 | [constraints/contracts.md](../constraints/contracts.md) |

> 本文档描述 paper-toolkit-mcp 的产品需求。当前版本反映**已发布 v0.2.0 的实现状态**，未来迭代项以 TODO 形式标注。

---

## 1. 引言

### 1.1 目的

本文档定义 paper-toolkit-mcp 的功能边界、用户场景、验收标准与非功能约束，作为：
- 开发者新增/修改功能的对照基线；
- 用户评估工具适用性的依据；
- AI 代理（Claude / Trae 等）理解项目能力的知识源。

### 1.2 范围

paper-toolkit-mcp 是一个**学术论文工具包**，提供文献检索、PDF 下载、全文抽取、引用生成、手稿排版五类能力，以 **MCP Server** 与 **CLI** 双形态对外服务。**不包含**：文献管理数据库、协同写作、PDF 阅读器 UI、引文图谱可视化。

### 1.3 术语

| 术语 | 定义 |
|---|---|
| MCP | Model Context Protocol，AI 客户端与外部工具通信的协议 |
| PaperSource | 所有学术平台搜索器的抽象基类（[academic_platforms/base.py](../../paper_toolkit_mcp/academic_platforms/base.py#L7)） |
| 源（source） | 单个学术平台连接器，如 `arxiv`、`pubmed` |
| 占位符 | 手稿中的 `[@doi:...]` / `[@pmid:...]` / `[@arxiv:...]` / `[@title:...]` 标记 |
| OA | Open Access，开放获取 |
| OAI-PMH | Open Archives Initiative Protocol for Metadata Harvesting |
| CSL | Citation Style Language，引用样式语言 |
| WORK_DIR | 统一工作目录，所有下载与缓存的根（[config.py](../../paper_toolkit_mcp/config.py#L115)） |

### 1.4 参考文档

- [README.md](../../README.md) — 用户手册
- [CLAUDE.md](../../CLAUDE.md) — AI 会话知识地图
- [.env.example](../../.env.example) — 配置模板

---

## 2. 项目概述

### 2.1 背景

学术研究流程中"检索—下载—阅读—引用—成稿"分散在多个工具中，且多数商业数据库需要订阅。研究者（尤其 LLM 辅助写作场景）需要一个统一、免费优先、可被 AI 直接调用的工具层。

### 2.2 项目目标

| 目标 | 度量 |
|---|---|
| G1 统一检索入口 | 单次调用并发查询 ≥20 个学术源，结果标准化去重 |
| G2 免费优先 | 核心源全部基于公开 API，付费源可选激活 |
| G3 LLM 友好 | 输出标准化 dict，可直接进入 LLM 上下文 |
| G4 手稿闭环 | 从 Markdown 占位符到 Word 终稿一键完成 |
| G5 可扩展 | 新增一个学术源 ≤1 个文件 + 2 处注册 |

### 2.3 用户画像

| 用户 | 主要场景 | 关键诉求 |
|---|---|---|
| 研究者 | 文献综述、追踪领域、撰写论文 | 多源检索、引用格式正确、Word 输出 |
| AI 辅助写作用户 | 让 Claude/Cursor 自动找文献并插入论文 | MCP 工具稳定、结果结构化 |
| 工具开发者 | 集成到自有流水线 | CLI 可脚本化、JSON 输出 |
| 数据抓取者 | 批量获取元数据 | 缓存、DOI 反查、可降级 |

### 2.4 典型场景

**场景 A — LLM 辅助综述**
用户在 Claude Desktop 中提问"近三年 Transformer 架构改进综述"，Claude 调用 `search_papers` 跨 arXiv/Semantic Scholar/CrossRef 检索，再用 `download_with_fallback` 获取 OA 全文，最后用 `process_manuscript` 生成带 GB/T 7714 引用的 Word 草稿。

**场景 B — 命令行批处理**
开发者写脚本 `paper-toolkit search "AlphaFold" -s crossref -n 50 > refs.json`，再导入 Zotero。

**场景 C — 单篇元数据回填**
手稿中有 `[@doi:10.1038/s41586-021-03819-2]`，`process_manuscript` 自动通过 CrossRef 取回标题/作者/期刊并生成参考文献列表。

---

## 3. 功能需求

> 需求编号规则：`FR-<模块>-<序号>`。优先级：P0 必须 / P1 重要 / P2 可选。

### 3.1 FR-SRC 学术源连接器

| ID | 需求 | 优先级 | 验收标准 | 实现位置 |
|---|---|---|---|---|
| FR-SRC-01 | 提供 `PaperSource` 抽象基类，定义 `search`/`download_pdf`/`read_paper`/`search_with_cache` 接口 | P0 | 新源继承后只需实现 `search`，其余可默认抛 `NotImplementedError` | [base.py:7](../../paper_toolkit_mcp/academic_platforms/base.py#L7) |
| FR-SRC-02 | 支持 arXiv（Atom Feed） | P0 | `paper-toolkit search "x" -s arxiv -n 5` 返回 ≥1 篇，含 pdf_url | [arxiv.py:15](../../paper_toolkit_mcp/academic_platforms/arxiv.py#L15) |
| FR-SRC-03 | 支持 PubMed（NCBI EUtils XML） | P0 | 同上 | [pubmed.py:12](../../paper_toolkit_mcp/academic_platforms/pubmed.py#L12) |
| FR-SRC-04 | 支持 bioRxiv / medRxiv（REST JSON） | P0 | 两个源均返回结果 | [biorxiv.py:11](../../paper_toolkit_mcp/academic_platforms/biorxiv.py#L11)、[medrxiv.py:11](../../paper_toolkit_mcp/academic_platforms/medrxiv.py#L11) |
| FR-SRC-05 | 支持 Semantic Scholar（Graph API，可选 key） | P0 | 无 key 可用（受速率限制）；有 key 速率提升；key 被拒（403）自动降级匿名 | [semantic.py:20](../../paper_toolkit_mcp/academic_platforms/semantic.py#L20) |
| FR-SRC-06 | 支持 CrossRef / OpenAlex（元数据主干，REST JSON） | P0 | 按 DOI 与按关键词均可查 | [crossref.py:14](../../paper_toolkit_mcp/academic_platforms/crossref.py#L14)、[openalex.py:13](../../paper_toolkit_mcp/academic_platforms/openalex.py#L13) |
| FR-SRC-07 | 支持 PMC / Europe PMC / CORE（OA 全文仓库） | P0 | 返回结果；OA PDF 可下载 | [pmc.py:20](../../paper_toolkit_mcp/academic_platforms/pmc.py#L20)、[europepmc.py:17](../../paper_toolkit_mcp/academic_platforms/europepmc.py#L17)、[core.py:20](../../paper_toolkit_mcp/academic_platforms/core.py#L20) |
| FR-SRC-08 | 支持 dblp / CiteSeerX / DOAJ / BASE / OpenAIRE | P0 | 各源 `search` 返回结果（BASE/CiteSeerX 容许返回空） | [dblp.py](../../paper_toolkit_mcp/academic_platforms/dblp.py)、[citeseerx.py](../../paper_toolkit_mcp/academic_platforms/citeseerx.py)、[doaj.py](../../paper_toolkit_mcp/academic_platforms/doaj.py)、[base_search.py](../../paper_toolkit_mcp/academic_platforms/base_search.py)、[openaire.py](../../paper_toolkit_mcp/academic_platforms/openaire.py) |
| FR-SRC-09 | 支持 Zenodo / HAL / SSRN / Unpaywall | P0 | Zenodo/HAL 返回结果；SSRN 返回结果或明确失败消息；Unpaywall 需配置 email | [zenodo.py](../../paper_toolkit_mcp/academic_platforms/zenodo.py)、[hal.py](../../paper_toolkit_mcp/academic_platforms/hal.py)、[ssrn.py](../../paper_toolkit_mcp/academic_platforms/ssrn.py)、[unpaywall.py](../../paper_toolkit_mcp/academic_platforms/unpaywall.py) |
| FR-SRC-10 | 支持 Google Scholar（HTML 抓取，可选代理） | P1 | 无代理可能被验证码拦截，返回空；配置 `GOOGLE_SCHOLAR_PROXY_URL` 后可用 | [google_scholar.py:16](../../paper_toolkit_mcp/academic_platforms/google_scholar.py#L16) |
| FR-SRC-11 | 支持 IACR ePrint（HTML 抓取） | P1 | 返回结果，可下载 PDF | [iacr.py:17](../../paper_toolkit_mcp/academic_platforms/iacr.py#L17) |
| FR-SRC-12 | 可选激活 IEEE Xplore / ACM DL（需 API Key） | P2 | 无 key 时仅启动告警，不注册工具；有 key 时注册 search/download/read（download/read 当前为 skeleton，抛 `NotImplementedError`） | [ieee.py:33](../../paper_toolkit_mcp/academic_platforms/ieee.py#L33)、[acm.py:39](../../paper_toolkit_mcp/academic_platforms/acm.py#L39) |
| FR-SRC-13 | 新增源无需改动核心层 | P0 | 新源只需放在 `academic_platforms/`，在 `server.py` 与 `cli.py` 注册即可；反向 import 由 `lint-imports` 禁止 | [pyproject.toml tool.importlinter](../../pyproject.toml#L163) |

### 3.2 FR-SEARCH 统一检索

| ID | 需求 | 优先级 | 验收标准 | 实现位置 |
|---|---|---|---|---|
| FR-SEARCH-01 | 提供 `search_papers` 跨源并发检索 | P0 | 指定多个源时并发请求，单源失败不影响其他源，错误归入 `errors` 字段 | [server.py:260](../../paper_toolkit_mcp/server.py#L260) |
| FR-SEARCH-02 | 结果按 DOI→title→id 三级 key 去重 | P0 | 同一篇论文跨源出现时合并为一条 | [server.py:170](../../paper_toolkit_mcp/server.py#L170) `_dedupe_papers` |
| FR-SEARCH-03 | 支持 `sources` / `max_results_per_source` / `year` 参数 | P0 | `year` 仅 Semantic Scholar 生效（已文档化） | [server.py:260](../../paper_toolkit_mcp/server.py#L260) |
| FR-SEARCH-04 | 各源同时暴露独立 `search_<source>` 工具 | P1 | 每个默认源都有独立 MCP 工具，便于定向查询 | [server.py:377-1055](../../paper_toolkit_mcp/server.py#L377) |
| FR-SEARCH-05 | 输出标准化 `Paper` dict | P0 | 字段集见 [paper.py:7](../../paper_toolkit_mcp/paper.py#L7)；`authors`/`categories` 等用 `; ` 连接 | [paper.py:41](../../paper_toolkit_mcp/paper.py#L41) `to_dict` |

### 3.3 FR-DL 下载与全文抽取

| ID | 需求 | 优先级 | 验收标准 | 实现位置 |
|---|---|---|---|---|
| FR-DL-01 | 各源提供 `download_<source>` 下载 PDF | P0 | 支持下载的源返回本地 PDF 路径；不支持的源返回明确消息 | [server.py:475-1275](../../paper_toolkit_mcp/server.py#L475) |
| FR-DL-02 | 提供 `download_with_fallback` 多级回退链 | P0 | 顺序：源原生 → OA 仓库（OpenAIRE/CORE/EuropePMC/PMC）→ Unpaywall → 可选 Sci-Hub | [server.py:775](../../paper_toolkit_mcp/server.py#L775) |
| FR-DL-03 | 提供 `download_scihub`（可选，需用户主动调用） | P2 | README 明示法律风险与用户责任；默认不在 fallback 中启用除非用户调用 | [server.py:753](../../paper_toolkit_mcp/server.py#L753) |
| FR-DL-04 | 提供 `read_<source>_paper` 抽取全文文本 | P0 | 下载 PDF 后用 `pypdf` 抽取文本返回 | [server.py:543-1290](../../paper_toolkit_mcp/server.py#L543) |
| FR-DL-05 | 默认下载目录为 `WORK_DIR/downloads` | P0 | 跟随工作目录，不污染系统目录 | [server.py:53](../../paper_toolkit_mcp/server.py#L53) |

### 3.4 FR-REF 引用与手稿处理

| ID | 需求 | 优先级 | 验收标准 | 实现位置 |
|---|---|---|---|---|
| FR-REF-01 | 解析 4 类占位符：`[@doi:...]`/`[@pmid:...]`/`[@arxiv:...]`/`[@title:...]` | P0 | 正则 `\[@(doi\|pmid\|arxiv\|title):([^\]]+)\]`，返回位置与全文匹配 | [reference.py:17](../../paper_toolkit_mcp/reference.py#L17) |
| FR-REF-02 | 按标识符取元数据（DOI→CrossRef，PMID→NCBI，arXiv→Atom，title→CrossRef） | P0 | 实测 `get_paper_by_identifier('doi','10.1038/s41586-021-03819-2')` 返回完整字段 | [reference.py:612](../../paper_toolkit_mcp/reference.py#L612) |
| FR-REF-03 | 生成 BibTeX | P0 | 输出 `@article{...}`，含 author/title/year/journal/volume/number/pages/doi/url | [reference.py:51](../../paper_toolkit_mcp/reference.py#L51) |
| FR-REF-04 | 生成 RIS | P0 | 兼容 Zotero/Mendeley/EndNote，含 TY/AU/PY/DO/UR 等字段 | [reference.py:130](../../paper_toolkit_mcp/reference.py#L130) |
| FR-REF-05 | 内置 3 种引用样式 formatter：GB/T 7714 / APA 7th / IEEE | P0 | `generate_reference_list(papers, style)` 输出 `[1] ...` 编号列表，未知 style 抛 `ValueError` | [reference.py:318-454](../../paper_toolkit_mcp/reference.py#L318) |
| FR-REF-06 | 支持 5 种 CSL 样式（含 Vancouver / Harvard）经 pandoc 渲染 | P1 | `csl/` 目录含 5 个 .csl 文件；`--docx` 时按 style 选用 | [server.py:1531](../../paper_toolkit_mcp/server.py#L1531) |
| FR-REF-07 | `process_manuscript` 完整流水线 | P0 | 输入 Markdown → 输出 formatted.md + refs.bib + refs.ris + references.txt + （可选）docx | [server.py:1406](../../paper_toolkit_mcp/server.py#L1406) |
| FR-REF-08 | 未解析占位符归入 `unresolved` 列表 | P1 | 处理结果含 `unresolved` 字段，不静默丢失 | [reference.py:491](../../paper_toolkit_mcp/reference.py#L491) |
| FR-REF-09 | `export_references` 批量导出 bibtex/ris/text | P1 | text 模式可选 style | [server.py:1611](../../paper_toolkit_mcp/server.py#L1611) |
| FR-REF-10 | pandoc 缺失时优雅降级 | P1 | `pandoc_available()` 检测；缺失时跳过 docx 生成，其余产物仍生成 | [pandoc_helper.py:8](../../paper_toolkit_mcp/pandoc_helper.py#L8) |

### 3.5 FR-CACHE 缓存

| ID | 需求 | 优先级 | 验收标准 | 实现位置 |
|---|---|---|---|---|
| FR-CACHE-01 | 搜索结果自动缓存为 JSON | P0 | 缓存命中且未过 TTL 直接返回，未命中则请求并写回 | [base.py:18](../../paper_toolkit_mcp/academic_platforms/base.py#L18) `search_with_cache` |
| FR-CACHE-02 | 缓存键 = MD5(source:query:kwargs) | P0 | 同参数命中同一文件 | [cache.py:35](../../paper_toolkit_mcp/cache.py#L35) |
| FR-CACHE-03 | 默认 TTL 24 小时 | P0 | 可通过 `--cache-ttl`（CLI）/参数覆盖 | [cache.py:15](../../paper_toolkit_mcp/cache.py#L15) |
| FR-CACHE-04 | 缓存目录默认 `WORK_DIR/.paper_cache` | P0 | 跟随工作目录，便于随项目迁移 | [server.py:58](../../paper_toolkit_mcp/server.py#L58) |
| FR-CACHE-05 | 提供 `cache_list` / `cache_clear` 工具与 CLI 子命令 | P0 | list 返回每条缓存的 query/source/count/timestamp/is_expired；clear 返回清除条数 | [server.py:1671](../../paper_toolkit_mcp/server.py#L1671)、[cli.py:453](../../paper_toolkit_mcp/cli.py#L453) |

### 3.6 FR-IFACE 双入口

| ID | 需求 | 优先级 | 验收标准 | 实现位置 |
|---|---|---|---|---|
| FR-IFACE-01 | 提供 MCP Server（stdio 传输） | P0 | `python -m paper_toolkit_mcp.server` 启动，工具数 = 默认源×3 + 统一工具 + 条件工具 | [server.py:1700](../../paper_toolkit_mcp/server.py#L1700) |
| FR-IFACE-02 | 提供 CLI（argparse） | P0 | 6 个子命令：search/download/read/sources/manuscript/cache | [cli.py:403](../../paper_toolkit_mcp/cli.py#L403) |
| FR-IFACE-03 | MCP 与 CLI 共享同一套 searcher 实现 | P0 | 避免行为分叉；新增源两处都要注册（棕地陷阱，见 CLAUDE.md） | [cli.py:43](../../paper_toolkit_mcp/cli.py#L43) `SEARCHERS` |
| FR-IFACE-04 | CLI 输出 JSON | P0 | 便于脚本化与管道处理 | [cli.py:146](../../paper_toolkit_mcp/cli.py#L146) |

### 3.7 FR-CONFIG 配置

| ID | 需求 | 优先级 | 验收标准 | 实现位置 |
|---|---|---|---|---|
| FR-CONFIG-01 | 所有密钥通过 `config.get_env(name)` 读取，禁止硬编码 | P0 | CI lint 强制；`.env` 文件 gitignored | [config.py:100](../../paper_toolkit_mcp/config.py#L100) |
| FR-CONFIG-02 | 统一前缀 `paper_toolkit_mcp_`，兼容无前缀旧名 | P0 | 两种命名都能识别 | [config.py:107](../../paper_toolkit_mcp/config.py#L107) |
| FR-CONFIG-03 | `.env` 自动发现：`ENV_FILE` > `WORK_DIR/.env` > `CWD/.env` > 项目根 `.env` | P0 | 按序查找，首个存在者生效 | [config.py:26](../../paper_toolkit_mcp/config.py#L26) |
| FR-CONFIG-04 | 提供 `.env.example` 模板 | P0 | 列出全部可选 key 与说明 | [.env.example](../../.env.example) |

---

## 4. 非功能需求

### 4.1 NFR-PERF 性能

| ID | 需求 | 度量 |
|---|---|---|
| NFR-PERF-01 | 多源搜索并发执行 | `search_papers` 总耗时 ≈ 最慢源耗时（非求和） |
| NFR-PERF-02 | 缓存命中时零网络 IO | 命中返回 < 100ms |
| NFR-PERF-03 | 单源超时不阻塞整体 | 单源失败归入 `errors`，不影响其他源 |

### 4.2 NFR-REL 可靠性

| ID | 需求 | 度量 |
|---|---|---|
| NFR-REL-01 | 上游 429/403 自动退避 | Semantic Scholar / CORE / OpenAIRE 均实现重试与降级 |
| NFR-REL-02 | 上游不可达时优雅返回空 | 不抛异常中断；返回空列表 + 错误消息 |
| NFR-REL-03 | 缓存损坏不影响运行 | `_load_env_from_file` 与缓存读取均 try/except |

### 4.3 NFR-SEC 安全

| ID | 需求 | 度量 |
|---|---|---|
| NFR-SEC-01 | 禁止硬编码 API key | [contracts.md](../constraints/contracts.md) 硬性规则 + CI 强制 |
| NFR-SEC-02 | `.env` 不入库 | [.gitignore](../../.gitignore#L128) 覆盖 |
| NFR-SEC-03 | bandit 安全扫描 | CI 每次运行；配置见 [bandit.yaml](../constraints/security/bandit.yaml) |
| NFR-SEC-04 | Sci-Hub 默认不启用，明示法律风险 | 仅 `download_scihub` 显式调用或用户在 fallback 中主动配置 |

### 4.4 NFR-MAINT 可维护性

| ID | 需求 | 度量 |
|---|---|---|
| NFR-MAINT-01 | 分层依赖单向 | `lint-imports` CI 强制；违规则 CI 红 |
| NFR-MAINT-02 | 单文件 ≤400 行 | CI 文件大小门禁；历史超标文件见豁免清单 |
| NFR-MAINT-03 | ruff 风格统一 | line-length=120，规则集见 [pyproject.toml](../../pyproject.toml#L84) |
| NFR-MAINT-04 | mypy 类型检查 | 渐进收紧；当前已清零 107 处历史类型问题 |
| NFR-MAINT-05 | 覆盖率门禁 ≥20% | `--cov-fail-under=20`；目标 50% 渐进提升 |
| NFR-MAINT-06 | 测试拆分：unit 离线 / integration 触网 | CI 仅跑 `tests/unit`；integration 手动触发 |

### 4.5 NFR-COMP 兼容性

| ID | 需求 | 度量 |
|---|---|---|
| NFR-COMP-01 | Python 3.10 / 3.11 / 3.12 / 3.13 | CI 矩阵验证 3.10/3.12/3.13 |
| NFR-COMP-02 | 跨平台（Windows / macOS / Linux） | 纯 Python，无平台特定依赖；pandoc 为可选外部依赖 |
| NFR-COMP-03 | MCP 客户端兼容 | 兼容 Claude Desktop / Trae IDE / 任意 MCP 客户端 |

---

## 5. 接口需求

### 5.1 MCP 工具接口（核心）

| 工具 | 入参 | 出参 | 行号 |
|---|---|---|---|
| `search_papers` | `query`, `sources=None`, `max_results_per_source=5`, `year=None` | `{total, source_results, errors, papers[]}` | [server.py:260](../../paper_toolkit_mcp/server.py#L260) |
| `get_paper_metadata` | `id_type`(doi/pmid/arxiv), `identifier` | `Paper dict \| null` | [server.py:1576](../../paper_toolkit_mcp/server.py#L1576) |
| `download_with_fallback` | `paper_id`, `source`, `doi=""`, `title=""`, `save_path=DEFAULT_SAVE_PATH`, `use_scihub=False` | `{success, file_path/error, source_used}` | [server.py:775](../../paper_toolkit_mcp/server.py#L775) |
| `process_manuscript` | `text`, `style="gb7714"`, `generate_docx=False`, `output_dir`, `cache_ttl` | `{processed_text, reference_list, citation_map, unresolved, files{}}` | [server.py:1406](../../paper_toolkit_mcp/server.py#L1406) |
| `export_references` | `papers[]`, `format`(bibtex/ris/text), `style` | `{success, content}` | [server.py:1611](../../paper_toolkit_mcp/server.py#L1611) |
| `cache_list` / `cache_clear` | — | 缓存清单 / 清除条数 | [server.py:1671](../../paper_toolkit_mcp/server.py#L1671) |
| `search_<source>` / `download_<source>` / `read_<source>_paper` | 各源特定 | 同上 | [server.py:377-1290](../../paper_toolkit_mcp/server.py#L377) |

### 5.2 CLI 接口

```
paper-toolkit search    <query> [-s sources] [-n N] [-y year]
paper-toolkit download  <source> <paper_id> [-o save_path]
paper-toolkit read      <source> <paper_id> [-o save_path]
paper-toolkit sources
paper-toolkit manuscript <draft.md> [-s style] [--docx] [-o output_dir] [--no-bib] [--no-ris] [--cache-ttl H]
paper-toolkit cache list|clear
```
详见 [cli.py:403](../../paper_toolkit_mcp/cli.py#L403)。

### 5.3 配置接口（环境变量）

| 变量 | 必需 | 作用 |
|---|---|---|
| `paper_toolkit_mcp_UNPAYWALL_EMAIL` | **是**（否则 Unpaywall 跳过） | Unpaywall DOI 解析 |
| `paper_toolkit_mcp_CORE_API_KEY` | 推荐 | CORE 速率提升 |
| `paper_toolkit_mcp_SEMANTIC_SCHOLAR_API_KEY` | 可选 | Semantic Scholar 速率提升 |
| `paper_toolkit_mcp_GOOGLE_SCHOLAR_PROXY_URL` | 可选 | 绕过 Google Scholar 验证码 |
| `paper_toolkit_mcp_DOAJ_API_KEY` | 可选 | DOAJ 速率提升 |
| `paper_toolkit_mcp_ZENODO_ACCESS_TOKEN` | 可选 | 私有 Zenodo 记录 |
| `paper_toolkit_mcp_IEEE_API_KEY` | 激活 IEEE 必需 | 启用 IEEE 工具 |
| `paper_toolkit_mcp_ACM_API_KEY` | 激活 ACM 必需 | 启用 ACM 工具 |
| `paper_toolkit_mcp_WORK_DIR` | 可选 | 统一工作目录 |
| `paper_toolkit_mcp_ENV_FILE` | 可选 | 显式指定 .env 路径 |

---

## 6. 约束与假设

### 6.1 约束

- **C1 免费优先**：核心源全部公开 API；付费源（IEEE/ACM）为可选 skeleton。
- **C2 单向分层**：`server/cli` → `academic_platforms` → `reference/pandoc_helper/cache/utils/config/paper`，禁止反向（[boundaries.md](architecture/boundaries.md)）。
- **C3 数据类纯净**：`paper.py` 不 import 任何上层模块。
- **C4 搜索器统一基类**：所有源必须继承 `PaperSource`。
- **C5 不可逆操作禁令**：禁止 `git push --force` 到 main/master；禁止删除 `csl/` 内置样式。
- **C6 测试隔离**：unit 必须 hermetic，integration 允许触网。

### 6.2 假设

- **A1** 用户有合法的网络访问权限访问各公开 API。
- **A2** Google Scholar / SSRN 等带反爬的源不保证稳定，依赖代理或可能失败。
- **A3** Sci-Hub 可用性受镜像与司法管辖影响，用户自行承担合规责任。
- **A4** pandoc 为可选外部依赖；缺失时仅 docx 生成不可用。
- **A5** 上游 API 字段变更可能导致个别源解析异常，应通过 integration 测试尽早发现。

---

## 7. 附录

### 7.1 平台能力矩阵（实测）

> ✅ 可靠 / ⚠️ 受上游不稳定影响 / ❌ 不支持 / 🔑 需 key / 🚧 skeleton

| 平台 | Search | Download | Read | 备注 |
|---|:---:|:---:|:---:|---|
| arXiv | ✅ | ✅ | ✅ | 实测通过（本文档验证） |
| PubMed | ✅ | ❌ | ⚠️ info-only | 元数据可靠 |
| bioRxiv / medRxiv | ✅ | ✅ | ✅ | 同 API |
| Semantic Scholar | ✅ | ✅(OA) | ✅(OA) | 无 key 受限，403 自动降级 |
| CrossRef | ✅ | ❌ | ⚠️ info-only | 实测 DOI 元数据获取通过 |
| OpenAlex | ✅ | ❌ | ⚠️ info-only | |
| PMC / Europe PMC | ✅ | ✅(OA) | ✅(OA) | 代理环境可能拦截 PDF |
| CORE | ✅ | ✅ | ✅ | 推荐 key |
| dblp | ✅ | ❌ | ⚠️ info-only | |
| OpenAIRE | ✅ | ❌ | ❌ | 瞬时 403 自动重试 3 级 |
| CiteSeerX | ⚠️ | ✅ | ⚠️ | 端点间歇不可用 |
| DOAJ | ✅ | ⚠️ | ⚠️ | PDF 视文章而定 |
| BASE | ⚠️ | ✅ | ✅ | OAI-PMH 需机构 IP |
| Zenodo / HAL | ✅ | ✅ | ✅ | 视记录而定 |
| SSRN | ⚠️ | ⚠️ | ⚠️ | Cloudflare 反爬 |
| Unpaywall | ✅(DOI) | ❌ | ❌ | 需 email |
| Google Scholar | ⚠️ | ❌ | ❌ | 需代理 |
| IACR | ✅ | ✅ | ✅ | |
| IEEE / ACM | 🚧 | 🚧 | 🚧 | 需 key 激活 |
| Sci-Hub | ⚠️ fallback | ✅ | ❌ | 可选，用户责任 |

### 7.2 验证记录（2026-07-09）

| 验证项 | 命令 | 结果 |
|---|---|---|
| 单源搜索 | `paper-toolkit search "transformer attention" -s arxiv -n 2` | ✅ 返回 2 篇，字段完整 |
| 多源并发 | `paper-toolkit search "deep learning" -s arxiv,crossref -n 1` | ✅ 返回 2 篇，errors={} |
| 源清单 | `paper-toolkit sources` | ✅ 20 个默认源全部注册 |
| DOI 元数据 | `get_paper_by_identifier('doi','10.1038/s41586-021-03819-2')` | ✅ 返回 AlphaFold 完整元数据（含 34 位作者、期刊、卷期页） |
| 单元测试 | `pytest tests/unit` | ⚠️ 本机 pytest 7.4.4 不满足 ≥8.0 要求，需 `pip install -e ".[dev]"` 升级 |

### 7.3 未来迭代（TODO）

- 引文图谱与论文关系上下文（README TODO 未完成项）
- IEEE / ACM skeleton 补全 download/read 实现
- ResearchGate / JSTOR / ScienceDirect / Springer / Web of Science / Scopus 集成（非核心）
- 覆盖率从 20% 渐进提升至 50%
- mypy 启用 `disallow_untyped_defs` / `strict`

---

## 8. 需求追溯矩阵

| 需求簇 | 关键 FR | 实现模块 | 验证方式 |
|---|---|---|---|
| 学术源连接器 | FR-SRC-01..13 | `academic_platforms/*` | integration 测试 + 实测 |
| 统一检索 | FR-SEARCH-01..05 | `server.py` 顶层工具 | unit `test_server_sources.py` + 实测 |
| 下载与抽取 | FR-DL-01..05 | `server.py` + `pypdf` | integration `test_e2e.py` |
| 引用与手稿 | FR-REF-01..10 | `reference.py` + `pandoc_helper.py` | unit `test_reference.py` |
| 缓存 | FR-CACHE-01..05 | `cache.py` + `base.py` | unit `test_cache.py` |
| 双入口 | FR-IFACE-01..04 | `server.py` + `cli.py` | unit + 手动 |
| 配置 | FR-CONFIG-01..04 | `config.py` | unit `test_config_env.py` |
