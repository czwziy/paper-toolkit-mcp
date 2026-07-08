# Paper Search MCP - 学术论文检索工具

一个基于 MCP（Model Context Protocol）的学术论文搜索和下载工具，支持 20+ 学术平台。本项目采用"免费优先"策略：优先使用开放和公共数据源，支持可选的 API 密钥以提升稳定性和覆盖范围。

**v0.2.0 新功能**：支持手稿引用占位符处理、搜索缓存、BibTeX/RIS 导出、一键生成 Word 文档。

![PyPI](https://img.shields.io/pypi/v/paper-toolkit-mcp.svg) ![License](https://img.shields.io/badge/license-MIT-blue.svg) ![Python](https://img.shields.io/badge/python-3.10+-blue.svg)

---

## 快速导航

- [v0.2.0 新功能](#v020-新功能)
- [项目简介](#项目简介)
- [功能特性](#功能特性)
- [支持的学术平台](#支持的学术平台)
- [本地部署](#本地部署)
- [手稿处理功能](#手稿处理功能)
- [搜索缓存](#搜索缓存)
- [CLI 命令行使用](#cli-命令行使用)
- [参与贡献](#参与贡献)
- [Star 趋势](#star-趋势)
- [许可证](#许可证)

---

## v0.2.0 新功能

### 手稿处理

在 Markdown 中用引用占位符写论文，一键生成格式化的 Word 文档和参考文献：

```markdown
# 引言
深度学习在医疗影像领域取得了重大进展[@doi:10.1038/s41591-020-0001-2]。
Transformer 架构彻底改变了 NLP 领域[@title:Attention Is All You Need]。
```

处理它：
```bash
paper-toolkit manuscript draft.md -s gb7714 --docx
```

输出：
- `draft_formatted.md` - 带编号引用的 Markdown [1], [2], ...
- `refs.bib` - BibTeX 文件（可导入 Zotero/EndNote）
- `refs.ris` - RIS 文件（Zotero 兼容）
- `draft_final.docx` - 格式化的 Word 文档

支持的占位符：`[@doi:...]`、`[@pmid:...]`、`[@arxiv:...]`、`[@title:...]`

支持的引用格式：GB/T 7714-2015、APA 7th、IEEE、Vancouver、Harvard

### 搜索缓存

搜索结果自动缓存在 `.paper_cache/`（相对于当前工作目录）：
- **跟随工作文件夹**：缓存保存在你工作的文件夹内
- **可移植**：复制项目文件夹时缓存一起迁移
- **易管理**：用户可手动删除 `.paper_cache/` 清理缓存

---

## 项目简介

`paper-toolkit-mcp` 是一个基于 Python 的学术论文搜索和下载工具。它支持搜索论文、下载 PDF 和提取文本，非常适合研究人员和 AI 驱动的工作流。可作为 MCP 服务器（Claude Desktop、Trae IDE 等）或命令行工具使用。

## 项目原则

- **免费优先**：公共和开放源作为默认路线图，付费或受限源不是核心方向
- **可选 API 密钥**：仅在提升稳定性、速率限制或元数据质量时支持 API 密钥
- **LLM 友好**：搜索结果标准化、去重、尽可能完整
- **来源透明**：不同来源有不同优势，明确权衡而非假装每个源都支持全文

---

## 功能特性

- **双层架构**：
  - **第一层（统一工具）**：`search_papers` 多源并发搜索和去重，`download_with_fallback` 开放获取链接回退下载
  - **第二层（平台连接器）**：arXiv、PubMed、Semantic Scholar 等模块化连接器
- **多源支持**：20+ 学术平台（详见下方矩阵）
- **标准化输出**：通过 `Paper` 类返回一致的字典格式
- **MCP 集成**：兼容 MCP 客户端，支持 LLM 上下文增强
- **可扩展设计**：通过扩展 `academic_platforms` 模块轻松添加新平台

---

## 支持的学术平台

| 平台 | 搜索 | 下载 | 读取 | 说明 |
|------|------|------|------|------|
| arXiv | ✅ | ✅ | ✅ | 开放 API，稳定 |
| PubMed | ✅ | ❌ | ⚠️ 仅元数据 | 开放 API，稳定 |
| bioRxiv | ✅ | ✅ | ✅ | 开放 API，稳定 |
| medRxiv | ✅ | ✅ | ✅ | 开放 API，稳定 |
| Google Scholar | ⚠️ | ❌ | ❌ | 有反爬检测 |
| Semantic Scholar | ✅ | ✅ (OA) | ✅ (OA) | 无需密钥（限流），有密钥提升限制 |
| Crossref | ✅ | ❌ | ⚠️ 仅元数据 | 开放 API，稳定 |
| OpenAlex | ✅ | ❌ | ⚠️ 仅元数据 | 开放 API，稳定 |
| CORE | ✅ | ✅ | ✅ | 免费密钥推荐 |
| Europe PMC | ✅ | ✅ (OA) | ✅ (OA) | OA PDF 可用 |
| Zenodo | ✅ | ✅ | ✅ | 开放 API，稳定 |
| HAL | ✅ | ✅ | ✅ | 开放 API，稳定 |
| dblp | ✅ | ❌ | ⚠️ 仅元数据 | 开放 API，稳定 |
| IACR | ✅ | ✅ | ✅ | 开放 API，稳定 |
| Unpaywall | ✅ (DOI) | ❌ | ❌ | **需要** `paper_toolkit_mcp_UNPAYWALL_EMAIL` |

> ✅ = 稳定 | ⚠️ = 可用但有波动 | ❌ = 不支持

---

## 本地部署

### 推荐方式：pip 安装

```bash
# 从 PyPI 安装
pip install paper-toolkit-mcp

# 验证运行
paper-toolkit search "machine learning" -s arxiv,semantic
```

### 从源码安装（开发模式）

```bash
# 1. 克隆仓库
git clone https://github.com/YOUR_USERNAME/paper-toolkit-mcp.git
cd paper-toolkit-mcp

# 2. 创建虚拟环境并安装
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e ".[dev]"

# 3. 验证运行
python -m paper_toolkit_mcp.server
# 或者
paper-toolkit search "machine learning" -s arxiv,semantic
```

### Trae IDE / Claude Desktop 配置

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

> 若 `python` 不在 PATH 中，替换为完整路径（如 `/usr/bin/python3` 或 `C:\Python311\python.exe`）。

**配置文件位置**：
- **Windows**: `%APPDATA%\Claude\claude_desktop_config.json`
- **macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`
- **Linux**: `~/.config/Claude/claude_desktop_config.json`

---

## 手稿处理功能

### 工作流程

1. **写作** - 用 Markdown 写论文，用占位符标记引用
2. **处理** - 运行 `paper-toolkit manuscript` 命令
3. **导入** - 将 `refs.ris` 导入 Zotero（可选）
4. **提交** - 使用生成的 `draft_final.docx`

### 支持的占位符

```markdown
[@doi:10.1038/s41591-020-0001-2]     # DOI
[@pmid:32145678]                      # PubMed ID
[@arxiv:2106.12345]                   # arXiv ID
[@title:Attention Is All You Need]   # 论文标题
```

### 使用方法

```bash
# 基础用法（生成格式化 Markdown + BibTeX + RIS）
paper-toolkit manuscript draft.md

# 生成 Word 文档（需要安装 pandoc）
paper-toolkit manuscript draft.md --docx

# 指定引用格式
paper-toolkit manuscript draft.md -s gb7714   # GB/T 7714-2015
paper-toolkit manuscript draft.md -s apa      # APA 7th
paper-toolkit manuscript draft.md -s ieee     # IEEE

# 自定义输出目录
paper-toolkit manuscript draft.md -o ./output
```

### 支持的引用格式

| 格式 | 代码 | 说明 |
|------|------|------|
| GB/T 7714-2015 | `gb7714` | 中国国家标准（顺序编码制） |
| APA 7th | `apa` | 美国心理学会格式 |
| IEEE | `ieee` | 电气电子工程师学会格式 |
| Vancouver | `vancouver` | 国际医学期刊编辑委员会格式 |
| Harvard | `harvard` | 哈佛格式（著者-出版年制） |

### 输出文件

| 文件 | 说明 |
|------|------|
| `draft_formatted.md` | 带编号引用的 Markdown |
| `draft_final.docx` | Word 文档（需 pandoc） |
| `refs.bib` | BibTeX 文件（Zotero/JabRef 兼容） |
| `refs.ris` | RIS 文件（Zotero/EndNote/Mendeley 兼容） |
| `draft_references.txt` | 纯文本参考文献列表 |

---

## 搜索缓存

### 工作机制

- 搜索结果以 JSON 格式缓存在 `.paper_cache/`
- 缓存位置**相对于当前工作目录**
- 跟随项目文件夹 — 复制文件夹，缓存一起迁移
- 默认 TTL（生存时间）为 24 小时

### 缓存位置示例

```
your_project/
├── draft.md
├── refs.bib
└── .paper_cache/          ← 缓存在这里
    ├── abc123.json        ← 缓存的搜索结果
    └── def456.json
```

### 缓存管理

```bash
# 列出缓存项
paper-toolkit cache list

# 清除所有缓存
paper-toolkit cache clear
```

或通过 MCP 工具：`cache_list()`、`cache_clear()`

---

## CLI 命令行使用

```bash
# 搜索论文
paper-toolkit search "machine learning" -s arxiv,semantic -n 10

# 下载 PDF
paper-toolkit download arxiv 2106.12345

# 读取论文（提取文本）
paper-toolkit read arxiv 2106.12345

# 处理手稿
paper-toolkit manuscript draft.md -s gb7714 --docx

# 缓存管理
paper-toolkit cache list
paper-toolkit cache clear

# 列出可用来源
paper-toolkit sources
```

---

## API 密钥配置

所有密钥**可选**（除非特别注明）。在 `.env` 文件中配置：

```bash
cp .env.example .env
```

```dotenv
paper_toolkit_mcp_UNPAYWALL_EMAIL=your@email.com     # Unpaywall 需要
paper_toolkit_mcp_CORE_API_KEY=                      # CORE 推荐
paper_toolkit_mcp_SEMANTIC_SCHOLAR_API_KEY=          # 提升速率限制
paper_toolkit_mcp_IEEE_API_KEY=                      # 启用 IEEE Xplore
```

---

## 参与贡献

欢迎贡献！入门指南：

1. **Fork 仓库** - 在 GitHub 上点击 "Fork"
2. **克隆并设置**：
   ```bash
   git clone https://github.com/yourusername/paper-toolkit-mcp.git
   cd paper-toolkit-mcp
   python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
   pip install -e ".[dev]"
   ```
3. **进行修改**：
   - 在 `academic_platforms/` 中添加新平台
   - 在 `tests/` 中更新测试
4. **提交 Pull Request** - 推送更改并在 GitHub 上创建 PR

---

## Star 趋势

[![Star History Chart](https://api.star-history.com/svg?repos=openags/paper-toolkit-mcp&type=Date)](https://star-history.com/#openags/paper-toolkit-mcp&Date)

---

## 许可证

本项目采用 MIT 许可证。详见 LICENSE 文件。

---

使用 `paper-toolkit-mcp` 愉快地做研究吧！如遇问题，请在 GitHub 上提 issue。
