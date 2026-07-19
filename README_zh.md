[English](README.md) | **中文**

# Paper Toolkit MCP

> 一个用于学术论文检索、稿件处理和引用管理的综合 MCP 工具集。

![PyPI](https://img.shields.io/pypi/v/paper-toolkit-mcp.svg) ![License](https://img.shields.io/badge/license-MIT-blue.svg) ![Python](https://img.shields.io/badge/python-3.10+-blue.svg)

---

## 功能特性

### 论文检索与下载
- 多源检索：arXiv、Semantic Scholar、PubMed、Crossref、OpenAlex、PMC、medRxiv、DBLP、Europe PMC、OpenAIRE、SSRN、IEEE、ACM
- PDF 下载与自动兜底（Unpaywall → OA 仓库 → Sci-Hub）
- PDF 全文提取

### 文献管理
- SQLite 本地文献库
- BibTeX/RIS 导出
- 自动生成 cite_key
- 作者姓名自动标准化（Surname, Given 格式）

### 文稿处理
- Markdown 文稿引用替换与参考文献列表生成
- 人工核对版生成（cite_key → 作者(年份) DOI）
- 多引用格式：GB/T 7714-2015、APA 7th、IEEE
- 写作模板

### 文稿 Harness
- 30 条自动验证规则（R0-R9），支持 local/global scope
- 中文语言强制
- 引用格式验证
- 字数检查
- 撰写/定稿模式切换（chapter/draft/final）

### 引用验证
- 多模型 LLM 评分验证引用准确性
- 增量缓存，避免重复验证
- 单句验证与全文批量验证

---

## 快速开始

### 安装

```bash
pip install paper-toolkit-mcp
```

### MCP 配置

添加到 MCP 客户端配置：

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

> **注意**：设置 `paper_toolkit_mcp_WORK_DIR` 为你的项目目录，这样 `papers.db`、下载文件和缓存都会存储在该项目目录下。

### API Key（可选）

所有数据源无需 API key 即可使用。可选 key 可提升速率限制：

```bash
# 复制示例文件并填入可用的 key
cp .env.example .env
```

详见 `.env.example`。

---

## MCP 工具

### 检索与下载

| 工具 | 说明 |
|------|------|
| `search_papers` | 多源检索论文（支持分组：medical/cs/metadata） |
| `get_paper_by_doi` | 根据 DOI 获取元数据（CrossRef + Semantic Scholar 兜底） |
| `download_paper` | 下载 PDF（源原生 → OA 仓库 → Unpaywall → Sci-Hub） |
| `download_by_cite_key` | 根据 cite_key 下载 |
| `read_by_cite_key` | 下载并提取 PDF 文本 |

### 文献库管理

| 工具 | 说明 |
|------|------|
| `library_search` | 检索本地文献库 |
| `library_stats` | 文献库统计 |
| `cache_clear` | 清除检索缓存 |

### 文稿处理

| 工具 | 说明 |
|------|------|
| `process_manuscript` | 处理 Markdown 文稿，替换引用占位符并生成输出 |
| `get_paper_metadata` | 获取单篇论文完整元数据 |
| `export_references` | 批量导出参考文献（BibTeX/RIS/文本） |
| `get_writing_template` | 获取写作模板 |
| `generate_ref_list` | 从文稿 cite_key 生成参考文献列表 |
| `generate_human_review` | 生成人工核对版（cite_key → 作者(年份) DOI） |

### 文稿 Harness

| 工具 | 说明 |
|------|------|
| `harness_init` | 初始化 Harness 基础设施 |
| `harness_verify` | 验证文稿规范 |
| `harness_list_rules` | 列出所有规则（含 scope 和 draft_skip 标记） |

### 引用验证

| 工具 | 说明 |
|------|------|
| `verify_citation` | 验证单条引用（多模型 LLM 评分） |
| `verify_manuscript` | 批量验证文稿中所有引用 |
| `verify_config` | 检查验证器配置与模型连通性 |

---

## Harness 规则

| 规则 | 类别 | Scope | 说明 |
|------|------|-------|------|
| R0 | 语言 | local | 全文中文、标题中文 |
| R1 | 结构 | local | 标题层级、标题长度、禁止列表/加粗 |
| R2 | 数据 | local/global | P值、均值±标准差、统计量、数据一致性 |
| R3 | 章节 | global | 必备章节（引言/方法/结果/讨论/结论） |
| R4 | 术语 | local | 缩写一致性、行文谦逊 |
| R5 | 引用 | local/global | cite_key 格式、引用密度、文献总量 |
| R6 | 位置 | local | 引用标记位置、多文献同引格式 |
| R7 | AI痕迹 | local | 标题冒号、禁止自我夸大/回引、用户意见 |
| R8 | 字数 | local/global | 全文 3000-8000 字、段落字数、摘要字数 |
| R9 | 表图 | local/global | 三线表、300dpi、图片编号 |

> **Scope 说明**：`local` 规则可由子代理独立检查单章节；`global` 规则需全文合并后检查。撰写模式（draft）下，摘要字数（R8.3）和文献总量（R5.4）自动跳过。

---

## 开发

```bash
# 安装开发依赖
pip install -e ".[dev]"

# 运行测试
pytest

# 代码检查
ruff check paper_toolkit_mcp tests

# 类型检查
mypy paper_toolkit_mcp
```

---

## 许可证

MIT

---

## 链接

- [GitHub](https://github.com/czwziy/paper-toolkit-mcp)
- [PyPI](https://pypi.org/project/paper-toolkit-mcp/)
- [发布指南](docs/publishing.md)
