# CLAUDE.md — {PROJECT_NAME} 项目地图

> 本文件是 AI Agent 的知识地图，指引 Agent "去哪里找"信息，而非"百科全书"。

## 项目概述

{PROJECT_DESCRIPTION}

## 知识导航

| 你需要… | 去这里 |
|---------|-------|
| 撰写规范与验证规则 | `.harness/rules.md` |
| 自动化验证脚本 | `.harness/verify.py` |
| 人工审查清单 | `.harness/checklist.md` |
| 可变标准配置（字数、引用数等） | `.harness/specs/manuscript-spec.yaml` |
| Harness 使用指南 | `.harness/Harness.md` |
| 论文正文 | `manuscript/` 目录 |
| 参考文献库 | `papers.db`（SQLite 数据库，由 MCP 工具自动管理） |
| 下载的论文 PDF | `paper_cache/` 目录（由 MCP 工具自动管理） |
| 研究数据 | `data/` 目录 |
| 统计分析脚本 | `scripts/` 目录 |

## 构建与验证

```bash
# 运行 harness 验证（检查文稿是否符合规范）
python .harness/verify.py manuscript/manuscript_v{N}.md

# 带详细输出
python .harness/verify.py manuscript/manuscript_v{N}.md --verbose
```

## 文件结构

```
{PROJECT_NAME}/
├── CLAUDE.md                    # 本文件——项目地图
├── .harness/                    # 约束层——Harness 基础设施
│   ├── rules.md                 # 规则体系（R0-R9）
│   ├── verify.py                # 自动化验证脚本
│   ├── checks/                  # 验证规则实现
│   │   ├── language.py          # R0 语言强制 + R4 语言行文 + R7 AI痕迹
│   │   ├── structure.py         # R1 结构编号 + R8 字数检查
│   │   ├── citations.py         # R5 文献引用
│   │   └── data.py              # R2 数据格式
│   ├── specs/
│   │   └── manuscript-spec.yaml # 可变标准配置
│   ├── checklist.md             # 人工审查清单
│   └── Harness.md               # Harness 使用指南
├── papers.db                    # 参考文献库（SQLite，由 MCP 工具自动管理）
├── paper_cache/                 # 下载的论文 PDF（由 MCP 工具自动管理）
├── manuscript/                  # 文稿层——论文正文（用户创建）
├── data/                        # 数据层——研究数据（用户创建）
└── scripts/                     # 统计层——分析脚本（用户创建）
```

## 硬性规则

> 以下规则由 harness 验证脚本机械化执行，违反即验证失败。

- **全文必须中文撰写**。英文仅限专业术语首次出现时括注。
- **标题必须中文**。英文标题是严重错误。
- **正文禁止列表格式**。使用段落叙述，用分号"；"连接。
- **正文禁止加粗**。加粗仅限结构化摘要标签。
- **引用格式必须为 `[@cite_key]`**。cite_key 由 paper-toolkit 工具自动生成。
- **禁止编造文献**。所有引用必须通过 `search_papers` 或 `get_paper_by_doi` 获取。
- **字数限制**。全文 3000-8000 字，摘要 200-500 字，段落 30-500 字。
- **引用数量**。全文引用 30-45 篇文献。
