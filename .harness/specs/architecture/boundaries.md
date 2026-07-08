# 分层架构

## 设计意图

paper-toolkit-mcp 采用三层分离，核心目的是：

1. **`server.py` / `cli.py`** 作为入口编排点 — 注册 MCP 工具、CLI 命令，但不承载解析/搜索逻辑
2. **`academic_platforms/`** 作为外部学术平台的适配层 — 每个搜索器封装一个平台的 HTTP/解析细节
3. **叶子模块**（`paper.py`、`reference.py`、`cache.py` 等）作为无内部依赖的工具/数据层 — 可被任意上层调用，自身不依赖上层

这种分离让搜索器可以独立测试、叶子模块可以纯函数化推理、入口层可以独立演化（MCP 协议变更不影响搜索器）。

## 依赖方向

```
server, cli  →  academic_platforms  →  paper / reference / cache / utils / config / pandoc_helper
   (入口)            (适配层)                         (叶子 / 数据 / 工具)
```

所有箭头**单向向下**，禁止反向依赖：
- `academic_platforms/*` 不得 import `server` 或 `cli`
- 叶子模块（如 `paper.py`）不得 import 任何上层模块
- `server` 与 `cli` 互不依赖（两者都是入口，平行存在）

## 各层职责

### 入口层（`server.py`, `cli.py`）
- `server.py`：注册 FastMCP 工具（`search_arxiv`、`download_pdf`、`process_manuscript` 等），实例化所有 searcher 并分发请求
- `cli.py`：argparse 命令行入口，复用同一批 searcher 实例
- **新增 searcher 时两处都要注册**，否则 MCP 工具与 CLI 命令会不一致（棕地陷阱）

### 适配层（`academic_platforms/`）
- 每个 `*Searcher` 必须继承 `base.PaperSource`，实现 `search()` 抽象方法
- `base_search.py` 通过 `oaipmh.py` 复用 OAI-PMH 协议（多个仓储共用）
- 适配层可以 import 叶子层（`paper`, `utils`, `config`），但**不能反向 import 入口层**

### 叶子层（`paper`, `reference`, `cache`, `utils`, `config`, `pandoc_helper`）
- `paper.py`：`Paper` dataclass — 唯一的数据载体，无任何内部依赖
- `reference.py`：引用占位符解析 + BibTeX/RIS 生成 + CSL 格式化
- `cache.py`：JSON 搜索缓存，按 `query + source` 维度缓存。**无任何内部依赖**（默认缓存目录回退 CWD；需要 `<WORK_DIR>/.paper_cache` 时由入口层调用方显式传入 `cache_dir`）
- `utils.py`：DOI 提取等纯函数工具
- `config.py`：环境变量加载（`paper_toolkit_mcp_*` 前缀，向后兼容无前缀旧名）
- `pandoc_helper.py`：Pandoc 子进程封装（Markdown → Word）

> **叶子层独立性**：叶子模块之间用 `|` 在 import-linter 契约中标记为"独立"（互不依赖）。
> `cache` 需要 WORK_DIR 时，不直接 import `config`，而是由入口层（`server`/`cli`）
> 调用 `config.get_work_dir()` 后作为 `cache_dir` 参数注入。依赖注入而非直接依赖，
> 让 `cache` 保持可独立测试、纯函数化的叶子性质。

## 具体规则

由约束层代码强制执行，参见：

- 分层依赖方向 → `pyproject.toml` 的 `[tool.importlinter]` contract
- 安全规则 → `.harness/constraints/security/bandit.yaml`
- 风格/复杂度 → `pyproject.toml` 的 `[tool.ruff]`
- 类型安全 → `pyproject.toml` 的 `[tool.mypy]`
- 完整"约定 → 机械化规则"对照表 → `.harness/constraints/contracts.md`

## 关键设计决策

| 决策 | 原因 |
|------|------|
| `server.py` 与 `cli.py` 平行而非 cli 调 server | MCP 协议层与 CLI 层是不同消费者，平行避免循环耦合 |
| 所有 searcher 继承 `PaperSource` | 统一 `search()` 契约，缓存逻辑在基类中自动复用 |
| `Paper` 是最底层依赖 | 数据结构稳定，所有层都可依赖；自身不依赖任何上层避免循环 |
| 配置走 `config.get_env()` 而非直接读 `os.environ` | 统一前缀处理 + `.env` 文件加载 + 旧名向后兼容 |
| `cache` 通过参数注入 `cache_dir` 而非 import `config` | 叶子层模块互不依赖（import-linter 同层 `|` = 独立）；WORK_DIR 由入口层解析后注入，`cache` 保持纯叶子可独立测试 |
