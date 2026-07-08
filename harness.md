# Harness Engineering 通用开发指南

> **从 AI 辅助编码到 AI 工程化：如何为你的团队和技术栈构建一套保证 AI 正确编写代码的 Harness 体系**
>
> 本指南综合了两个范例项目的经验：
> - **Schedulr Harness**（Python/TS 棕地项目）—— Claude Code 原语级 Harness：Hooks + Skills + MCP + Ralph
> - **Taskapp Harness**（Java/Spring 企业级项目）—— 构建系统级 Harness：ArchUnit + Checkstyle + CI + 多代理适配

---

## 第一章：Harness Engineering 是什么

### 1.1 问题

你有一个编码代理（Claude、Copilot、Cursor、Codex……），它很聪明，但它：

- **不知道你的规则**——你的命名规范、你的架构约定、你的安全红线
- **不会自我验证**——它说"我做完了"，但代码跑不过测试、没过 lint、甚至有安全漏洞
- **没有纪律**——它会跳步、偷懒、走捷径，把"看起来能工作"当成"真的能工作"
- **没有记忆**——每次对话从零开始，上一轮犯过的错下一轮照犯
- **不知道边界**——它会自己发明需求，把"范围外"的东西也做了

### 1.2 定义

> **Harness Engineering = 构建包装编码代理的上下文和工作流——它运行的生态系统——让它像你团队中的工程师一样工作，而不是一个聪明的陌生人在猜测你的代码库。**

Harness 不是框架，不是库，不是产品。它是**你围绕 AI 代理构建的工程系统**，由五个层次组成：

```
┌──────────────────────────────────────────────────────┐
│  编排层  驱动 AI 按流程工作、循环验证              │  ← Hooks / Loops / Skills / Ralph
├──────────────────────────────────────────────────────┤
│  工具层  为项目开发配置的必要工具                    │  ← Skills / MCP 服务器
├──────────────────────────────────────────────────────┤
│  约束层  AI 不能做什么——可代码验证的行为限制         │  ← ArchUnit / Checkstyle / 安全守卫 / CI
├──────────────────────────────────────────────────────┤
│  规格层  代码应该长什么样——可代码验证的正向声明      │  ← lint 配置 / 架构约束测试 / 覆盖率门禁
├──────────────────────────────────────────────────────┤
│  知识层  AI 去哪里找需要的知识                       │  ← CLAUDE.md 知识地图
└──────────────────────────────────────────────────────┘
     必选 ←————————————————————————————————→ 可选
```

**前 3 层（知识层、规格层、约束层）是必选的**，任何项目都必须有。工具层和编排层按需启用。

### 1.3 各层职责

| 层次 | 核心问题 | 产出形态 | 消费者 |
|------|---------|---------|-------|
| **知识层** | "去哪里找知识？" | CLAUDE.md（知识地图） | AI（每次会话加载） |
| **规格层** | "代码应该长什么样？为什么？" | 文档（为什么）+ 代码配置（是什么） | 构建系统自动验证 |
| **约束层** | "不能做什么？怎么拦？" | 约束代码 + 运行时防线 + CI | Hook / 构建系统 / CI 三道防线 |
| **工具层** | "用什么工具？" | MCP 服务器 + Skills | AI 按需调用 |
| **编排层** | "按什么顺序做事？什么时候循环？" | Hooks + Loops + 工作流脚本 | AI 运行时 |

### 1.4 核心原则

| 原则 | 含义 |
|------|------|
| **Spec 在前，代码在后** | 先写规格再写代码；AI 不允许自己发明需求 |
| **验证是强制执行，不是可选步骤** | AI 不能在验证门未通过时说"我做完了" |
| **规格层写"为什么"，约束层写"是什么"** | 文档解释设计意图和全景图，代码负责原子规则的可执行验证，两者不重复 |
| **约束必须机械化，不能只靠文档** | 每条规则都必须有对应的执行工具，"口头约定"不是约定 |
| **约束输出只保留错误** | 验证门禁只返回错误信息——正确的、检查过程的提示不返回，减少 AI 上下文噪音 |
| **安全规则不可绕过** | 即使在无人值守模式下，安全约束也必须生效 |
| **审查不是自我审查** | 代码审查由独立的审查者执行，不是自己看自己的 diff |
| **棕地规则必须显式编码** | 代码库中的旧模式必须被标记为"不要复制"，否则 AI 会照搬 |
| **约束对任何代理同样生效** | 无论用 Claude、Codex 还是人类开发者，约束必须同样有效 |

---

## 第二章：知识层——告诉 AI 去哪里找知识

### 2.1 知识层只有一个文件：CLAUDE.md

CLAUDE.md 是**知识地图**，不是知识本身。AI 每次会话强制加载，因此必须精炼：

```
❌ 冗长的百科全书（浪费上下文窗口）
✅ 精炼的索引地图（告诉 AI 去哪找、找什么）
```

#### CLAUDE.md 必须包含的板块

| 板块 | 写什么 | 为什么 |
|------|--------|-------|
| **项目概述** | 一句话说明项目是什么、技术栈 | 让 AI 知道它在为谁工作 |
| **知识导航** | 指向各层文档/代码的路径 + 一句话说明内容 | 让 AI 知道去哪里找深层知识 |
| **构建与验证命令** | lint、类型检查、测试、构建的完整命令 | 让 AI 知道如何验证自己的工作 |
| **硬性规则** | 安全红线、认证路径、不可逆操作的限制 | 阻止 AI 犯不可逆的错误 |

#### CLAUDE.md 不应该包含的内容

| 不要放这里 | 应该放哪里 |
|-----------|----------|
| 详细的命名规范 | 规格层文档 `.harness/specs/conventions/naming.md` |
| 完整的分层架构说明 | 规格层文档 `.harness/specs/architecture/boundaries.md` |
| ORM/DI/错误处理的代码模式 | 按需上下文模块（知识层子目录） |
| 架构约束测试代码 | 约束层 `.harness/constraints/` |
| Hook 脚本 | 编排层 `.harness/orchestration/hooks/` |

#### 知识地图示例

