[English](README.md) | **中文**

# Paper Toolkit MCP

> 一个用于学术论文检索、稿件处理和引用管理的综合 MCP 工具集。

![PyPI](https://img.shields.io/pypi/v/paper-toolkit-mcp.svg) ![License](https://img.shields.io/badge/license-MIT-blue.svg) ![Python](https://img.shields.io/badge/python-3.10+-blue.svg)

---

## 功能特性

### 论文检索与下载
- 多源检索：arXiv、Semantic Scholar、PubMed、Crossref、OpenAlex
- PDF 下载与自动兜底
- PDF 全文提取

### 文献管理
- SQLite 本地文献库
- BibTeX/RIS 导出
- 自动生成 cite_key

### 文稿 Harness（v0.3.0）
- 27 条自动验证规则（R0-R9）
- 中文语言强制
- 引用格式验证
- 字数检查

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
      "command": "paper-toolkit-mcp"
    }
  }
}
```

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
| `search_papers` | 多源检索论文 |
| `get_paper_by_doi` | 根据 DOI 获取元数据 |
| `download_paper` | 下载 PDF |
| `download_by_cite_key` | 根据 cite_key 下载 |
| `read_by_cite_key` | 阅读 PDF 文本 |

### 文献库管理

| 工具 | 说明 |
|------|------|
| `library_search` | 检索本地文献库 |
| `library_stats` | 文献库统计 |
| `cache_clear` | 清除检索缓存 |

### 文稿 Harness

| 工具 | 说明 |
|------|------|
| `harness_init` | 初始化 Harness 基础设施 |
| `harness_verify` | 验证文稿规范 |
| `harness_list_rules` | 列出所有规则 |

---

## Harness 规则

| 规则 | 类别 | 说明 |
|------|------|------|
| R0 | 语言 | 全文中文、标题中文 |
| R1 | 结构 | 标题层级、禁止列表/加粗 |
| R2 | 数据 | P值、均值±标准差、统计量 |
| R3 | 章节 | 必备章节（引言/方法/结果/讨论/结论） |
| R4 | 术语 | 缩写一致性 |
| R5 | 引用 | cite_key 格式、引用密度 |
| R6 | 位置 | 引用标记位置 |
| R7 | AI痕迹 | 禁止自我夸大/回引 |
| R8 | 字数 | 全文 3000-8000 字 |
| R9 | 表图 | 三线表、300dpi |

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
