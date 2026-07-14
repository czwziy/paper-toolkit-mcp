# Harness Engineering 适配科学论文撰写的实践指南

基于 OpenAI Harness Engineering 方法论，结合护理健康教育 RAG 智能问答系统论文撰写项目的实际落地经验，提炼面向科学论文撰写场景的 Harness 实践指南。本指南不重复 Harness Engineering 的概念阐释，直接给出可操作的方案。

---

## 一、为什么科学论文撰写需要 Harness

AI Agent 辅助论文撰写时，最容易犯的错误不是"内容不完整"，而是"格式违规"和"数据不一致"——这些错误在作者自审时容易被忽略，但在同行评审中会被放大。Harness Engineering 的核心价值在于：**把审稿人会检查的规则，提前转化为 Agent 不得不遵守的约束**。

论文撰写场景中，Harness 需要解决的核心问题：

| 问题类型 | 典型表现 | 审稿人敏感度 |
|---------|---------|-------------|
| 统计格式违规 | P=0.030、χ²=68.4 | 高——一眼可见 |
| 数据不一致 | 摘要写96.1%、正文写96% | 高——逐字核对 |
| 文献编造 | 虚构DOI或PMID | 极高——学术不端 |
| 百分率格式 | 表格单元格重复写% | 中——格式不专业 |
| AI痕迹 | 标题用冒号、回引、夸大词汇 | 高——审稿人反感 |

---

## 二、落地路线图

论文撰写的 Harness 落地是渐进式的，分为三个阶段：

```
Phase 1: 信息层（1天）           Phase 2: 约束层（2-3天）         Phase 3: 自动化层（1周）
┌───────────────────┐       ┌───────────────────┐       ┌───────────────────┐
│ CLAUDE.md 地图模式  │  →    │ 规则体系 + 验证脚本  │  →    │ Agent 自验证闭环    │
│ .trae/rules/ 规范   │       │ harness/verify.py   │       │ 人工审查清单        │
│ 文档结构化          │       │ harness/rules.md    │       │ 定期全量检查        │
└───────────────────┘       └───────────────────┘       └─────────────────┘
  适合：所有论文项目              适合：正式投稿论文              适合：长期系列研究
  收益：Agent 输出一致性 ↑       收益：格式错误 ↓↓↓             收益：人工审查量 ↓↓
```

**关键要点**：论文撰写项目中，Phase 2 的优先级最高。因为论文的格式错误（如 P 值格式、百分率小数位、数据一致性）是"硬伤"，审稿人一眼可见。

---

## 三、Phase 1：信息层——让 Agent "看得懂"你的论文项目

### 3.1 CLAUDE.md：论文项目的地图

**反面教材**：

```
# ❌ 错误示范：把所有格式规范塞进 CLAUDE.md
P值格式：P≥0.01保留2位小数...
百分率：分母<100时报告整数...
标题层级：不超过4级...
（后面还有 200 行规范）
```

问题：挤占上下文窗口、Agent 无法快速定位需要的信息。

**正确做法**（本项目实际使用的 CLAUDE.md）：

```markdown
# CLAUDE.md

## 项目简介
护理健康教育RAG智能问答系统的学术论文撰写项目。论文题为"支持自定义知识库接入的患者
健康教育智能问答系统研制与场景化评价"，目标期刊为护理信息学/医学信息学领域核心期刊。

## 快速导航
| 你想做什么 | 去哪里看 |
|-----------|---------|
| 了解论文格式规范 | harness/rules.md |
| 运行自动化格式检查 | harness/verify.py |
| 查看人工审查清单 | harness/checklist.md |
| 了解工作指令（最高优先级） | .trae/rules/constitution.md |
| 了解详细格式规范 | .trae/rules/文稿格式.md |
| 查看当前论文正文 | manuscript/manuscript_v5.md |
| 查看参考文献数据 | ref/ref.json |
| 查看原始研究数据 | data/research_data.csv |
| 查看统计分析脚本 | scripts/statistical_calculation.py |
| 查看知识库种子数据 | data/seed_data/nhc_prescriptions/ |

## 硬性规则（必须遵守）
1. 文献真实性：绝对禁止编造不存在的文献
2. 引用策略：边检索边补充，禁止批量检索后统一补引
3. 用户意见：文稿中【】包裹的内容为用户意见，须针对性完善
4. 数据一致性：同一指标在摘要、正文、表格中的数值须完全一致
5. 层级编号：阿拉伯数字层级法（1→1.1→1.1.1→1.1.1.1），不超过4级
6. 标题长度：标题不超过15字，末尾无标点
7. P值格式：P≥0.01保留2位小数；0.001≤P<0.01保留3位小数；P<0.001报告为"P<0.001"
8. AI痕迹控制：标题禁用冒号；禁用"首次证实""颠覆性"等未论证词汇；严禁回引
9. 段落内层级：同级内容合并于同一段落，用分号连接
10. 术语规范：术语全文统一，多次出现的专业术语首次出现时添加缩写
11. 表格单位：表格中单元格禁止出现%等单位，统一到标题/表头中，以（%）表示
12. 语言态度：行文逻辑周密，避免自我吹捧/夸大/形容词滥用

## 提交规范
- 任务结束前执行门禁验证脚本 harness/verify.py
```