```markdown
# CLAUDE.md — <项目名>

## 项目概述
<一句话>。技术栈：<技术栈>。

## 知识导航
| 你需要… | 去这里 |
|---------|-------|
| 理解系统架构和分层意图 | `.harness/specs/architecture/boundaries.md` |
| 查看数据流转路径 | `.harness/specs/architecture/data-flow.md` |
| 了解某个功能的设计和范围 | `.harness/specs/design/feature-<name>.md` |
| 查找命名/错误处理/DI 等编码约定 | `.harness/specs/conventions/<topic>.md` |
| 查阅错误码或 API 契约 | `.harness/specs/reference/error-codes.md` / `api-spec.yaml` |
| 学习特定领域的代码模式 | `.harness/knowledge/<domain>.md` |
| 理解哪些旧模式不能复制 | `.harness/knowledge/brownfield-traps.md` |

## 构建与验证
- Lint：`<命令>`
- 类型检查：`<命令>`
- 测试：`<命令>`
- 完整验证：`<命令>`

## 硬性规则
- <安全红线>
- <认证路径限制>
- <不可逆操作的限制>
```

### 2.2 多代理适配：一套地图，多个入口

不同 AI 代理使用不同的指令文件位置。**核心策略：CLAUDE.md 为源真相，其他文件从其派生**。

| 代理 | 指令文件位置 | 加载方式 |
|------|------------|---------|
| Claude Code | `.claude/CLAUDE.md` 或根目录 `CLAUDE.md` | 启动时强制加载 |
| OpenAI Codex | `.codex/AGENTS.md` | 启动时强制加载 |
| Cursor | `.cursorrules` | 启动时强制加载 |
| GitHub Copilot | `.github/copilot-instructions.md` | 启动时加载 |
| **通用基线** | 根目录 `CLAUDE.md` | 跨代理参考 |

```
CLAUDE.md（源真相）
  ├── .claude/CLAUDE.md（+ Claude 特有的 Hook/Skill/工具层引用）
  ├── .codex/AGENTS.md（+ Codex 特有的命令格式）
  └── .cursorrules（精简版，Cursor 上下文窗口较小）
```

维护策略：避免多份文件各自演化。以 CLAUDE.md 为源真相，其他文件定期从其同步。

### 2.3 按需上下文模块

CLAUDE.md 是地图，上下文模块是地图指向的**知识详情**。按领域拆分，只在需要时加载。

#### 拆分原则

| 信号 | 应该拆成独立模块 |
|------|------------------|
| 知识只在特定任务中需要 | 拆分（如导出模式只在写导出功能时需要） |
| 知识每次会话都需要 | 放在 CLAUDE.md 中 |
| 模块内容超过 50 行 | 拆分 |
| 模块之间有交叉引用 | 拆分，用链接关联 |

#### 每个模块的标准结构

```markdown
---
last_updated: 2026-06-14
status: active
owner: backend-team
---

# <领域> — <项目名>

## 概览
一段话说清楚这个领域是什么、怎么运作。

## 协议/接口
代码级别的接口定义（Protocol、Interface、API 签名）。

## 正确做法
带代码示例的标准用法。

## 错误做法
带代码示例的常见陷阱（标注关联的 bug/工单号）。

## 添加新功能的检查清单
1. 步骤一
2. 步骤二

## 测试模式
测试应该怎么写、覆盖什么。
```

---

## 第三章：规格层——代码应该长什么样

### 3.1 规格层的双重形态

规格层有**两种形态**，分工不同：

| 形态 | 写什么 | 为什么不可替代 |
|------|--------|--------------|
| **文档** | "为什么"——设计意图、全景图、规则间的关系 | 测试代码只能表达原子规则，无法传达心智模型和推理链 |
| **代码配置** | "是什么"——lint 规则、架构约束测试、覆盖率门禁 | 可执行、可自动验证、不需要人工审查 |

**文档和代码配置不重复**：
- `boundaries.md` 不逐条罗列"Controller 不调 Mapper"——那是约束层代码的事
- `boundaries.md` 解释"为什么分层、依赖方向是什么、整体格局怎样"
- ArchUnit 测试代码是规格的可执行版本，自身就是最好的原子规则文档

#### 文档写"为什么"的示例

```markdown
# 分层架构

## 设计意图
Controller → Service → Mapper 三层分离，核心目的是：
1. Service 作为唯一的事务边界和业务编排点
2. Controller 只负责协议适配，不承载业务逻辑
3. Mapper 只负责数据映射，不承载业务语义

## 依赖方向
Controller → Service → Mapper → Domain
（所有箭头单向，禁止反向依赖）

## 具体规则
→ 由约束层代码强制执行，参见 .harness/constraints/ 目录
```

### 3.2 规格层目录结构

```
.harness/specs/
├── architecture/              # 架构规格（文档 + 代码配置）
│   ├── overview.md            # 系统概览：技术栈、模块划分、部署拓扑
│   ├── boundaries.md          # 分层意图：为什么分层、依赖方向、设计推理
│   ├── data-flow.md           # 数据流：请求从入口到存储的完整路径
│   └── arch-rules/            # 架构约束配置（代码形态）
│       ├── ArchUnitTests.java # Java 架构约束测试
│       └── .importlinter      # Python 分层约束配置
├── conventions/               # 编码约定
│   ├── README.md              # 约定总览
│   ├── naming.md              # 命名规范
│   ├── error-handling.md      # 错误处理 + 错误码体系
│   ├── logging.md             # 日志规范
│   ├── testing.md             # 测试规范
│   └── di.md                  # 依赖注入规范
├── design/                    # 功能设计（每个功能一个规格）
│   ├── feature-auth.md
│   ├── feature-billing.md
│   └── feature-search.md
├── plans/                     # 迭代计划
│   ├── backlog.md             # 待办事项
│   └── current-sprint.md      # 当前冲刺
└── reference/                 # 参考契约
    ├── error-codes.md         # 错误码表（按模块分段）
    └── api-spec.yaml          # OpenAPI 规格
```

### 3.3 架构文档

#### `overview.md`——系统概览

```markdown
# 架构概览

## 技术栈
- 后端：Spring Boot 2.7 + Java 8 + MyBatis-Plus + MySQL 5.7
- 前端：Vue 3 + Element Plus
- 基础设施：Redis + MinIO + Nginx

## 模块划分
<描述每个模块的职责>

## 部署拓扑
<描述部署架构>
```

