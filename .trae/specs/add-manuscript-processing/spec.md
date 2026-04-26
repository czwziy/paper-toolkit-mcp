# 论文手稿处理功能规格

## Why

当前 paper-toolkit-mcp 工具已支持 20+ 学术平台搜索和 PDF 下载，但存在以下不足：
1. 搜索元数据无本地缓存，重复查询浪费 API 配额
2. 无法将 Markdown 中的引用占位符自动替换为格式化参考文献
3. 无法一键生成投稿版 Word 文档

本功能旨在实现"写作→引用→生成投稿版"的完整自动化工作流，最小化用户手动操作。

## What Changes

- **新增** `cache.py` - JSON 格式搜索缓存模块，按查询+来源缓存，支持 TTL 过期
- **新增** `reference.py` - 占位符解析 + BibTeX/RIS 生成 + GB/T 7714-2015 格式化
- **新增** `pandoc_helper.py` - Pandoc 调用封装，支持 Markdown → Word 转换
- **新增** `chinese-gb7714-2015-numeric.csl` - 内置 GB/T 7714-2015 CSL 文件
- **新增** `apa-7th-edition.csl` - 内置 APA 7th Edition CSL 文件
- **新增** `ieee.csl` - 内置 IEEE CSL 文件
- **新增** `vancouver.csl` - 内置 Vancouver CSL 文件
- **新增** `harvard.csl` - 内置 Harvard CSL 文件
- **修改** `academic_platforms/base.py` - 基类集成缓存逻辑，所有 Searcher 自动使用
- **修改** `server.py` - 新增 MCP 工具：`process_manuscript`、`get_paper_metadata`、`export_references`
- **修改** `cli.py` - CLI 支持手稿处理命令

## Impact

- **影响模块**：搜索层、引用处理层、MCP 工具层、CLI 层
- **向后兼容**：✅ 完全兼容，不破坏现有 API
- **新增依赖**：`pandoc` (需系统安装)、`pypandoc` (Python 包)

## ADDED Requirements

### Requirement: 搜索缓存
系统应当将搜索结果缓存为 JSON 文件，按查询词和来源命名，支持 TTL 过期机制。

#### Scenario: 缓存命中
- **WHEN** 用户搜索相同关键词且缓存未过期
- **THEN** 直接返回缓存结果，不请求 API

#### Scenario: 缓存过期
- **WHEN** 缓存文件存在但超过 TTL
- **THEN** 重新请求 API 并更新缓存

#### Scenario: 缓存文件位置
- **WHEN** 系统运行
- **THEN** 缓存保存在当前工作目录的 `./paper_cache/` 下

### Requirement: 占位符解析
系统应当支持以下占位符格式并提取标识符：
- `[@doi:10.1234/example]`
- `[@pmid:12345678]`
- `[@arxiv:2106.12345]`
- `[@title:Paper Title]`

#### Scenario: 解析成功
- **WHEN** 输入包含占位符的 Markdown 文本
- **THEN** 提取所有占位符，去重后获取文献元数据

#### Scenario: 解析失败
- **WHEN** 占位符标识符无效或 API 失败
- **THEN** 保留原文并返回错误信息，不中断处理

### Requirement: 参考文献导出
系统应当支持导出 BibTeX (.bib) 和 RIS (.ris) 格式。

#### Scenario: 导出 BibTeX
- **WHEN** 用户请求导出参考文献
- **THEN** 生成标准 BibTeX 格式，包含 title、author、year、doi 等字段

#### Scenario: 导出 RIS
- **WHEN** 用户请求导出参考文献
- **THEN** 生成标准 RIS 格式，可导入 Zotero/EndNote

### Requirement: GB/T 7714-2015 格式化
系统应当支持多种主流引用格式，包括但不限于：
- GB/T 7714-2015（中国国标）
- APA 7th Edition
- IEEE
- Vancouver
- Harvard

#### Scenario: 期刊论文（GB/T 7714）
- **WHEN** 格式化期刊文献
- **THEN** 输出：作者. 标题[文献类型标识]. 期刊名, 年, 卷(期): 页码. DOI.

#### Scenario: 会议论文（APA）
- **WHEN** 格式化会议文献为 APA 格式
- **THEN** 输出：Author, A. A. (Year). Title of paper. In *Proceedings* (pp. xx-xx). Publisher.

### Requirement: 手稿处理工具
系统应当提供一键处理手稿的 MCP 工具。

#### Scenario: 处理手稿
- **WHEN** 用户调用 `process_manuscript` 并传入 Markdown 文件路径
- **THEN** 输出格式化后的 Markdown、BibTeX、RIS、Word 文档及处理报告

#### Scenario: Pandoc 未安装
- **WHEN** 系统未安装 pandoc
- **THEN** 跳过 Word 生成，返回其他格式并提示安装 pandoc

#### Scenario: 部分文献无法识别
- **WHEN** 某些占位符对应的文献无法获取元数据
- **THEN** 在报告中标明失败的占位符及原因，保留原文中的占位符

### Requirement: 处理报告
系统应当在手稿处理后生成处理报告，包含成功/失败统计。

#### Scenario: 成功处理
- **WHEN** 所有占位符都成功获取元数据
- **THEN** 报告显示：成功数量、使用的引用格式、输出文件路径

#### Scenario: 部分失败
- **WHEN** 部分占位符无法获取元数据（DOI 无效、API 失败等）
- **THEN** 报告显示：
  - 成功获取的文献列表
  - 失败的占位符及失败原因
  - 建议操作（如手动检查 DOI 是否正确）

### Requirement: 元数据查询工具
系统应当提供单篇文献元数据查询工具。

#### Scenario: 查询文献
- **WHEN** 用户提供 DOI/PMID/arXiv ID
- **THEN** 返回完整元数据（查缓存或调 API）

## MODIFIED Requirements

### Requirement: PaperSource 基类搜索方法
所有继承 PaperSource 的 Searcher 类，其 `search()` 方法应当自动使用缓存。

**修改前**：
```python
def search(self, query, **kwargs) -> List[Paper]:
    # 直接请求 API
```

**修改后**：
```python
def search(self, query, **kwargs) -> List[Paper]:
    # 先查缓存，未命中则请求 API 并缓存
```

### Requirement: CLI 新增命令
CLI 应当支持新的手稿处理命令。

**新增命令**：
- `paper-toolkit manuscript draft.md` - 处理手稿
- `paper-toolkit cache list` - 列出缓存
- `paper-toolkit cache clear` - 清除缓存