**设计原则**：
- 控制在 50 行以内
- "你想做什么 → 去哪里看"比"这是什么"更有效——面向任务而非面向知识
- 硬性规则单独列出——这些是脚本会强制验证的，不是"建议"

### 3.2 .trae/rules/：IDE 级别的规范注入

Trae IDE 的 rules 系统是 Harness Engineering 在论文撰写场景中的天然载体。它在 Agent 每次对话时自动加载，无需手动指定，是"约束即环境"理念的最轻量实现。

本项目使用了两个规则文件：

**constitution.md（工作指令）**——定义最高优先级的工作流程规则：
- 任务规划（复杂任务必须使用 TodoWrite）
- 文献引用策略（边检索边补充，禁止批量补引）
- 用户意见处理（【】标记须针对性完善）
- 知识盲区（禁止脑补，须先检索）

**文稿格式.md（格式规范）**——定义论文格式规则：
- 层级编号体系
- 数据格式（P值、百分率、统计量）
- 正文结构要求
- 语言与行文规范
- 文献引用格式
- AI痕迹控制

### 3.3 文件结构：论文项目的知识库

```
论文项目/
├── CLAUDE.md                    # 项目地图（Phase 1）
├── .trae/                       # IDE 级规范（Phase 1）——IDE固定读取，不可移动
│   ├── rules/
│   │   ├── constitution.md      # 工作指令
│   │   └── 文稿格式.md          # 格式规范
│   ├── skills/                  # IDE 技能
│   └── mcp.json                 # MCP 配置
├── manuscript/                  # 文稿层——论文正文与参考文献
│   ├── manuscript_v5.md         # 论文正文（带版本号）
│   └── ref/
│       └── ref.json             # 参考文献
├── data/                        # 数据层——原始数据与知识库
│   ├── research_data.csv        # 原始研究数据
│   └── seed_data/               # 知识库种子数据
│       └── nhc_prescriptions/
├── scripts/                     # 统计层——统计分析脚本
│   ├── statistical_calculation.py
│   └── comprehensive_data_validation.py
├── .harness/                      # 约束层——Harness 基础设施
│   ├── rules.md                 # 规则体系（R0-R9）
│   ├── verify.py                # 自动化验证脚本
│   ├── checks/                  # 验证规则实现
│   │   ├── language.py          # R0 语言 + R4 行文 + R7 AI痕迹
│   │   ├── structure.py         # R1 结构 + R8 字数
│   │   ├── citations.py         # R5 引用
│   │   └── data.py              # R2 数据
│   ├── specs/
│   │   └── manuscript-spec.yaml # 可变标准配置
│   ├── checklist.md             # 人工审查清单
│   └── Harness.md               # 本指南
└── README.md                    # 项目说明
```

**设计原则**：按功能边界划分5层，每层职责单一、互不交叉——

| 层 | 目录 | 职责 | 边界规则 |
|---|------|------|---------|
| IDE规范 | `.trae/` | IDE自动加载的规则与技能 | 不可移动（IDE固定读取路径） |
| 文稿 | `manuscript/` | 论文正文与参考文献 | 仅含文稿文件，不含数据或脚本 |
| 数据 | `data/` | 原始研究数据与知识库种子 | 仅含数据文件，不含分析逻辑 |
| 统计 | `scripts/` | 统计分析脚本 | 仅含代码，不含数据或文稿 |
| 约束 | `harness/` | 规则、验证、审查 | 仅含约束基础设施，不含业务内容 |

