# CLAUDE.md — paper-toolkit-mcp

> 本文件是知识地图（指向"去哪找"），不是百科全书。AI 每次会话强制加载。

## 项目概述

paper-toolkit-mcp 是一个 MCP 工具包，用于学术论文搜索、手稿处理与引用生成。技术栈：Python 3.10+ / FastMCP / requests / pypdf / Pandoc。PyPI 包名 `paper-toolkit-mcp`，提供 `paper-toolkit-mcp`（MCP server）与 `paper-toolkit`（CLI）两个入口。

## 知识导航

| 你需要… | 去这里 |
|---------|-------|
| 理解分层架构与依赖方向 | [`.harness/specs/architecture/boundaries.md`](.harness/specs/architecture/boundaries.md) |
| 系统概览（模块/技术栈/数据流） | [`.harness/specs/architecture/overview.md`](.harness/specs/architecture/overview.md) |
| 查找"约定 → 机械化规则"对照表 | [`.harness/constraints/contracts.md`](.harness/constraints/contracts.md) |
| 安全扫描配置 | [`.harness/constraints/security/bandit.yaml`](.harness/constraints/security/bandit.yaml) |
| 架构约束（import-linter）配置 | [`pyproject.toml`](pyproject.toml) 的 `[tool.importlinter]` |
| Lint / 类型 / 测试 / 覆盖率配置 | [`pyproject.toml`](pyproject.toml) 的对应 `[tool.*]` 段 |
| 了解功能设计与范围 | `.trae/specs/<feature>/spec.md` |
| Harness 工程化方法论 | [`harness.md`](harness.md) |

## 构建与验证

```bash
# 一次性安装开发依赖（lint / 类型 / 测试 / 架构 / 安全）
pip install -e ".[dev]"

# 风格检查（ruff）
ruff check paper_toolkit_mcp tests

# 类型检查（mypy）
mypy paper_toolkit_mcp

# 架构检查（import-linter，分层依赖方向）
lint-imports

# 单元测试（CI 默认，hermetic 离线）
pytest

# 覆盖率报告
pytest --cov --cov-report=term-missing

# 集成测试（需网络，手动触发，CI 不跑）
pytest tests/integration/

# 安全扫描（bandit）
bandit -r paper_toolkit_mcp -c .harness/constraints/security/bandit.yaml -q

# 完整验证门（CI 等价命令）
ruff check paper_toolkit_mcp tests \
  && mypy paper_toolkit_mcp \
  && lint-imports \
  && pytest \
  && bandit -r paper_toolkit_mcp -c .harness/constraints/security/bandit.yaml -q
```

## 硬性规则

> 以下规则由约束层代码机械化执行，违反即 CI 红。

- **禁止硬编码 API key**。所有密钥通过 `config.get_env(name)` 读取，配置走 `.env` 文件（gitignored）。参见 [`.env.example`](.env.example)。
- **禁止 `academic_platforms/*` 反向 import `server` 或 `cli`**。分层依赖方向单向，由 `lint-imports` 强制。
- **禁止新增不继承 `PaperSource` 的搜索器**。所有学术源必须实现 `academic_platforms/base.py` 的 `PaperSource` 抽象基类。
- **禁止在 `paper.py`（数据类）中 import 任何上层模块**。`Paper` 是最底层依赖。
- **禁止提交真实 API key / `.env` / `paper_cache/` / `downloads/`**。`.gitignore` 已覆盖。
- **测试拆分**：`tests/unit/` 必须离线 hermetic（mock 所有外部 IO）；任何在 import 或 setUp 阶段触网、或断言真实 API 响应的测试放 `tests/integration/`。CI 只跑 `tests/unit/`。
- **不可逆操作**：不允许 `git push --force` 到 main/master；不允许删除 `csl/` 内置引用样式文件。

## 棕地陷阱（不要复制旧模式）

- `server.py` 与 `cli.py` 集中实例化所有 searcher — 新增 searcher 时**两处都要注册**，否则 MCP 工具与 CLI 命令会不一致。
- 原 `tests/test.pubmed.py` 已重命名为 `tests/integration/test_pubmed.py` — pytest 不自动发现点号命名的文件，新增测试文件必须用 `test_*.py` 命名。
- 原 `tests/test_server.py` 已拆分：离线部分在 `tests/unit/test_server_sources.py`，网络部分在 `tests/integration/test_server.py`。
- `tests/integration/*` 中多个测试在 `setUpClass` 调用真实 API 探测可达性（如 `check_semantic_accessible`）——这类**不能放 `tests/unit/`**，否则 CI 在 import 阶段就触网。