#### `boundaries.md`——分层意图

这是规格层最关键的文档。它解释**为什么这样分层**，而不是逐条罗列禁止清单：

```markdown
# 分层架构

## 设计意图
<为什么这样分层，每层的核心职责是什么>

## 依赖方向
Controller → Service → Mapper → Domain
（所有箭头单向，禁止反向依赖）

## 各层职责
### domain（领域层）
纯数据结构，不依赖任何框架。

### mapper（数据访问层）
只做数据映射，不承载业务语义。

### service（业务层）
唯一的事务边界和业务编排点。

### controller（控制层）
HTTP 协议适配，不承载业务逻辑。

### infrastructure（基础设施层）
外部集成，必须通过 Spring 注入。

## 具体规则
→ 由约束层代码强制执行，参见 .harness/constraints/ 目录
```

> **关键洞察**：这份文档解释"为什么"——具体的"禁止什么"由约束层代码定义和执行。文档和代码互补，不重复。

#### `data-flow.md`——数据流

描述请求从入口到存储的完整路径，让 AI 理解数据如何流转。

### 3.4 功能设计文档——每个功能一个规格

功能设计文档遵循**统一模板**，对抗 AI "自己发明需求"的倾向：

```markdown
---
last_updated: 2026-06-14
status: active
owner: auth-team
---

# 功能设计：<功能名称>

## 目标
一段话说清楚这个模块负责什么。

## 范围
### 包含
- <明确在范围内的功能>
### 不包含
- <明确在范围外的功能>

## 分层设计
### domain
<该层在这个功能中承担什么>
### service
<该层在这个功能中承担什么>
### controller
<该层在这个功能中承担什么>

## 关键规则/约束
- <模块特有的约束，如"认证组件必须通过 Spring 注入">
- <状态流转规则，如 CREATED → PAYING → PAID>
- <安全规则，如"sortBy 必须白名单校验">

## 测试要求
- [ ] <必须覆盖的测试场景>
- [ ] <必须覆盖的测试场景>
```

**"范围"部分是最重要的**——它明确告诉 AI "不包含"什么，阻止 AI 越界。

### 3.5 参考契约

#### 错误码体系

```markdown
# 错误码参考

## AUTH 模块（1000-1999）
| 错误码 | HTTP 状态 | 说明 |
|--------|----------|------|
| AUTH_1001 | 401 | 未认证 |
| AUTH_1002 | 403 | 权限不足 |

## USER 模块（2000-2999）
| 错误码 | HTTP 状态 | 说明 |
|--------|----------|------|
| USER_2001 | 404 | 用户不存在 |

## 规则
- 新增业务错误必须在本文件登记
- 新增错误码必须在测试中覆盖对应错误分支
- 错误码按模块分段，每段预留 999 个编号
```

#### API 规格（OpenAPI）

在代码之前定义 API 契约：

```yaml
# api-spec.yaml
openapi: 3.0.3
info:
  title: Taskapp API
  version: 1.0.0
paths:
  /api/v1/auth/login:
    post:
      x-last-updated: 2026-06-14
      x-status: active
      x-owner: auth-team
      # ...
```

### 3.6 package-info.java / 模块声明——层合约

在 Java 项目中，每个包的 `package-info.java` 充当**架构约束的合约声明**：

```java
/**
 * Controller 层 — HTTP 协议边界处理。
 *
 * <p>职责：参数校验、调用 Service、组装响应。
 *
 * <p>约束：
 * <ul>
 *   <li>是依赖链的终点，不允许被其他业务层引用</li>
 *   <li>禁止直接调用 Mapper</li>
 *   <li>禁止写业务规则</li>
 * </ul>
 *
 * @see <a href="../../.harness/specs/architecture/boundaries.md">架构边界文档</a>
 */
package com.example.app.controller;
```

> **通用化**：其他语言可以用类似机制——Python 的 `__init__.py` docstring、Go 的 `doc.go`、TypeScript 的 `README.md` in directory。

---

## 第四章：约束层——让 AI 不能做错事

### 4.1 约束层的核心定位

约束层是**可代码验证的行为限制**。它和规格层的关系：

| | 规格层 | 约束层 |
|---|---|---|
| 性质 | 正向声明："代码应该长什么样" | 负向禁止："不能做什么、怎么拦" |
| 产出 | 文档（为什么）+ 代码配置（是什么） | 约束代码 + 运行时防线 + CI |
| 消费者 | 构建系统自动验证 | Hook + 构建系统 + CI 三道防线 |
| 同一规则的两个形态 | `boundaries.md` 解释"为什么分层" | ArchUnit 测试定义"Controller 不调 Mapper" |

> **关键原则**：如果一条规则没有对应的可执行约束代码，它就不是规则，只是愿望。在 CLAUDE.md 中写"Controller 不要调 Mapper"是愿望；加上 ArchUnit 规则才是规则。

### 4.2 约束执行的三道防线

约束不是单一机制，而是**三道防线**层层递进：

```
┌──────────────────────────────────────────────────────┐
│  第一道：构建系统（编译/测试时拦截）                │
│  触发时机：mvn verify / cargo test / go test          │
│  覆盖范围：lint + 架构检查 + 覆盖率 + 安全扫描      │
│  优势：对任何代理（AI 或人类）同样生效               │
│  劣势：反馈延迟（需要显式运行构建）                  │
├──────────────────────────────────────────────────────┤
│  第二道：AI 运行时 Hook（编辑时拦截）               │
│  触发时机：AI 每次操作时                             │
│  覆盖范围：安全守卫 + 增量 lint + 验证门            │
│  优势：即时反馈，AI 能立刻修正                       │
│  劣势：仅限支持 Hook 的 AI 工具                      │
├──────────────────────────────────────────────────────┤
│  第三道：CI Pipeline（提交/合并时拦截）             │
│  触发时机：git push / PR                             │
│  覆盖范围：全部构建检查 + Doc Freshness + E2E        │
│  优势：最终兜底，即使绕过前两道也能捕获              │
│  劣势：反馈最慢（分钟级）                            │
└──────────────────────────────────────────────────────┘
```