> **注意**：`.trae/` 是 IDE 固定读取的配置目录，必须位于项目根目录下，不可移入子目录。其余4个目录均按功能独立放置，边界清晰。

---

## 四、Phase 2：约束层——让 Agent "不得不"写规范论文

### 4.1 规则体系：从"口头约定"到"可验证规则"

本项目的做法是创建 `harness/rules.md`，将每条格式规范转化为包含三要素的规则：

```
规则定义 → 违规示例 → 验证方法
```

验证方法分为三类：
- **A（全自动）**：脚本可完全自动检查，如 P 值格式、标题层级
- **S（半自动）**：脚本初筛 + 人工终审，如数据一致性、缩写定义
- **M（纯人工）**：只能人工审查，如结构完整性、文献真实性

**经验法则**：如果一条规则在审稿意见中被提过 3 次以上，就应该写成 A 类规则。

### 4.2 规则编写示例

以下是本项目 rules.md 中的完整规则示例，可直接作为模板使用：

#### 示例1：R2.1 P值格式（A类——全自动）

```markdown
### R2.1 P值格式

**规则**：P≥0.01时保留2位小数（如P=0.03）；0.001≤P<0.01时保留3位小数
（如P=0.006）；P<0.001时报告为"P<0.001"；P值前不写前导零。

**违规示例**：
- ❌ `P=0.030`（P≥0.01应保留2位小数，即P=0.03）
- ❌ `P=0.0060`（0.001≤P<0.01应保留3位小数，即P=0.006）
- ❌ `p<0.001`（应大写P）
- ❌ `P=0.0001`（应报告为P<0.001）

**验证方法**：[A] 脚本正则匹配所有P值出现，检查格式合规性。
```

对应的验证脚本函数：

```python
def check_p_value_format(lines: list[str], result: VerifyResult):
    """R2.1 检查P值格式。"""
    for i, line in enumerate(lines, 1):
        if line.strip().startswith("```"):
            continue
        # 检查小写p
        for m in re.finditer(r'(?<![A-Za-z])p\s*([=<>])', line):
            result.add(Violation(
                rule="R2.1", line=i,
                message=f"P值应大写：'p{m.group(1)}'",
                severity="error",
                fix_hint="将p改为大写P"
            ))
        # 检查P=0.000x
        for m in re.finditer(r'P\s*=\s*(0\.0{3,}\d+)', line):
            result.add(Violation(
                rule="R2.1", line=i,
                message=f"P值极小应报告为P<0.001：'P={m.group(1)}'",
                severity="error",
                fix_hint="改为P<0.001"
            ))
        # 检查P>=0.01时小数位>2
        for m in re.finditer(r'P\s*=\s*(0\.0[1-9]\d+)', line):
            val = m.group(1)
            if len(val.split('.')[1]) > 2 and float(val) >= 0.01:
                result.add(Violation(
                    rule="R2.1", line=i,
                    message=f"P≥0.01应保留2位小数：'P={val}'",
                    severity="error",
                    fix_hint=f"改为P={round(float(val), 2)}"
                ))
```

#### 示例2：R2.4 百分率（S类——半自动）

```markdown
### R2.4 百分率

**规则**：率一般保留1位小数，必要时可保留2位小数；表格中%符号应提取到
表头/列标题统一呈现，单元格内不再重复写%。

**违规示例**：
- ❌ `| 96.0% | 85.5% |`（%应提取到表头，单元格只写数值）
- ❌ `96%`（率应保留1位小数，即96.0%）
- ❌ `85.500%`（百分率不应保留3位以上小数）

**正确示例**：
- ✅ 表头写"数值（%）"，单元格写"96.0""85.5"
- ✅ 正文中独立出现的百分率写"96.0%"（保留1位小数）

