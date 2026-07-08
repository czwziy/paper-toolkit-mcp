# 口头约定 → 机械化规则 对照表

> 每条约定必须映射到一个可执行工具。没有执行工具的约定不是约定，是愿望。
> 参见 `harness.md` 第九章 9.2 节。

## 对照表

| 约定 | 执行工具 | 配置位置 | 违规时 |
|------|---------|---------|--------|
| 行长 ≤ 120 | ruff `line-length` | `pyproject.toml [tool.ruff]` | ruff check 报错 |
| import 顺序规范 | ruff `I` (isort) | `pyproject.toml [tool.ruff.lint]` | ruff check 报错（可 `--fix`） |
| 旧语法升级（pyupgrade） | ruff `UP` | `pyproject.toml [tool.ruff.lint]` | ruff check 报错 |
| 常见 bug 模式 | ruff `B` (bugbear) | `pyproject.toml [tool.ruff.lint]` | ruff check 报错 |
| 分层依赖方向单向 | import-linter `layers` contract | `pyproject.toml [tool.importlinter]` | `lint-imports` 报错 |
| 入口层不互相依赖 | import-linter（同层不可互引） | 同上 | `lint-imports` 报错 |
| 函数返回值类型一致 | mypy `warn_return_any` | `pyproject.toml [tool.mypy]` | mypy 报错 |
| 隐式 Optional 禁用 | mypy `no_implicit_optional` | 同上 | mypy 报错 |
| 单元测试必须离线 hermetic | pytest `testpaths=["tests/unit"]` | `pyproject.toml [tool.pytest]` | CI 不收集 integration 测试 |
| 覆盖率 ≥ 50% | coverage `fail_under=50` | `pyproject.toml [tool.coverage.report]` | pytest --cov 退出码非 0 |
| 安全扫描（无硬编码密钥/弱密码） | bandit | `.harness/constraints/security/bandit.yaml` | bandit 退出码非 0 |
| 文件 ≤ 400 行 | CI 脚本 `find + wc + awk` | `.github/workflows/ci.yml` | CI job 失败 |
| 设计文档不腐化（≤60 天） | CI git log 检查 | `.github/workflows/ci.yml` | CI warning（不阻断） |
| 不可硬编码 API key | 人工审查 + bandit `S` 规则 | 代码审查 + `.harness/constraints/security/bandit.yaml` | bandit 报告 |
| 不可 force push 主分支 | 人工审查 + 分支保护 | GitHub 仓库设置 | git push 被拒 |

## 待机械化（暂未实现）

| 约定 | 计划工具 | 状态 |
|------|---------|------|
| 所有 searcher 必须继承 `PaperSource` | 自定义 import-linter contract 或单元测试 | TODO |
| `server.py` 与 `cli.py` 的 searcher 注册必须同步 | 单元测试断言两者集合相等 | TODO |
| `Paper` dataclass 不得 import 上层 | import-linter `forbidden` contract | 已由 `layers` contract 覆盖 |

## 渐进收紧计划

当前为**初始门禁**，规则相对宽松以让现有代码通过 CI。后续逐步收紧：

1. **当前**：ruff `E/W/F/I/UP/B`、mypy `check_untyped_defs`、coverage 50%
2. **下一阶段**：ruff 加 `S`（bandit 子集）/`C90`（复杂度）/`N`（命名）、mypy `disallow_untyped_defs=true`、coverage 70%
3. **目标**：mypy `strict=true`、coverage 80%、文件 ≤ 300 行

每一步收紧前，需先让现有代码合规（auto-fix 或人工修复），再修改阈值。
