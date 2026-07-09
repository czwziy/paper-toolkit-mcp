[English](README.md) | **中文**

# Scholar Toolkit MCP

> **Fork 声明**：本仓库是 [openags/paper-toolkit-mcp](https://github.com/openags/paper-toolkit-mcp) 的 fork，
> 原项目由 [P.S Zhang](https://github.com/openags) 创建。本 fork 在原项目基础上扩展了稿件处理、
> 搜索缓存以及引文导出等功能。两个版本均采用 MIT 协议授权。

一个用于论文检索、稿件处理和学术研究工作流的综合 MCP 工具集。项目遵循"免费优先"策略：优先使用开放和公开的数据源，在能够提升稳定性或覆盖范围时支持可选的 API key，并保持针对具体数据源的连接器可扩展，以便高级用户自行增强。

**新功能（v0.2.0）**：稿件处理（支持引文占位符）、搜索缓存、BibTeX/RIS 导出，以及一键生成 Word 文档。

![PyPI](https://img.shields.io/pypi/v/paper-toolkit-mcp.svg) ![License](https://img.shields.io/badge/license-MIT-blue.svg) ![Python](https://img.shields.io/badge/python-3.10+-blue.svg)

---

## 稿件处理（新功能）

### 工作流

1. **撰写**：使用带引文占位符的 Markdown 编写论文
2. **处理**：使用 `paper-toolkit manuscript` 命令处理
3. **导入**：将 `refs.ris` 导入 Zotero（可选）
4. **提交**：提交生成的 `draft_final.docx`

### 支持的占位符

```markdown
[@doi:10.1038/s41591-020-0001-2]
[@pmid:32145678]
[@arxiv:2106.12345]
[@title:Attention Is All You Need]
```

### 用法

```bash
# 基本用法（生成格式化 markdown + BibTeX + RIS）
paper-toolkit manuscript draft.md

# 生成 Word 文档（需要 pandoc）
paper-toolkit manuscript draft.md --docx

# 指定引文样式
paper-toolkit manuscript draft.md -s apa
paper-toolkit manuscript draft.md -s ieee
paper-toolkit manuscript draft.md -s gb7714

# 自定义输出目录
paper-toolkit manuscript draft.md -o ./output

# 禁用特定输出
paper-toolkit manuscript draft.md --no-bib --no-ris
```

### 引文样式

| 样式 | 代码 | 说明 |
|-------|------|-------------|
| GB/T 7714-2015 | `gb7714` | 中国国家标准（顺序编码制） |
| APA 7th | `apa` | 美国心理学会（American Psychological Association） |
| IEEE | `ieee` | 电气电子工程师学会（Institute of Electrical and Electronics Engineers） |
| Vancouver | `vancouver` | 国际医学期刊编辑委员会 |
| Harvard | `harvard` | 作者-年份格式 |

### 输出文件

处理完成后，你会得到：
- `draft_formatted.md` - 带编号引文 [1], [2], ... 的 Markdown
- `draft_final.docx` - Word 文档（使用了 `--docx` 且安装了 pandoc 时生成）
- `refs.bib` - BibTeX 文件（可导入 Zotero/JabRef）
- `refs.ris` - RIS 文件（兼容 Zotero/EndNote/Mendeley）
- `draft_references.txt` - 纯文本参考文献列表

---

## 搜索缓存（新功能）

### 工作原理

- 搜索结果以 JSON 文件形式缓存在 `.paper_cache/` 中
- 缓存位置跟随你的 **WORK_DIR**（默认为当前工作目录）
- 跟随你的项目文件夹 —— 复制文件夹，缓存随之移动
- TTL（生存时间）默认为 24 小时

### 缓存位置

```
your_project/
├── draft.md
├── refs.bib
└── .paper_cache/          ← 缓存在这里
    ├── abc123.json        ← 缓存的搜索结果
    └── def456.json
```

### 管理缓存

```bash
# 列出缓存项
paper-toolkit cache list

# 清空所有缓存
paper-toolkit cache clear
```

或通过 MCP 工具：`cache_list()`、`cache_clear()`

---

## CLI 用法

```bash
# 搜索论文
paper-toolkit search "machine learning" -s arxiv,semantic -n 10

# 下载 PDF
paper-toolkit download arxiv 2106.12345

# 阅读论文（提取文本）
paper-toolkit read arxiv 2106.12345

# 获取论文元数据
paper-toolkit search "attention is all you need" -s crossref -n 1

# 处理稿件
paper-toolkit manuscript draft.md -s gb7714 --docx

# 缓存管理
paper-toolkit cache list
paper-toolkit cache clear

# 列出可用数据源
paper-toolkit sources
```

---

## 目录

- [概述](#概述)
- [新功能](#新功能v020)
- [项目原则](#项目原则)
- [功能特性](#功能特性)
- [数据源策略](#数据源策略)
- [Sci-Hub 说明](#sci-hub-说明)
- [安装](#安装)
  - [从 PyPI 安装（pip）](#从-pypi-安装pip)
  - [从源码安装（开发）](#从源码安装开发)
  - [环境变量（.env 文件）](#环境变量env-文件)
- [稿件处理](#稿件处理新功能)
- [搜索缓存](#搜索缓存新功能)
- [CLI 用法](#cli-用法)
- [贡献](#贡献)
- [Star History](#star-history)
- [License](#license)
- [TODO](#todo)

---

## 新功能（v0.2.0）

### 稿件处理

使用带引文占位符的 Markdown 编写论文，然后自动生成带参考文献的格式化 Word 文档：

```markdown
# Introduction
Deep learning has made significant progress in medical imaging[@doi:10.1038/s41591-020-0001-2].
Transformer architecture revolutionized NLP[@title:Attention Is All You Need].
```

处理它：
```bash
paper-toolkit manuscript draft.md -s gb7714 --docx
```

输出：
- `draft_formatted.md` - 带编号引文 [1], [2], ... 的文本
- `refs.bib` - BibTeX 文件（用于导入 Zotero/EndNote）
- `refs.ris` - RIS 文件（兼容 Zotero）
- `draft_final.docx` - 带格式化参考文献的 Word 文档

支持的占位符：`[@doi:...]`、`[@pmid:...]`、`[@arxiv:...]`、`[@title:...]`

支持的引文样式：GB/T 7714-2015、APA 7th、IEEE、Vancouver、Harvard

### 搜索缓存

搜索结果会自动缓存到 `.paper_cache/` 中（位于你的 WORK_DIR 下，默认为 CWD）：
- **跟随你的工作区**：缓存保存在你正在工作的文件夹中
- **可移植**：复制项目文件夹，缓存随之移动
- **易于管理**：用户可手动删除 `.paper_cache/` 进行清理

### 新增的 MCP 工具
- `process_manuscript` - 处理带引文的稿件
- `get_paper_metadata` - 按标识符获取论文元数据
- `export_references` - 以 BibTeX/RIS/文本格式导出参考文献
- `cache_list` / `cache_clear` - 管理搜索缓存

---

## 概述

`paper-toolkit-mcp` 是一个基于 Python 的工具，用于从各种平台搜索和下载学术论文。它提供了搜索论文、下载 PDF 和提取文本的工具，非常适合研究人员和 AI 驱动的工作流。它可作为 MCP 服务器（用于 Claude Desktop 和其他 MCP 客户端）使用，也可作为带 CLI 界面的 Claude Code skill 使用。

## 项目原则

- **免费优先**：公开和开放的数据源是默认路线图。付费或受限的数据源不是本项目的核心方向。
- **可选 API Key**：仅在 API key 能改善稳定性、速率限制或元数据质量时才支持使用。MCP 应尽可能在没有 key 的情况下也可使用。
- **LLM 友好的检索**：搜索结果应标准化、去重，并尽可能完整，以便下游 LLM 工作流使用。
- **数据源透明**：不同数据源各有优势。MCP 应明确说明这些权衡，而不是假装每个数据源都支持全文检索。

---

## 功能特性

- **双层架构**：
  - **第 1 层（统一工具）**：高层级的 `search_papers` 用于多源并发搜索与去重，`download_with_fallback` 依赖出版商开放获取链接进行顺序回退。
  - **第 2 层（平台连接器）**：针对特定学术平台（arXiv、PubMed、bioRxiv、Semantic Scholar 等）的模块化连接器，配备通过 regex 文本分析或 API 字段进行的智能 DOI 提取。
- **多数据源支持**：支持从 arXiv、PubMed、bioRxiv、medRxiv、Google Scholar、IACR ePrint Archive、Semantic Scholar、Crossref、OpenAlex、PubMed Central（PMC）、CORE、Europe PMC、dblp、OpenAIRE、CiteSeerX、DOAJ、BASE、Zenodo、HAL、SSRN、Unpaywall（DOI 查询）以及可选的 Sci-Hub 工作流搜索和下载论文。
- **标准化输出**：论文通过 `Paper` 类以一致的字典格式返回。
- **免费优先设计**：在任何可选的商业或受限集成之前，优先使用开放和公开的数据源。
- **可选 API-Key 增强**：像 Semantic Scholar 这样的数据源在用户提供 API key 时能更好地工作，但并不强制要求付费使用。
- **发现 + 检索工作流**：Google Scholar 和 Crossref 可用于发现和 DOI 回填，而开放仓库和出版商链接在可用时用于合法的全文解析。
- **OA 优先回退链**：`download_with_fallback` 现在遵循数据源原生下载 → OpenAIRE/CORE/Europe PMC/PMC 发现 → Unpaywall DOI 解析 → 可选 Sci-Hub 的顺序。
- **MCP 集成**：兼容 MCP 客户端，用于增强 LLM 上下文。
- **可扩展设计**：通过扩展 `academic_platforms` 模块即可轻松添加新的学术平台。

## 数据源策略

长期目标不是依赖单一搜索引擎，而是结合多个免费和公开的数据源，各自承担明确角色：

- **开放元数据骨干**：Crossref、OpenAlex、Semantic Scholar、dblp、CiteSeerX、SSRN、Unpaywall（以 DOI 为中心的 OA 元数据）。
- **学科专用数据源**：arXiv、PubMed、PubMed Central、Europe PMC、IACR。
- **开放获取全文数据源**：arXiv、PMC、CORE、OpenAIRE、DOAJ、BASE、Zenodo、HAL、出版商开放获取链接。
- **发现和 DOI 恢复**：当其他公开元数据源不完整时，Google Scholar 可用于查找标题、版本和 DOI 线索。

推荐的免费优先路线图：

1. 保持现有公开数据源稳定。
2. 添加 OpenAlex 作为广泛的免费元数据源。
3. 添加 PubMed Central 和 Europe PMC 以加强生物医学全文访问。
4. 添加 CORE 和 OpenAIRE 用于基于仓库的开放获取检索。
5. 主要将 Google Scholar 作为发现回退手段，而非主要权威数据源。

## 平台能力矩阵

本矩阵反映本仓库中功能和端到端回归测试的**实测集成结果**。各列展示在正常条件下观测到的最高能力级别。

| 平台 | 搜索 | 下载 | 阅读 | 说明 |
|---|---|---|---|---|
| arXiv | ✅ | ✅ | ✅ | 开放 API；可靠 |
| PubMed | ✅ | ❌ | ⚠️ 仅信息 | 开放 API；可靠 |
| bioRxiv | ✅ | ✅ | ✅ | 开放 API；可靠 |
| medRxiv | ✅ | ✅ | ✅ | 开放 API；可靠 |
| Google Scholar | ⚠️ | ❌ | ❌ | 启用反爬检测；设置 `paper_toolkit_mcp_GOOGLE_SCHOLAR_PROXY_URL` |
| IACR | ✅ | ✅ | ✅ | 开放 API；可靠 |
| Semantic Scholar | ✅ | ✅（OA） | ✅（OA） | 无 key 也可用（受限速）；key 提升限额；key 被拒（403）会自动无 key 重试 |
| Crossref | ✅ | ❌ | ⚠️ 仅信息 | 开放 API；可靠 |
| OpenAlex | ✅ | ❌ | ⚠️ 仅信息 | 开放 API；可靠 |
| PMC | ✅ | ✅（仅 OA） | ✅（仅 OA） | 仅 OA PDF；某些代理环境下直接下载可能被阻止 |
| CORE | ✅ | ✅（取决于记录） | ✅（取决于记录） | 推荐使用免费 key；连接器带退避重试，401/403 时回退到无 key 模式 |
| Europe PMC | ✅ | ✅（OA） | ✅（OA） | 仅 OA PDF；某些代理环境下直接下载可能被阻止 |
| dblp | ✅ | ❌ | ⚠️ 仅信息 | 开放 API；可靠 |
| OpenAIRE | ✅ | ❌ | ❌ | 开放 API；瞬时 403 时按 3 次递进请求配置重试 |
| CiteSeerX | ⚠️ | ✅（取决于记录） | ⚠️ | API 端点间歇性不可用 / 重定向到 web 归档 |
| DOAJ | ✅ | ⚠️（取决于 URL） | ⚠️（取决于 URL） | PDF 可用性因文章而异；免费 key 提高速率限额 |
| BASE | ⚠️ | ✅（取决于记录） | ✅（取决于记录） | OAI-PMH 端点需要机构 IP 注册；否则优雅地返回空 |
| Zenodo | ✅ | ✅（取决于记录） | ✅（取决于记录） | 开放 API；可靠 |
| HAL | ✅ | ✅（取决于记录） | ✅（取决于记录） | 开放 API；可靠 |
| SSRN | ⚠️ | ⚠️ 尽力而为 | ⚠️ 尽力而为 | 启用 403 反爬检测；仅公开 PDF |
| Unpaywall | ✅（DOI 查询） | ❌ | ❌ | **需要** `paper_toolkit_mcp_UNPAYWALL_EMAIL` |
| Sci-Hub（可选） | ⚠️ 仅作回退 | ✅ | ❌ | 可选；镜像不稳定；用户自负责任 |
| **IEEE Xplore** 🔑 | 🚧 骨架 | 🚧 骨架 | 🚧 骨架 | 需要 `paper_toolkit_mcp_IEEE_API_KEY` 才能激活 |
| **ACM DL** 🔑 | 🚧 骨架 | 🚧 骨架 | 🚧 骨架 | 需要 `paper_toolkit_mcp_ACM_API_KEY` 才能激活 |

> ✅ = 实测可靠。  ⚠️ = 可用但受上游不稳定或访问限制影响。  ❌ = 不支持。  🔑 = 需要 key。  🚧 = 仅骨架。

---

## 凭证与 API Key 要求

除特别说明外，所有 key 均为**可选**。请在 `.env`（推荐）中配置，或通过 shell 导出。

| 环境变量 | 提供方 | 是否必需？ | 如何获取 |
|---|---|---|---|
| `paper_toolkit_mcp_UNPAYWALL_EMAIL` | Unpaywall | **是**（不设置则禁用 Unpaywall） | 任意有效邮箱；在 [unpaywall.org](https://unpaywall.org/products/api) 注册 |
| `paper_toolkit_mcp_CORE_API_KEY` | CORE | 推荐 | 在 [core.ac.uk/services/api](https://core.ac.uk/services/api) 免费获取 |
| `paper_toolkit_mcp_SEMANTIC_SCHOLAR_API_KEY` | Semantic Scholar | 可选 | 在 [semanticscholar.org](https://www.semanticscholar.org/product/api) 免费获取 —— 提升速率限额 |
| `paper_toolkit_mcp_GOOGLE_SCHOLAR_PROXY_URL` | Google Scholar | 可选 | 你的 HTTP/HTTPS 代理 URL —— 绕过反爬检测 |
| `paper_toolkit_mcp_DOAJ_API_KEY` | DOAJ | 可选 | 在 [doaj.org](https://doaj.org/apply-for-api-key/) 免费获取 —— 提升每小时速率限额 |
| `paper_toolkit_mcp_ZENODO_ACCESS_TOKEN` | Zenodo | 可选 | 在 [zenodo.org](https://zenodo.org/account/settings/applications/) 免费获取 —— 私有记录需要 |
| `paper_toolkit_mcp_IEEE_API_KEY` | IEEE Xplore | **激活必需** | 在 [developer.ieee.org](https://developer.ieee.org/) 免费获取 |
| `paper_toolkit_mcp_ACM_API_KEY` | ACM DL | **激活必需** | 参见 [libraries.acm.org/digital-library/acm-open](https://libraries.acm.org/digital-library/acm-open) |

所有变量遵循 `paper_toolkit_mcp_<NAME>` 前缀方案。不带前缀的旧名称（如 `CORE_API_KEY`、`UNPAYWALL_EMAIL`）仍受支持以保持向后兼容。

---

## 已知的上游限制

部分搜索失败是由外部提供方不稳定导致的，而非本项目的 bug：

| 数据源 | 症状 | 原因 | 解决方法 |
|---|---|---|---|
| Google Scholar | 返回 0 条结果 / 空 HTML | 反爬检测（CAPTCHA） | 将 `paper_toolkit_mcp_GOOGLE_SCHOLAR_PROXY_URL` 设置为代理 |
| Semantic Scholar | 429 限速响应 | 匿名访问限速 | 设置 `paper_toolkit_mcp_SEMANTIC_SCHOLAR_API_KEY`；若 key 被拒（403），连接器会自动无 key 重试 |
| CORE | 500 / 超时错误 | 未认证限速 | 设置 `paper_toolkit_mcp_CORE_API_KEY`（免费）；连接器带指数退避重试，401/403 时回退到无 key 模式 |
| OpenAIRE | 瞬时 403 响应 | 基于 IP 的会话限速 | 连接器按配置重试 3 次，递进升级：普通会话 → XML Accept 头 → 带 Mozilla UA 的原生 `requests.get` |
| CiteSeerX | 经 web 归档重定向 404 | PSU 端点间歇性重定向到归档 | 无解决方法；连接器优雅地返回空 |
| BASE | 搜索返回 0 条结果 | OAI-PMH 端点需要机构 IP 注册 | 在 [base-search.net](https://www.base-search.net/about/en/) 注册获取 API 访问；否则连接器优雅地返回空 |
| SSRN | HTTP 403 | 反爬检测（Cloudflare） | 无解决方法；连接器尝试两个端点，失败时返回清晰信息 |
| PMC / Europe PMC | PDF 下载 ProxyError | 本地代理阻止直接 HTTPS PDF 下载 | 禁用代理或改用 `download_with_fallback` |
| Unpaywall | 完全跳过 | 未设置 `UNPAYWALL_EMAIL` 环境变量 | 在 `.env` 中设置 `paper_toolkit_mcp_UNPAYWALL_EMAIL` |

## 可选付费平台连接器（第 3 阶段）

IEEE Xplore 和 ACM Digital Library 连接器以**可选骨架**形式提供。
它们**默认禁用** —— 除非你显式配置相应的 key，否则不会发起任何 API 调用。

| 平台 | 环境变量 | 状态 |
|---|---|---|
| IEEE Xplore | `paper_toolkit_mcp_IEEE_API_KEY` | 🚧 骨架 —— 已注册搜索，下载/阅读会抛出 `NotImplementedError` |
| ACM Digital Library | `paper_toolkit_mcp_ACM_API_KEY` | 🚧 骨架 —— 已注册搜索，下载/阅读会抛出 `NotImplementedError` |

**如何启用：**

```bash
export paper_toolkit_mcp_IEEE_API_KEY=<your_ieee_key>       # 免费申请：https://developer.ieee.org/
export paper_toolkit_mcp_ACM_API_KEY=<your_acm_key>         # 参见 https://libraries.acm.org/digital-library
```

设置 key 后，对应的数据源会自动添加到 `ALL_SOURCES`，其 MCP 工具（`search_ieee` / `search_acm`、`download_ieee` / `download_acm`、`read_ieee_paper` / `read_acm_paper`）会在服务器启动时注册。

未设置 key 时，连接器仅记录启动警告 —— 服务器的其余部分不受影响。

## 免费数据源扩展（第 4 阶段）

现已将三个额外的免费数据源连接器集成到 MCP 服务器：

- `zenodo`：官方 Zenodo REST API 连接器（搜索 + 取决于记录的 PDF/阅读支持）。
- `hal`：HAL 公共 API 连接器（搜索 + 取决于记录的 PDF/阅读支持）。
- `ssrn`：发现优先的连接器，配备加固的解析器，在存在直接公开 PDF 链接时尽力提供下载/阅读。
- `unpaywall`：以 DOI 为中心的 OA 元数据源，用于独立查询（`search_unpaywall`）和回退 URL 解析。

SSRN 集成仍坚持合规优先：仅尝试 SSRN 页面暴露的直接公开 PDF 链接。若需要登录/受限分发，连接器会返回清晰信息，而非绕过访问控制。

## Sci-Hub 说明

Sci-Hub 支持可作为可选连接器保留给明确选择启用的用户，但不应将其视为默认或推荐的全文路径。

- 可用性不稳定，镜像频繁更换。
- 法律和政策风险因司法管辖区而异。
- README 和工具描述应明确声明用户对启用和使用它负责。
- 应尽可能优先尝试开放获取和出版商许可的数据源。

---

## 安装

选择最适合你工作流的方式。所有方式都支持相同的[可选 API key](#凭证与-api-key-要求)。

---

> **MCP Server 配置文件位置**（适用于以下方式）
> - **macOS**：`~/Library/Application Support/Claude/claude_desktop_config.json`
> - **Windows**：`%APPDATA%\Claude\claude_desktop_config.json`
> - **Linux**：`~/.config/Claude/claude_desktop_config.json`

---

### 从 PyPI 安装（pip）

推荐的安装方式是从 PyPI：

```bash
pip install paper-toolkit-mcp
```

验证是否可用：

```bash
paper-toolkit search "machine learning" -s arxiv,semantic
```

**Claude Desktop / Trae IDE 配置：**

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

> 如果 `python` 不在你的 PATH 中，请替换为完整路径（如 `/usr/bin/python3` 或 `C:\Python311\python.exe`）。运行 `which python3` / `where python` 来查找它。

---

### 从源码安装（开发）

用于开发或自定义，克隆仓库并以可编辑模式安装：

```bash
# 1. 克隆你 fork 的仓库
git clone https://github.com/YOUR_USERNAME/paper-toolkit-mcp.git
cd paper-toolkit-mcp

# 2. 创建虚拟环境并安装
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e ".[dev]"

# 3. 验证是否可用
python -m paper_toolkit_mcp.server
# 或
paper-toolkit search "machine learning" -s arxiv,semantic
```

**Claude Desktop / Trae IDE 配置**（将路径替换为你实际的克隆位置）：

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

从你的项目目录运行，或适当设置 `cwd`，以便 `.env` 文件和 `.paper_cache/` 相对于项目根目录解析。

---

### 环境变量（`.env` 文件）

你可以将 key 存储在项目根目录的 `.env` 文件中（启动时自动加载），而不是直接放在 JSON 配置中：

```bash
cp .env.example .env   # 若从源码运行
# 或创建 ~/.paper-toolkit-mcp.env 供全局使用
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

使用自定义路径：`export paper_toolkit_mcp_ENV_FILE=/absolute/path/to/.env`

> 不带 `paper_toolkit_mcp_` 前缀的旧变量名（如 `CORE_API_KEY`、`UNPAYWALL_EMAIL`）仍受支持以保持向后兼容。

---

## 贡献

欢迎贡献！以下是入门步骤：

1. **Fork 仓库**：
   在 GitHub 上点击 "Fork"。

2. **克隆并配置**：

   ```bash
   git clone https://github.com/yourusername/paper-toolkit-mcp.git
   cd paper-toolkit-mcp
   python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
   pip install -e ".[dev]"
   ```

3. **进行修改**：

   - 在 `academic_platforms/` 中添加新平台。
   - 在 `tests/` 中更新测试。

4. **提交 Pull Request**：
   推送修改并在 GitHub 上创建 PR。

### 测试

```bash
# 离线单元测试（CI 运行，无需网络）—— 含覆盖率门禁（≥20%）
pytest

# 真实抓取集成测试（仅本地，需要网络）
# 验证每个源是否真正获取到摘要与全文。
pytest tests/integration/test_live_fetch.py -m integration --no-cov
```

---

## Demo

<img src="docs/images/demo.png" alt="Demo" width="800">

## TODO

### 计划中的学术平台

- [√] arXiv
- [√] PubMed
- [√] bioRxiv
- [√] medRxiv
- [√] Google Scholar
- [√] IACR ePrint Archive
- [√] Semantic Scholar
- [√] Crossref
- [√] PubMed Central（PMC）
- [√] CORE
- [√] Europe PMC
- [√] Sci-Hub 警告和启用文档

### 开发任务
- [√] 修复异步搜索 bug 并确保可靠的快速 MCP 事件
- [√] 端到端全流程测试脚本（搜索、解析、下载）
- [√] 建立两层联邦架构（第 1 层工具：`search_papers`）
- [√] 确保在元数据字段和摘要回退中全面提取 DOI
- [ ] 引文图谱和论文关系上下文功能
- [√] 扩展全栈 OpenAlex 提供方

### 优先免费和开放数据源

- [√] PubMed Central（PMC）
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
- [√] SSRN（发现 + 尽力全文）
- [√] Unpaywall（独立 DOI 搜索源）

### 可选和非核心集成

- [ ] ResearchGate
- [ ] JSTOR
- [ ] ScienceDirect
- [ ] Springer Link
- [√] IEEE Xplore（可选骨架 —— 用 `IEEE_API_KEY` 激活）
- [√] ACM Digital Library（可选骨架 —— 用 `ACM_API_KEY` 激活）
- [ ] Web of Science
- [ ] Scopus

---

## Star History

[![Star History Chart](https://api.star-history.com/svg?repos=czwziy/paper-toolkit-mcp&type=Date)](https://star-history.com/#czwziy/paper-toolkit-mcp&Date)

---

## License

本项目采用 MIT License 授权。详情请参见 LICENSE 文件。

---

祝使用 `paper-toolkit-mcp` 愉快！如遇问题，请提交 GitHub issue。