**验证方法**：[S] 脚本检测表格单元格中是否包含%符号，标记为疑似违规；
人工确认表头是否已统一标注%。
```

对应的验证脚本函数：

```python
def check_percentage_format(lines: list[str], result: VerifyResult):
    """R2.4 检查百分率格式：表格中%提取到表头，率保留1位小数。"""
    for i, line in enumerate(lines, 1):
        if line.strip().startswith("```"):
            continue
        stripped = line.strip()
        if stripped.startswith("|") and stripped.endswith("|"):
            # 跳过分隔行
            if re.match(r'^\|[\s\-:|]+\|$', stripped):
                continue
            cells = [c.strip() for c in stripped.split("|")[1:-1]]
            # 检测是否为表头行
            is_header = any(re.search(r'[\u4e00-\u9fff]', c) for c in cells) and \
                        not any(re.match(r'^\d+\.?\d*（', c) for c in cells)
            if is_header:
                continue  # 表头行允许包含%
            # 检查数据行单元格中是否包含%
            cells_with_pct = [c for c in cells if "%" in c]
            if cells_with_pct:
                result.add(Violation(
                    rule="R2.4", line=i,
                    message=f"表格数据单元格中包含%符号，应提取到表头统一标注",
                    severity="warning",
                    fix_hint="在表头/列标题中标注（%），单元格内只写数值"
                ))
        # 正文中百分率小数位检查
        if not stripped.startswith("|"):
            for m in re.finditer(r'(\d+(?:\.\d+)?)%', stripped):
                pct_str = m.group(1)
                if "." in pct_str and len(pct_str.split(".")[1]) > 2:
                    result.add(Violation(
                        rule="R2.4", line=i,
                        message=f"百分率小数位超过2位：'{m.group(0)}'",
                        severity="error",
                        fix_hint="百分率保留1~2位小数"
                    ))
```

#### 示例3：R6.3 禁止回引（A类——全自动）

```markdown
### R6.3 禁止回引

**规则**：严禁在论文中进行回引，如"见本文2.3.1节""本研究2.2节佐证了本观点"。

**违规示例**：
- ❌ "如前文2.3.1节所述"
- ❌ "见本文表1"
- ❌ "本研究3.1节已证明"

**验证方法**：[A] 脚本正则匹配"见本文""如前文""如上文""本研究\d"等回引模式。
```

对应的验证脚本函数：

```python
def check_back_reference(lines: list[str], result: VerifyResult):
    """R6.3 检查回引。"""
    back_ref_patterns = [
        r'见本文', r'见上文', r'如前文', r'如上文',
        r'本研究\s*\d', r'本研究第\d', r'见\d+\.\d+',
    ]
    for i, line in enumerate(lines, 1):
        if line.strip().startswith("```"):
            continue
        for pattern in back_ref_patterns:
            if re.search(pattern, line):
                result.add(Violation(
                    rule="R6.3", line=i,
                    message=f"疑似回引：'{line.strip()[:60]}'",
                    severity="error",
                    fix_hint="删除回引，改为在当前位置直接陈述观点"
                ))
                break
```

### 4.3 验证脚本：论文的格式检查器

核心设计原则——"错误信息即 Prompt"：

**每条报错必须包含三要素**：
1. 什么错了
2. 怎么改（给出具体修正值）
3. 对应哪条规则

实际运行示例：

```
$ python harness/verify.py manuscript/manuscript_v5.md --verbose

🔍 检查 R1.1...
🔍 检查 R2.1...
🔍 检查 R2.3...
🔍 检查 R2.4...
🔍 检查 R6.1...

检查完成：共 5 项检查
  错误：0
  警告：5

⚠️ 警告详情：
  [R4.1] L17: 缩写'LLM'在定义前已使用
    💡 HINT: 在首次使用'LLM'处添加完整定义
  [R4.1] L13: 缩写'PEHT'在定义前已使用
    💡 HINT: 在首次使用'PEHT'处添加完整定义
  [R5.3] L27: 单行引用4篇文献，默认一个观点只引1篇
    💡 HINT: 确认是否确实需要多篇文献支撑该观点
```

Agent 看到这种报错，不需要任何额外提示就能自动修复。**你写的每一条验证规则，本质上都是一个自动触发的 Prompt**。

### 4.4 验证脚本的整体架构

```python
# 数据结构
@dataclass
class Violation:
    rule: str          # 规则编号，如"R2.1"
    line: int          # 行号
    message: str       # 问题描述
    severity: str      # error | warning | info
    fix_hint: str      # 修复建议