> **关键原则**：构建系统是约束层的核心（最通用、最可靠），Hook 是加速反馈的优化，CI 是最终兜底。即使 AI 工具不支持 Hook，构建系统 + CI 仍然有效。

### 4.3 约束输出原则：只返回错误

约束层检查后的输出是给 AI 看的。**只输出与判断当前代码是否合格相关的错误信息**：

```
❌ 错误的输出（信息噪音，浪费 AI 上下文窗口）：
  ✓ src/main/java/com/example/controller/UserController.java — OK
  ✓ src/main/java/com/example/service/UserService.java — OK
  ✗ src/main/java/com/example/controller/OrderController.java:42 — Controller 不得直接依赖 Mapper
  Ran 3 checks, 1 failed, 2 passed

✅ 正确的输出（只保留错误）：
  ✗ OrderController.java:42 — Controller 不得直接依赖 Mapper
  FIX: 在 Service 中编排数据访问，Controller 仅持有 Service 引用。
  See: .harness/specs/architecture/boundaries.md
```

**具体规则**：
- 不输出通过的检查结果
- 不输出检查过程提示（如"Running lint..."、"Checking architecture..."）
- 不输出总结统计（如"3 passed, 1 failed"）
- 只输出：错误位置 + 错误描述 + 修复建议 + 文档引用

这个原则适用于所有三道防线，尤其是 Hook 和验证门的输出。

### 4.4 第一道防线：构建系统级约束

> **这是约束层的核心**：将约束内化为构建系统的一部分，使得约束对任何代理同样生效。

#### 口头约定机械化对照表

每条约定都必须映射到执行工具：

| 约定 | 执行工具 | 语言生态 |
|------|---------|---------|
| 方法/函数体不超过 N 行 | Checkstyle MethodLength / ruff | Java / Python |
| 文件不超过 N 行 | Checkstyle FileLength / ruff | Java / Python |
| 禁止 System.out / printStackTrace | Checkstyle RegexpSingleline / ruff | Java / Python |
| 分层架构依赖方向 | ArchUnit / import-linter | Java / Python |
| Controller 不调 Mapper/Repository | ArchUnit 自定义规则 | Java |
| 禁止字段级 DI | ArchUnit 注解检查 | Java |
| 禁止 public static 非 final 字段 | SpotBugs MS_* 规则族 | Java |
| 行覆盖率 >= N% | JaCoCo / coverage.py / Istanbul | Java / Python / TS |
| 构建工具链版本锁定 | maven-enforcer / constraints.txt | Java / Python |

#### 架构约束测试（ArchUnit / import-linter）

用代码测试代码的架构合规性。这些测试代码本身即是原子规则的最佳文档：

**Java (ArchUnit)：**
```java
@ArchTest
static final ArchRule controllers_must_not_access_mappers =
    noClasses()
        .that().resideInAPackage("..controller..")
        .should().dependOnClassesThat()
        .resideInAPackage("..mapper..")
        .because("Controller 必须通过 Service 编排数据访问，参见 .harness/specs/architecture/boundaries.md");
```

**Python (import-linter)：**
```ini
[importlinter:contract:layers]
name = Backend layer architecture
layers = controller > service > mapper > domain
```

> **关键洞察**：测试代码是规格的可执行版本——测试名 + `because()` 已经传达了规则和原因。不需要在文档中再逐条重复。文档负责"为什么这样设计"，代码负责"具体禁止什么"。

#### 违规消息设计

错误消息必须包含**错误 + 修复建议 + 文档引用**，且遵循"只输出错误"原则：

```
✗ OrderController.java:42 — Controller 不得直接依赖 Mapper
FIX: 在 Service 中编排数据访问，Controller 仅持有 Service 引用。
See: .harness/specs/architecture/boundaries.md
```

### 4.5 第二道防线：AI 运行时 Hook

Hook 是约束层在 AI 运行时的即时反馈机制，属于编排层的触发机制，但执行的约束逻辑属于约束层。

#### 三种 Hook 类型

| Hook 类型 | 触发时机 | 能做什么 | 不能做什么 |
|-----------|---------|---------|-----------|
| **PreToolUse** | 工具执行**之前** | 拒绝执行（deny） | 修改工具输入 |
| **PostToolUse** | 工具执行**之后** | 通知/建议（advisory） | 阻止已完成的操作 |
| **Stop** | AI 想要结束回合**时** | 阻止结束（block） | 修改已输出的内容 |

#### Hook 1：安全守卫（PreToolUse）

在工具执行前拦截**不可逆的、有安全风险的操作**。

| 规则 | 拦截什么 | 允许什么 |
|------|---------|---------|
| 密钥保护 | 读取/编辑/写入 `.env`、`.pem` | `.env.example`、`.env.template` |
| 删除保护 | `rm -rf`、`rmdir`、`find -delete` | 删除单个指定文件 |
| 分支保护 | `git push --force`、删除主分支 | 普通推送 |

**编写原则**：
1. **Fail-open**：解析错误直接放行，绝不卡死会话
2. **覆盖所有绕过向量**：包括 Bash 中的 `cat .env`、`python -c "open('.env')"`、混淆 glob
3. **只输出错误**：被拦截时只输出拒绝原因，不输出放行记录
4. **无人值守模式下也生效**

#### Hook 2：增量静态检查（PostToolUse）

每次文件编辑后**立即给出反馈**。Advisory（始终退出码 0，永不阻止工作流）。

| 语言 | Lint 工具 | 类型检查 |
|------|----------|---------|
| Python | ruff | mypy |
| TypeScript | ESLint | tsc |
| Java | Checkstyle | javac |
| Go | go vet | — |
| Rust | clippy | rustc |

**输出要求**：只输出检查发现的错误，不输出通过的项目和过程日志。

#### Hook 3：验证门（Stop）

**阻止 AI 在代码不通过检查时结束会话。** 检查 `stop_hook_active` 防止无限循环。只跑快速检查（lint + 单元测试），完整验证门留给编排层的 Skill。

**输出要求**：只输出未通过的检查项。如果全部通过，输出一行 `All checks passed` 即可。