@dataclass
class VerifyResult:
    errors: list       # 错误列表
    warnings: list     # 警告列表
    infos: list        # 提示列表

    def summary(self) -> str:
        # 格式化输出，包含错误详情和修复建议
        ...

# 规则注册表
ALL_CHECKS = {
    "R1.1": check_heading_hierarchy,
    "R1.2": check_heading_length,
    "R2.1": check_p_value_format,
    "R2.3": check_statistic_format,
    "R2.4": check_percentage_format,
    "R2.5": check_data_consistency,
    "R4.1": check_abbreviation_consistency,
    "R5.1": check_citation_format,
    "R6.1": check_heading_colon,
    "R6.3": check_back_reference,
    ...
}

# 主流程
def verify(filepath, rules=None, verbose=False) -> VerifyResult:
    lines = load_markdown(filepath)
    result = VerifyResult()
    for rule_id in (rules or ALL_CHECKS.keys()):
        ALL_CHECKS[rule_id](lines, result)
    return result
```

### 4.5 本项目实际验证的规则清单

| 规则 | 验证类型 | 典型违规 | 修复方式 |
|------|---------|---------|---------|
| R1.1 标题层级 | A | 5级标题 | 减少层级 |
| R1.2 标题长度 | A | 标题超15字 | 精简标题 |
| R2.1 P值格式 | A | P=0.030 | P=0.03 |
| R2.2 均值±标准差 | S | 85.5±12.34 | 小数位一致 |
| R2.3 推断统计量 | A | χ²=68.4 | χ²=68.40 |
| R2.4 百分率 | S | 表格单元格含% | 提取到表头 |
| R2.5 数据一致性 | S | 摘要与正文数值不同 | 统一数值 |
| R4.1 术语缩写 | S | 缩写在定义前使用 | 添加完整定义 |
| R4.2 行文谦逊 | A | "首次证实" | 客观表述 |
| R5.1 引用格式 | A | (Smith, 2024) | [@cite_key] |
| R5.2 待引证标记 | A | [待引证]残留 | 补充文献 |
| R5.3 引用密度 | S | 单行4篇引用 | 确认必要性 |
| R6.1 标题冒号 | A | "消融实验：XXX" | "XXX的消融实验" |
| R6.2 自我夸大 | A | "极其创新" | 客观表述 |
| R6.3 回引 | A | "见本文2.3.1节" | 删除回引 |
| R7.3 用户意见 | A | 【】标记残留 | 处理意见 |

### 4.6 表格百分率的处理——一个典型案例

本项目在 R2.4 百分率规则上经历了两次迭代，体现了"把主观品味翻译成机械规则"的渐进过程：

**第一版规则**：分母<100时报告整数百分率
→ 问题：率一般建议保留1位小数，且表格中%应提取到表头统一呈现

**第二版规则**：率保留1位小数；表格中%提取到表头，单元格只写数值
→ 修正后表格从 `| 96.0% |` 变为表头标注"数值（%）"，单元格写 `96.0`

**教训**：规则的第一版往往不完善，需要根据实际使用反馈迭代。这正是约束层需要 2-3 天的原因——不是写规则难，而是验证规则是否合理需要时间。

---

## 五、Phase 3：自动化层——让 Agent 自我验证

### 5.1 人工审查清单

自动化脚本无法覆盖所有规则。本项目创建了 `harness/checklist.md`，覆盖 M 类规则：

```markdown
# 人工审查清单

## 一、结构完整性
- [ ] 引言是否包含研究背景、目的、意义
- [ ] 引言是否客观评介前人研究并指出研究空白
- [ ] 资料与方法是否完整描述研究设计、对象与纳入排除标准
- [ ] 资料与方法是否说明研究工具及信效度
- [ ] 资料与方法是否说明统计学分析方法
- [ ] 涉及人体研究是否说明伦理审查与知情同意
- [ ] 结果是否按观察指标顺序依次报告，不作主观解释
- [ ] 讨论是否结合文献解释结果、指出局限性
- [ ] 结论是否提炼核心发现（非各章小结重复）

## 二、语言与行文
- [ ] 全文术语是否统一
- [ ] 专业术语首次出现时是否添加缩写定义
- [ ] 是否杜绝口语化表述
- [ ] 行文是否谦逊，无未论证词汇
- [ ] 同级并列内容是否合并在同一段落内
- [ ] 括号内是否无解释性语句