### 4.6 第三道防线：CI Pipeline

CI 是最终兜底。即使开发者（人或 AI）绕过了本地检查，CI 仍能捕获。

#### CI 检查项清单

| 步骤 | 检查什么 | 命令示例 |
|------|---------|---------|
| 工具链对齐 | JDK/Python/Node 版本锁定 | `setup-maven@v5 with maven-version: 3.6.3` |
| Build & Verify | 编译 + 单测 + lint + 安全扫描 | `mvn -B clean verify` |
| Architecture Check | ArchUnit / import-linter | `mvn test -pl . -Dtest=*ArchTest` |
| File Size Check | 文件行数限制 | `find src -name "*.java" -exec wc -l {} +` |
| Coverage Gate | 覆盖率门禁 | JaCoCo / coverage.py |
| **Doc Freshness** | 设计文档是否过期 | 见下方 |

#### Doc Freshness 检查

**防止文档腐化的自动化机制**——检查 `.harness/specs/design/` 下文件的最后修改时间：

```yaml
# GitHub Actions 示例
- name: Doc Freshness
  run: |
    STALE_DAYS=60
    find .harness/specs/design -name "*.md" -mtime +$STALE_DAYS -print | while read f; do
      echo "::warning file=$f::设计文档超过 $STALE_DAYS 天未更新，可能已与实现脱节"
    done
```

> **关键洞察**：文档腐化是 Harness 的隐形杀手。过期的设计文档比没有文档更危险——AI 会按过期规格写代码。

#### 双重保障设计

CI 中的 File Size Check 和构建系统中的 Checkstyle FileLength 存在功能重叠。这不是冗余——这是**双重保障**：

- Checkstyle 在 `mvn verify` 中执行（Java 生态内）
- shell 脚本在 CI 中独立执行（跨生态兜底）
- 即使 Checkstyle 配置被意外绕过，CI 仍能捕获

### 4.7 约束层目录结构

```
.harness/constraints/
├── arch/                          # 架构约束
│   ├── ArchUnitTests.java         # Java 架构约束测试
│   └── .importlinter              # Python 分层约束配置
├── style/                         # 代码风格约束
│   ├── checkstyle.xml             # Java Checkstyle 配置
│   ├── .eslintrc.js               # JS/TS ESLint 配置
│   └── pyproject.toml             # Python ruff 配置
├── security/                      # 安全约束
│   └── spotbugs-filter.xml        # SpotBugs 规则配置
├── coverage/                      # 覆盖率约束
│   └── jacoco.xml                 # JaCoCo 配置
└── ci/                            # CI 约束配置
    └── agent-guardrails.yml       # CI 护栏 workflow
```

---

## 第五章：工具层——为 AI 配置必要工具

### 5.1 工具层的定位

工具层是跨层的基础设施——知识层的 MCP 提供结构化代码导航，编排层的 Skills 提供可复用的工作流。工具层不定义规则，不定义约束，只提供**能力**。

### 5.2 MCP 服务器——给 AI 可编程的代码理解能力

grep 是文本匹配，会遗漏也会误报。MCP 服务器提供**结构化的代码导航**。

#### 什么时候需要 MCP 服务器

| 场景 | grep 够用吗 | 需要 MCP |
|------|-------------|----------|
| 查找函数定义 | 否（注释中也有同名文本） | `where_is("list_meetings")` |
| 验证依赖是否被使用 | 否（字符串中也有同名文本） | `find_references("get_current_user")` |
| 了解服务的公开 API | 否（需要读整个文件） | `outline("export_service")` |
| 简单的文本搜索 | 是 | 不需要 |

#### 不同语言的技术选型

| 语言 | AST 解析库 | MCP 框架 |
|------|-----------|----------|
| Python | `ast`（标准库） | FastMCP |
| TypeScript | `ts-morph` | FastMCP / MCP SDK |
| Go | `go/ast`（标准库） | MCP Go SDK |
| Java | JavaParser / Eclipse JDT | MCP Java SDK |
| Rust | `syn` crate | MCP Rust SDK |

### 5.3 Skills——可复用的工作流片段

Skill 是编排层工作流的原子单元。每个 Skill 封装一个可复用的操作序列。

详见编排层 6.2 节。

### 5.4 工具层目录结构

```
.harness/tools/
├── mcp/                           # MCP 服务器
│   └── codebase_search.py         # 代码导航 MCP 服务器
└── skills/                        # Skills（按工具平台放置）
    └── .claude/skills/            # Claude Code Skills
        ├── plan/SKILL.md
        ├── implement/SKILL.md
        ├── validate/SKILL.md
        └── review/SKILL.md
```

---

## 第六章：编排层——驱动 AI 有纪律地工作

### 6.1 编排层的定位

编排层的核心使命：**驱动 AI 不断验证规格层和约束层是否达标**。

它通过两种机制实现：
- **Hooks**：在 AI 操作的关键节点触发约束检查（事件驱动）
- **Loops**：驱动 AI 按流程循环工作，直到验证达标（循环驱动）

```
         规格层/约束层定义"达标标准"
                ↑ ↓
    编排层驱动 AI → 执行 → 验证 → 不达标则循环
```

### 6.2 PIVR 循环：Plan → Implement → Validate → Review

```
┌─────────┐  .harness/plans/*.md  ┌────────────┐ .harness/reports/*.md ┌──────────┐
│  /plan   │ ──────────────→ │ /implement  │ ──────────────→ │ /validate │
│  只规划   │                 │ 逐任务实现  │                  │  完整门禁  │
│  不写代码 │                 │ 逐任务验证  │                  │           │
└─────────┘                  └────────────┘                  └─────┬────┘
                                                                   │
                                                              PASS ↓
                                                             ┌──────────┐
                                                             │ /review   │
                                                             │ 子代理审查 │
                                                             │ PASS/CONCERNS│
                                                             └──────────┘
```

### 6.3 /plan Skill——只规划，不实现

输出结构化的计划文件 `.harness/plans/<feature-slug>-plan.md`：