## 三、数据与统计
- [ ] 同一指标在摘要、正文、表格中的数值是否完全一致
- [ ] P值格式是否规范
- [ ] 均值与标准差小数位是否一致
- [ ] 推断统计量是否保留2位小数
- [ ] 百分率是否按规则保留小数位
- [ ] 效应量与置信区间格式是否规范

## 四、文献引用
- [ ] 所有引用是否指向真实存在的文献
- [ ] 是否无[待引证]标记残留
- [ ] 引用密度是否合理

## 五、AI痕迹
- [ ] 标题中是否无冒号
- [ ] 是否无自我夸大式表述
- [ ] 是否无回引
- [ ] 整体行文风格是否自然

## 六、用户意见
- [ ] 文稿中所有【】标记是否已处理
```

### 5.2 验证工作流

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│ 1. 运行 verify.py │ →   │ 2. 修复错误和警告  │ →   │ 3. 人工审查清单   │
│    获取自动检查结果 │     │    重新运行确认    │     │    逐项审查通过   │
└─────────────────┘     └─────────────────┘     └─────────────────┘
```

目标状态：`verify.py` 输出 0 错误，警告均为已确认可接受的半自动规则提示。

### 5.3 本项目的验证结果

经过两轮修复，`verify.py` 对 manuscript_v5.md 的检查结果为：

- **错误：0**
- **警告：5**（均为 S 类规则，需人工判断）
  - R4.1：摘要中缩写在定义前使用（摘要惯例，可接受）
  - R5.3：引言部分引用密度较高（综述需要，可接受）

---

## 六、快速启动模板

如果你要在自己的论文项目中落地 Harness Engineering，按以下步骤操作：

### Step 1：创建 CLAUDE.md（30分钟）

复制本项目的 [CLAUDE.md](../CLAUDE.md)，修改项目简介和快速导航表。控制在 50 行以内。

### Step 2：创建 .trae/rules/（1小时）

复制本项目的 [.trae/rules/constitution.md](../.trae/rules/constitution.md) 和 [.trae/rules/文稿格式.md](../.trae/rules/文稿格式.md)，根据目标期刊要求调整格式规范。

### Step 3：创建 harness/rules.md（2小时）

复制本项目的 [rules.md](rules.md)，根据目标期刊的《稿约》和《作者须知》调整规则。每条规则必须包含：规则定义、违规示例、验证方法（A/S/M）。

### Step 4：创建 harness/verify.py（3小时）

复制本项目的 [verify.py](verify.py)，根据 rules.md 中的 A 类规则编写检查函数。每条报错必须包含三要素：问题、修复、规则编号。

### Step 5：创建 harness/checklist.md（1小时）

复制本项目的 [checklist.md](checklist.md)，根据 rules.md 中的 M 类规则编写审查项。

### Step 6：运行验证并迭代

```bash
python harness/verify.py manuscript/manuscript.md --verbose
```

修复所有错误，确认警告可接受，按清单完成人工审查。

---

## 七、踩坑记录

### 坑1：规则的第一版往往不完善

R2.4 百分率规则经历了两次迭代。第一版"分母<100报告整数"看似合理，但实际与期刊惯例冲突。**建议**：规则制定后先在论文上试运行一轮，根据输出调整。

### 坑2：表格%提取需要同步修改表头

单纯去除单元格中的%而不在表头标注，会导致读者无法理解数值含义。**建议**：表格修改必须表头和单元格同步调整。

### 坑3：摘要中的缩写定义顺序

摘要中常直接使用缩写（如 RAG、LLM），但正文才给出完整定义。脚本会报"缩写在定义前已使用"的警告。**建议**：这是摘要惯例，可接受；但若目标期刊要求摘要中也定义缩写，则须修改。

### 坑4：自动化验证的假阳性

verify.py 对表头行的%检测曾出现误报。**建议**：脚本需要区分表头行和数据行，表头行允许包含%。

### 坑5：数据一致性检查的局限性

脚本只能比对摘要和正文中的数值字符串，无法理解语义等价性。**建议**：R2.5 数据一致性设为 S 类（半自动），脚本初筛 + 人工终审。