```markdown
# 计划：<功能名称>

## 工单
<工单 ID 和一句话描述>

## 受影响文件
### 实现前阅读
- `<路径>`（第 N-M 行）—— <为什么需要读>
### 修改
- `<路径>`—— <变更内容>
### 新建
- `<路径>`—— <用途>

## 有序任务

### 任务 1 — <操作> <目标>
- 内容：<具体变更>
- 模式：`<路径>:L<行号>`—— <参考什么来写>
- 注意：<已知陷阱>
- 验证：`<精确的 shell 命令>`

## 验证门
\`\`\`
<lint> && <类型检查> && <测试>
\`\`\`

## 验收标准
- [ ] <可衡量的标准>
- [ ] 所有验证门命令通过
```

### 6.4 /implement Skill——逐任务执行，逐任务验证

1. **读完整计划后再写代码**
2. **每个任务：读取目标文件 → 实现变更 → 运行验证命令**——失败必须修复
3. **不允许跳过任何任务的验证**——跳过的检查 = 隐藏的回归
4. **所有任务完成后运行完整验证门**
5. **输出实现报告到 `.harness/reports/`**

### 6.5 /validate Skill——完整验证门

| 检查类别 | 命令示例 | 覆盖范围 |
|---------|---------|---------|
| Lint | `ruff check` / `checkstyle:check` | 代码风格 |
| 类型检查 | `mypy` / `tsc --noEmit` | 类型安全 |
| 架构检查 | ArchUnit / import-linter | 分层合规 |
| 单元测试 | `pytest` / `mvn test` | 功能正确性 |
| 覆盖率 | JaCoCo / coverage.py | 测试充分性 |
| 安全扫描 | SpotBugs / bandit | 安全漏洞 |

### 6.6 /review Skill——子代理审查

| 维度 | 检查什么 | 用什么验证 |
|------|---------|-----------|
| 命名规范 | 是否符合规则 | 读 diff |
| 代码模式 | ORM/DI/错误处理是否遵循标准 | 读 diff + 模式参考 |
| 架构合规 | 是否违反分层边界 | ArchUnit / `find_references` |
| 安全 | 输入验证、转义、认证 | 读 diff + 上下文模块 |
| 范围合规 | 是否超出功能设计的"包含"范围 | 对照 .harness/specs/design/*.md |

### 6.7 文件系统是唯一的状态传递通道

```
/plan     →  .harness/plans/xxx-plan.md           →  /implement
/implement →  .harness/reports/xxx-impl-report.md  →  /validate
/validate  →  验证门结果                   →  /review
/review    →  .harness/reports/xxx-review.md       →  提交/修复
```

文件系统优于内存：会话中断后不丢失、可审计、跨会话可传递、人类可读可改。

### 6.8 Ralph 循环：跨会话的自主驱动

```
循环：
  1. 检查 DONE.txt → 如果存在则退出
  2. 将规格（PROMPT.md）注入新的无头 AI 会话
  3. AI 做一个逻辑单元的工作
  4. git commit（捕获每次迭代的工作）
  5. 检查 DONE.txt → 如果存在则退出
  6. 重复，最多 MAX_ITER 次
```

| 决策 | 原因 |
|------|------|
| 每次迭代是全新的 AI 进程 | 不依赖上下文窗口的持续性 |
| 规格是编号的检查清单 | "完成"不是 AI 自己说了算 |
| 每次迭代 git commit | 每次迭代是可回退的检查点 |
| 循环而非模型决定何时完成 | DONE.txt 是模型向驱动器的信号 |
| fix_plan.md 是跨迭代的记忆 | 新会话通过此文件了解前序工作 |

### 6.9 编写好的 PROMPT.md

四个必要部分：**目标** → **规格项** → **工作模式** → **修复计划文件**

规格项编写原则：
```
✅ 可验证：export_service.py 包含 CSVExport 类，具有 content_type、file_extension、render()
❌ 不可验证：添加 CSV 导出功能
```

### 6.10 隔离机制

- **Worktree 隔离**：AI 在独立分支的工作副本中运行，主工作树不动
- **数据库隔离**：并行运行各自获得独立数据库
- **依赖隔离**：venv/node_modules 位于每个 worktree 中

### 6.11 编排层目录结构

```
.harness/orchestration/
├── hooks/                        # AI 运行时 Hook
│   ├── security_guard.py         # PreToolUse 安全守卫
│   ├── post_tool_use_lint.py     # PostToolUse 增量检查
│   └── stop_validate.py          # Stop 验证门
├── loops/                        # 循环驱动
│   ├── ralph.sh                  # Ralph 循环驱动脚本
│   └── prompt-template.md        # PROMPT.md 模板
├── agents/                       # 子代理
│   └── code-reviewer.md
└── settings.json                 # Hook 注册配置（或符号链接到 .claude/settings.json）
```

---

## 第七章：为你的团队构建 Harness——行动清单

### 7.1 第一阶段：知识层 + 规格层（2-3 天）

- [ ] **编写 `CLAUDE.md` 知识地图**：项目概述 + 知识导航 + 构建命令 + 硬性规则
- [ ] **多代理适配**：为每个 AI 代理放置对应的指令文件
- [ ] **编写架构文档**：`overview.md` + `boundaries.md`（写"为什么"）+ `data-flow.md`
- [ ] **编写约定文档**：naming + error-handling + logging + testing + DI
- [ ] **编写功能设计文档**：每个功能一个文件，包含目标/范围/分层设计/约束/测试要求
- [ ] **编写参考契约**：错误码表 + API 规格
- [ ] **识别并拆分上下文模块**：每个"只在特定任务中需要的知识"拆成独立文件
- [ ] **为棕地项目标记"不要复制"的模式**

**检查点**：AI 在没有 Harness 时经常犯的 5 个错误，是否都已被规则覆盖？

### 7.2 第二阶段：约束层（2-3 天）

- [ ] **配置构建系统级约束**：lint + 架构检查 + 覆盖率门禁 + 安全扫描
- [ ] **编写架构约束测试**：ArchUnit / import-linter
- [ ] **编写口头约定机械化对照表**：每条约定映射到执行工具
- [ ] **编写 PreToolUse 安全守卫 Hook**
- [ ] **编写 PostToolUse 增量检查 Hook**
- [ ] **编写 Stop 验证门 Hook**
- [ ] **确保所有约束输出只保留错误信息**
- [ ] **配置 CI Pipeline**：工具链对齐 + Build & Verify + Architecture Check + Doc Freshness
- [ ] **注册所有 Hook**

**检查点**：故意犯一个架构违规（如 Controller 调 Mapper），三道防线是否至少有两道能捕获？输出是否只有错误信息？

### 7.3 第三阶段：工具层（1-2 天）

- [ ] **（可选）构建 MCP 服务器**
- [ ] **（可选）编写 Skills**

### 7.4 第四阶段：编排层（1-2 天）

- [ ] **编写 /plan、/implement、/validate、/review Skills**
- [ ] **编写 code-reviewer 子代理**
- [ ] **编写循环驱动脚本**
- [ ] **编写第一个 PROMPT.md**
- [ ] **配置 worktree + 数据库隔离**

**检查点**：跑一次完整 PIVR 循环，每个环节是否都产生了预期的文件？验证门是否只输出了错误？

---

## 第八章：不同场景的 Harness 模式

### 8.1 小团队/个人项目

**精简版**：知识层 + 规格层 + 约束层（仅构建系统），跳过工具层和编排层。

### 8.2 中型团队

**标准版**：知识层 + 规格层 + 约束层（构建系统 + Hook）+ 编排层（Skills + Hook）。

### 8.3 大型组织/企业级

**扩展版**：五层全部启用 + 多代理适配 + 多代理并行 + 组织级规则继承。

```
CLAUDE.md（组织级基线）
  └── 项目级 CLAUDE.md（+ 项目特有规则）
      ├── .claude/CLAUDE.md
      └── .codex/AGENTS.md

.harness/
├── specs/（完整文档树）
│   ├── architecture/
│   ├── conventions/
│   ├── design/
│   ├── plans/
│   └── reference/
├── constraints/（约束三道防线全部启用，CI 包含 Doc Freshness 检查）
├── tools/（MCP + Skills）
└── orchestration/（Hooks + Ralph + 子代理）
    Ralph 并行运行多个功能
    审查子代理有多个维度
```

### 8.4 非 Claude Code 平台

| Harness 层次 | Claude Code | Cursor | Codex | 通用方案 |
|-------------|-------------|--------|-------|---------|
| 知识层 | CLAUDE.md | .cursorrules | .codex/AGENTS.md | CLAUDE.md |
| 规格层 | .harness/specs/ | .harness/specs/ | .harness/specs/ | .harness/specs/ |
| 约束层 | Hooks + 构建 + CI | 构建 + CI | 构建 + CI | 构建 + CI |
| 工具层 | MCP + Skills | MCP | — | MCP |
| 编排层 | Hooks + Skills + Ralph | Custom modes | — | Hooks + 自定义脚本 |

**关键洞察**：规格层和约束层的构建系统部分是**平台无关**的。无论用什么 AI 工具，`.harness/specs/architecture/boundaries.md` 和 ArchUnit/Checkstyle 都同样生效。这是企业级 Harness 的核心优势。

---

## 第九章：常见陷阱

### 9.1 规则太模糊

```
❌ "代码应该整洁"
✅ "Python 函数使用 snake_case，类使用 PascalCase"
```

### 9.2 约定没有机械化

```
❌ "Controller 不要调 Mapper"（只是愿望）
✅ "Controller 不要调 Mapper" + ArchUnit 规则 + CI 检查（才是约定）
```

如果一条约定没有对应的执行工具，它就不是约定。

### 9.3 规格层文档与约束层代码重复

```
❌ boundaries.md 逐条罗列"Controller 不调 Mapper"——和 ArchUnit 测试重复
✅ boundaries.md 解释"为什么分层"，ArchUnit 测试定义"具体禁止什么"——互补不重复
```

### 9.4 验证不是强制的

如果 AI 可以选择跳过验证，它一定会跳过。

**解决方案**：Stop Hook + 逐任务验证 + 构建系统门禁 + CI 兜底，四重保障。

### 9.5 约束输出噪音太多

验证门禁返回大量"通过"信息和过程日志，淹没真正需要 AI 关注的错误。

**解决方案**：所有约束检查只输出错误——错误的文件、错误描述、修复建议、文档引用。通过的检查不输出，过程日志不输出。

### 9.6 自己审查自己

**解决方案**：子代理审查 + ArchUnit 结构化验证 + CI 独立检查。

### 9.7 棕地项目中的旧模式被 AI 复制

**解决方案**：CLAUDE.md 标记"不要复制" + 上下文模块提供正确/错误对比 + ArchUnit 捕获违规。

### 9.8 文档腐化

设计文档与实现脱节，AI 按过期规格写代码。

**解决方案**：YAML front matter（last_updated/status/owner）+ Doc Freshness CI 检查。

### 9.9 多代理规则不同步

`.claude/CLAUDE.md` 和 `.codex/AGENTS.md` 各自演化。

**解决方案**：以 `CLAUDE.md` 为源真相，其他文件从其派生。定期 CI 检查文件内容一致性。

### 9.10 错误码无人管理

新增错误不登记，错误码冲突或遗漏。

**解决方案**：错误码按模块分段 + "新增必须登记并覆盖测试"的流程约束 + CI 检查错误码唯一性。

---

## 附录 A：文件结构模板（企业级）

```
<project-root>/
├── CLAUDE.md                          # 知识地图（源真相，每次会话加载）
│
├── .harness/                          # Harness 工程系统（所有 harness 相关文件集中于此）
│   ├── knowledge/                     # 按需上下文模块（知识层）
│   │   ├── <domain>.md               # 特定领域的代码模式
│   │   └── brownfield-traps.md       # 棕地项目"不要复制"清单
│   │
│   ├── specs/                         # 规格层
│   │   ├── architecture/              # 架构规格
│   │   │   ├── overview.md            # 系统概览
│   │   │   ├── boundaries.md          # 分层意图（写"为什么"）
│   │   │   └── data-flow.md          # 数据流
│   │   ├── conventions/               # 编码约定
│   │   │   ├── README.md
│   │   │   ├── naming.md
│   │   │   ├── error-handling.md
│   │   │   ├── logging.md
│   │   │   ├── testing.md
│   │   │   └── di.md
│   │   ├── design/                    # 功能设计
│   │   │   └── feature-*.md
│   │   ├── plans/                     # 迭代计划
│   │   │   ├── backlog.md
│   │   │   └── current-sprint.md
│   │   └── reference/                 # 参考契约
│   │       ├── error-codes.md
│   │       └── api-spec.yaml
│   │
│   ├── constraints/                   # 约束层
│   │   ├── arch/                      # 架构约束
│   │   │   └── ArchUnitTests.java
│   │   ├── style/                     # 代码风格约束
│   │   │   ├── checkstyle.xml
│   │   │   ├── .eslintrc.js
│   │   │   └── pyproject.toml
│   │   ├── security/                  # 安全约束
│   │   │   └── spotbugs-filter.xml
│   │   ├── coverage/                  # 覆盖率约束
│   │   │   └── jacoco.xml
│   │   └── ci/                        # CI 约束配置
│   │       └── agent-guardrails.yml
│   │
│   ├── tools/                         # 工具层
│   │   ├── mcp/                       # MCP 服务器
│   │   │   └── codebase_search.py
│   │   └── skills/                    # Skills
│   │       └── .claude/skills/
│   │           ├── plan/SKILL.md
│   │           ├── implement/SKILL.md
│   │           ├── validate/SKILL.md
│   │           └── review/SKILL.md
│   │
│   ├── orchestration/                 # 编排层
│   │   ├── hooks/                     # AI 运行时 Hook
│   │   │   ├── security_guard.py
│   │   │   ├── post_tool_use_lint.py
│   │   │   └── stop_validate.py
│   │   ├── loops/                     # 循环驱动
│   │   │   ├── ralph.sh
│   │   │   └── prompt-template.md
│   │   ├── agents/                    # 子代理
│   │   │   └── code-reviewer.md
│   │   └── settings.json              # Hook 注册
│   │
│   ├── plans/                         # /plan 输出
│   ├── reports/                       # /implement + /review 输出
│   └── ralph/                         # 循环驱动工作目录
│
├── .claude/
│   └── CLAUDE.md                      # Claude Code 专用（从 CLAUDE.md 派生）
├── .codex/
│   └── AGENTS.md                      # Codex 专用（从 CLAUDE.md 派生）
└── .mcp.json                          # MCP 服务器注册
```

## 附录 B：Spec 与门禁对照表

| Harness 层次 | Spec 机制 | 门禁机制 | 协同方式 |
|-------------|----------|---------|---------|
| 知识层 | CLAUDE.md 知识地图 + 上下文模块 | — | 知识地图告诉 AI"去哪找" |
| 规格层 | 文档（为什么）+ 代码配置（是什么） | 构建系统自动验证 | Spec 定义"代码应该长什么样"，门禁验证"是否符合" |
| 约束层 | — | 构建系统 + Hook + CI（三道防线） | 门禁阻止违反规格层定义的规则 |
| 工具层 | — | — | 提供能力，不定义规则 |
| 编排层 | 计划文件 + PROMPT.md | Hook 触发 + Loop 循环 + 逐任务验证 | 驱动 AI 不断验证规格层和约束层是否达标 |

## 附录 C：口头约定机械化对照表模板

在 `.harness/constraints/` 目录下维护这张表：

```
# 口头约定 → 机械化规则 对照表
# ─────────────────────────────────
# 约定                        | 执行工具
# ─────────────────────────────────
# 方法 <= 50 行               | Checkstyle MethodLength
# 文件 <= 300 行              | Checkstyle FileLength + CI File Size Check
# 禁止 System.out             | Checkstyle RegexpSinglelineJava
# Controller 不调 Mapper      | ArchUnit 分层规则
# 禁止字段级 @Autowired       | ArchUnit 注解检查
# 禁止 public static 非 final | SpotBugs MS_*
# 行覆盖率 >= 80%             | JaCoCo coverage check
# 构建工具版本锁定            | maven-enforcer-plugin
# 设计文档不超过 60 天未更新  | CI Doc Freshness
# ─────────────────────────────────
```

## 附录 D：关键决策参考

| 你在犹豫…… | 推荐选择 | 原因 |
|------------|---------|------|
| CLAUDE.md 写什么？ | 知识地图（指向哪里找），不是百科全书（把内容全放进来） | 避免上下文窗口浪费 |
| 规则放 CLAUDE.md 还是 .harness/knowledge/？ | 每次都需要 → CLAUDE.md；特定任务 → .harness/knowledge/ | 避免上下文窗口浪费 |
| 规格层文档写什么？ | "为什么"——设计意图、全景图、规则间关系 | 约束层代码已经表达了"是什么" |
| 约束层代码和规格层文档重复吗？ | 不重复——文档写"为什么"，代码写"是什么" | 互补而非冗余 |
| 需要独立的规格层吗？ | 中型项目以上需要 | 小项目知识层够用；大项目需要架构/约定/设计/参考的完整文档树 |
| 约束靠构建系统还是 Hook？ | 构建系统为核心，Hook 为加速反馈 | 构建系统通用可靠，Hook 仅在支持它的 AI 工具中生效 |
| Hook 应该阻塞还是建议？ | 安全 → 阻塞；质量 → 建议 | 安全不可妥协，质量允许迭代 |
| Stop Hook 跑快速还是完整检查？ | 快速 | 完整检查留给 /validate |
| 约束输出应该包含什么？ | 只输出错误：错误位置 + 描述 + 修复建议 + 文档引用 | 减少上下文噪音，让 AI 聚焦于修正错误 |
| 架构约束用 ArchUnit 还是 Code Review？ | 两者都要 | ArchUnit 捕获结构性违规，Code Review 捕获语义性问题 |
| 规格项写多少条？ | 6-12 条 | 太少覆盖不足，太多 AI 会遗漏 |
| 多代理规则怎么维护？ | 一份源真相 + 多份派生 | 避免规则分散后的同步负担 |
| 需要错误码体系吗？ | 中型项目以上需要 | 小项目用 HTTP 状态码 + 消息够用；大项目需要可追溯的错误码 |
| 需要编排层吗？ | 需要自主完成完整功能时 | 交互式会话不需要 Ralph |
