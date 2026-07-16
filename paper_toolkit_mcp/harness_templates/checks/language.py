"""R0 语言强制 + R4 语言行文 + R6 AI痕迹 检查模块。"""

from __future__ import annotations

import re

from . import (
    Violation,
    VerifyResult,
    find_ref_section_start,
    is_code_block_start,
    parse_heading,
    count_words,
    count_chinese_chars,
)


# ── 内部辅助 ──────────────────────────────────────────────

def _count_english_words(text: str) -> int:
    """统计英文单词数。"""
    return len(re.findall(r'[a-zA-Z]+', text))


def _is_table_line(line: str) -> bool:
    """判断是否为表格行。"""
    stripped = line.strip()
    return stripped.startswith("|") and stripped.endswith("|")


# ── R0.1 全文语言强制中文 ──────────────────────────────────

def check_language_chinese(lines: list[str], result: VerifyResult) -> None:
    """R0.1 全文语言强制中文。

    遍历每个非代码块、非表格、非参考文献的正文行，统计英文单词数占比。
    如果英文单词数 > 总字数的 40%，报 error。

    例外情况（不报错）：
    - 参考文献区域（## 参考文献 之后的内容）
    - 英文在括号内的术语定义（如"疼痛恐惧量表（Fear of Pain Questionnaire, FPQ-III）"）
    """
    in_code_block = False
    ref_start = find_ref_section_start(lines)

    for i, line in enumerate(lines, 1):
        # 跳过参考文献区域
        if i - 1 >= ref_start:
            continue

        stripped = line.strip()
        if is_code_block_start(stripped):
            in_code_block = not in_code_block
            continue
        if in_code_block:
            continue
        if _is_table_line(line):
            continue
        if not stripped:
            continue
        # 跳过标题行
        if parse_heading(line) is not None:
            continue

        total = count_words(stripped)
        if total == 0:
            continue
        en_words = _count_english_words(stripped)
        # 英文单词每个算1字，与 count_words 口径一致
        if en_words > total * 0.4:
            # 检查是否为术语括注：英文主要在括号内
            # 如"疼痛恐惧量表（Fear of Pain Questionnaire, FPQ-III）"
            # 移除括号内容后重新计算
            stripped_no_parens = re.sub(r'[（(][^）)]*[）)]', '', stripped)
            total_no_parens = count_words(stripped_no_parens)
            en_words_no_parens = _count_english_words(stripped_no_parens)

            # 如果移除括号后英文占比降低到阈值以下，说明是术语括注，跳过
            if total_no_parens > 0 and en_words_no_parens <= total_no_parens * 0.4:
                continue

            # 检查是否为技术定义/参数（包含变量赋值、函数调用等）
            # 如 "- 定义：mouth_rise / fall_time" 或 "max(pitch_exec)"
            tech_patterns = [
                r'[a-zA-Z_]\w*\s*=\s*\d',  # 变量赋值 var=0.40
                r'[a-zA-Z_]\w*\([^)]*\)',   # 函数调用 func()
                r'[a-zA-Z_]\w*\s*/\s*[a-zA-Z_]\w*',  # 斜杠分隔 var1 / var2
                r'\*\*[A-Za-z]+\*\*',       # 加粗的工具名 **InsightFace**
            ]
            is_tech = any(re.search(p, stripped) for p in tech_patterns)
            if is_tech:
                continue

            result.add(Violation(
                rule="R0.1",
                line=i,
                message=f"英文占比过高（{en_words}/{total}）：'{stripped[:50]}'",
                severity="error",
                fix_hint=(
                    "文稿必须使用中文撰写。英文仅限专业术语首次出现时括注，"
                    "如'检索增强生成（Retrieval-Augmented Generation, RAG）'"
                ),
            ))


# ── R0.2 标题必须中文 ──────────────────────────────────────

def check_heading_language(lines: list[str], result: VerifyResult) -> None:
    """R0.2 标题必须中文。

    跳过第一个 # 标题（论文标题）。
    如果标题中英文单词数 > 标题总字数的 30%，报 error。
    """
    is_first_heading = True
    for i, line in enumerate(lines, 1):
        parsed = parse_heading(line)
        if parsed is None:
            continue
        level, text = parsed
        # 跳过第一个 # 标题（论文标题）
        if is_first_heading and level == 1:
            is_first_heading = False
            continue
        is_first_heading = False

        total = count_words(text)
        if total == 0:
            continue
        en_words = _count_english_words(text)
        if en_words > total * 0.3:
            result.add(Violation(
                rule="R0.2",
                line=i,
                message=f"标题英文占比过高（{en_words}/{total}）：'{text.strip()}'",
                severity="error",
                fix_hint=(
                    "标题必须使用中文。将英文标题改为中文，如 "
                    "'Results' → '结果', 'Methods' → '方法', 'Discussion' → '讨论'"
                ),
            ))


# ── R1.3 正文禁止列表 ──────────────────────────────────────

def check_no_list_in_body(lines: list[str], result: VerifyResult) -> None:
    """R1.3（增强）正文禁止列表。

    遍历正文行（非代码块、非表格、非标题），检测以 `- `、`* `、
    `1. `、`2. `、`（1）`、`（2）` 等开头的行。如果在正文中发现列表格式
    （连续 >= 2 行），报 error。
    """
    in_code_block = False
    consecutive_list_lines = 0
    start_line = 0

    # 匹配以下格式：
    # - 无序列表：- item, * item
    # - 数字编号：1. item, 2) item
    # - 中文括号编号：（1）item, (2)item
    list_pattern = re.compile(r'^(?:[-*]\s+|\d+[.)]\s+|[（(]\d+[）)]\s*)')

    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        if is_code_block_start(stripped):
            # 结束前一个列表段
            if consecutive_list_lines >= 2:
                result.add(Violation(
                    rule="R1.3",
                    line=start_line,
                    message=f"正文中连续{consecutive_list_lines}行使用列表格式",
                    severity="error",
                    fix_hint=(
                        "正文中禁止使用列表格式。将列表内容改为段落叙述，"
                        "用分号'；'连接，或使用（1）（2）编号格式。"
                        "例如：将 '- 项目1\\n- 项目2\\n- 项目3' 改为 "
                        "'本研究包含三方面内容：一是项目1；二是项目2；三是项目3。'"
                    ),
                ))
            consecutive_list_lines = 0
            in_code_block = not in_code_block
            continue
        if in_code_block:
            consecutive_list_lines = 0
            continue
        if _is_table_line(line):
            consecutive_list_lines = 0
            continue
        if parse_heading(line) is not None:
            # 标题中断列表
            if consecutive_list_lines >= 2:
                result.add(Violation(
                    rule="R1.3",
                    line=start_line,
                    message=f"正文中连续{consecutive_list_lines}行使用列表格式",
                    severity="error",
                    fix_hint=(
                        "正文中禁止使用列表格式。将列表内容改为段落叙述，"
                        "用分号'；'连接，或使用（1）（2）编号格式。"
                        "例如：将 '- 项目1\\n- 项目2\\n- 项目3' 改为 "
                        "'本研究包含三方面内容：一是项目1；二是项目2；三是项目3。'"
                    ),
                ))
            consecutive_list_lines = 0
            continue

        if list_pattern.match(stripped):
            if consecutive_list_lines == 0:
                start_line = i
            consecutive_list_lines += 1
        else:
            # 检测到列表行结束，报告连续的列表行
            if consecutive_list_lines >= 2:
                result.add(Violation(
                    rule="R1.3",
                    line=start_line,
                    message=f"正文中连续{consecutive_list_lines}行使用列表格式",
                    severity="error",
                    fix_hint=(
                        "正文中禁止使用列表格式。将列表内容改为段落叙述，"
                        "用分号'；'连接，或使用（1）（2）编号格式。"
                        "例如：将 '- 项目1\\n- 项目2\\n- 项目3' 改为 "
                        "'本研究包含三方面内容：一是项目1；二是项目2；三是项目3。'"
                    ),
                ))
            # 单独的列表格式行（如独立的编号段落）也需要报告
            elif consecutive_list_lines == 1:
                result.add(Violation(
                    rule="R1.3",
                    line=start_line,
                    message="正文段落以列表格式符号开头",
                    severity="error",
                    fix_hint=(
                        "正文中禁止使用列表格式。将列表内容改为段落叙述，"
                        "删除开头的编号符号（如1.、（1）等），直接使用段落文字。"
                    ),
                ))
            consecutive_list_lines = 0

    # 文件末尾的列表
    if consecutive_list_lines >= 2:
        result.add(Violation(
            rule="R1.3",
            line=start_line,
            message=f"正文中连续{consecutive_list_lines}行使用列表格式",
            severity="error",
            fix_hint=(
                "正文中禁止使用列表格式。将列表内容改为段落叙述，"
                "用分号'；'连接，或使用（1）（2）编号格式。"
                "例如：将 '- 项目1\\n- 项目2\\n- 项目3' 改为 "
                "'本研究包含三方面内容：一是项目1；二是项目2；三是项目3。'"
            ),
        ))
    elif consecutive_list_lines == 1:
        result.add(Violation(
            rule="R1.3",
            line=start_line,
            message="正文段落以列表格式符号开头",
            severity="error",
            fix_hint=(
                "正文中禁止使用列表格式。将列表内容改为段落叙述，"
                "删除开头的编号符号（如1.、（1）等），直接使用段落文字。"
            ),
        ))


# ── R1.4 正文禁止加粗 ──────────────────────────────────────

def check_no_bold_in_body(lines: list[str], result: VerifyResult) -> None:
    """R1.4 正文禁止加粗。

    遍历正文行（非标题行、非代码块），检测 `**...**` 格式。
    如果在正文段落中发现加粗，报 error。
    """
    in_code_block = False
    bold_pattern = re.compile(r'\*\*[^*]+\*\*')
    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        if is_code_block_start(stripped):
            in_code_block = not in_code_block
            continue
        if in_code_block:
            continue
        # 跳过标题行
        if parse_heading(line) is not None:
            continue
        # 跳过空行
        if not stripped:
            continue
        # 跳过分隔线
        if stripped == "---":
            continue
        matches = bold_pattern.findall(stripped)
        if matches:
            # 过滤掉独立行的加粗标签（如 **摘要**、**背景**、**方法** 等）
            # 这些通常是结构化摘要的章节标签，是标准格式
            if stripped.startswith("**") and stripped.endswith("**") and stripped.count("**") == 2:
                continue
            # 过滤掉表格中的加粗（表头）
            if _is_table_line(line):
                continue
            result.add(Violation(
                rule="R1.4",
                line=i,
                message=f"正文中使用加粗标记：'{matches[0][:40]}'",
                severity="error",
                fix_hint=(
                    "正文中禁止使用加粗标记。删除 ** 和 **，保持纯文本。"
                    "如需强调，通过措辞而非格式实现"
                ),
            ))


# ── R3.1 必备中文章节 ──────────────────────────────────────

def check_required_sections_chinese(lines: list[str], result: VerifyResult) -> None:
    """R3.1 必备中文章节。

    只接受中文关键词：
    - ["研究背景", "引言"]
    - ["资料与方法", "方法"]
    - ["结果"]
    - ["讨论"]
    - ["结论"]

    如果缺少某个章节，报 error。
    """
    required_sections: list[tuple[str, list[str]]] = [
        ("研究背景", ["研究背景", "引言"]),
        ("资料与方法", ["资料与方法", "方法"]),
        ("结果", ["结果"]),
        ("讨论", ["讨论"]),
        ("结论", ["结论"]),
    ]
    headings: list[tuple[int, str]] = []
    for i, line in enumerate(lines, 1):
        parsed = parse_heading(line)
        if parsed:
            headings.append((i, parsed[1]))

    heading_texts_lower = [h[1].lower() for h in headings]
    for display_name, keywords in required_sections:
        found = False
        for kw in keywords:
            if any(kw.lower() in ht for ht in heading_texts_lower):
                found = True
                break
        if not found:
            result.add(Violation(
                rule="R3.1",
                line=0,
                message=f"缺少必备章节：'{display_name}'",
                severity="error",
                fix_hint=f"添加'{display_name}'章节。注意：章节标题必须使用中文",
            ))


# ── R4.1 缩写一致性 ────────────────────────────────────────

def check_abbreviation_consistency(lines: list[str], result: VerifyResult) -> None:
    """R4.1 检查缩写定义与使用一致性。"""
    full_text = "\n".join(lines)
    # 提取缩写定义：中文术语（English，缩写）或 中文术语（缩写）
    abbrev_defs: dict[str, dict] = {}
    for m in re.finditer(
        r'([\u4e00-\u9fff]+[^\(（]*?)\s*[（(]\s*([A-Z][A-Za-z\s]+?)\s*[，,]\s*([A-Z]{2,})\s*[）)]',
        full_text,
    ):
        cn_term = m.group(1).strip()
        en_term = m.group(2).strip()
        abbrev = m.group(3).strip()
        pos = m.start()
        if abbrev not in abbrev_defs or pos < abbrev_defs[abbrev]["first_pos"]:
            abbrev_defs[abbrev] = {"cn": cn_term, "en": en_term, "first_pos": pos}

    # 也匹配纯中文缩写定义：中文（缩写）或 中文（缩写，附加内容）
    # 负前瞻 (?![A-Za-z]) 防止匹配英文术语的前缀片段（如 "Complete Case Analysis" 中的 "CC"）
    # [^\)）]* 允许括号内缩写后有额外内容（如 "CCA，n=13"）
    for m in re.finditer(
        r'([\u4e00-\u9fff]+[^\(（]*?)\s*[（(]\s*([A-Z]{2,}(?![A-Za-z]))[^\)）]*\s*[）)]',
        full_text,
    ):
        abbrev = m.group(2).strip()
        pos = m.start()
        if abbrev not in abbrev_defs or pos < abbrev_defs[abbrev]["first_pos"]:
            cn_term = m.group(1).strip()
            abbrev_defs[abbrev] = {"cn": cn_term, "en": "", "first_pos": pos}

    # 检查缩写是否在首次使用时定义
    for abbrev, info in abbrev_defs.items():
        # 找缩写首次出现位置（排除定义括号内部的出现）
        def_match_text = full_text[info["first_pos"]:info["first_pos"] + 200]
        abbrev_in_def_pos = def_match_text.find(abbrev)
        if abbrev_in_def_pos >= 0:
            def_end = info["first_pos"] + abbrev_in_def_pos + len(abbrev)
        else:
            def_end = info["first_pos"] + len(abbrev)

        search_start = 0
        first_use = -1
        while True:
            pos = full_text.find(abbrev, search_start)
            if pos < 0:
                break
            # 跳过定义区域内部的出现
            if info["first_pos"] <= pos < def_end:
                search_start = pos + len(abbrev)
                continue
            first_use = pos
            break
        if first_use < 0:
            continue
        # 如果首次出现在定义之前，说明在使用前未定义
        if first_use < info["first_pos"]:
            line_num = full_text[:first_use].count("\n") + 1
            result.add(Violation(
                rule="R4.1",
                line=line_num,
                message=f"缩写'{abbrev}'在定义前已使用",
                severity="warning",
                fix_hint=f"在首次使用'{abbrev}'处添加完整定义",
            ))


# ── R4.2 / R6.2 行文谦逊 ──────────────────────────────────

# 默认夸大词列表（当 spec 未配置时使用）
# 分类：A=夸大断言 B=AI高频虚词 C=过度修饰 D=伪学术腔
_DEFAULT_BOAST_WORDS = [
    # A. 夸大断言（无证据的绝对化表述）
    "首次证实", "颠覆性", "革命性", "绝无仅有", "前所未有",
    "极其创新", "突破性", "独创", "首创", "完美解决",
    "彻底解决", "完全解决", "根本性突破", "史无前例", "划时代",
    "里程碑式", "开创性", "改写", "重塑",
    # B. AI 高频虚词（LLM 训练语料中过度出现的词）
    "范式", "范式转变", "范式转换", "协同", "赋能", "解锁", "释放",
    "催化", "驾驭", "深耕", "织就", "画卷", "景观", "领域",
    "基石", "灯塔", "枢纽",
    # C. 过度修饰（空泛的形容词/副词）
    "无缝", "稳健", "全面", "关键", "至关重要", "不可或缺",
    "精妙", "细致入微", "深刻", "显著", "卓越", "非凡",
    "无与伦比", "引人瞩目", "令人瞩目",
    # D. 伪学术腔（AI 偏好的学术八股）
    "值得注意的是", "需要指出的是", "不容忽视", "毋庸置疑", "不言而喻",
    "众所周知", "总而言之", "综上所述", "在当今", "在当下",
    "日新月异", "蓬勃发展", "方兴未艾",
]

def check_humble_language(
    lines: list[str],
    result: VerifyResult,
    *,
    boast_words: list[str] | None = None,
) -> None:
    """R4.2 & R6.2 检查行文谦逊与自我夸大。

    在非代码块行中匹配夸大词列表，报 error。
    boast_words 通过 spec 配置注入，未配置时使用默认列表。
    """
    if boast_words is None:
        boast_words = _DEFAULT_BOAST_WORDS
    in_code_block = False
    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        if is_code_block_start(stripped):
            in_code_block = not in_code_block
            continue
        if in_code_block:
            continue
        for word in boast_words:
            if word in line:
                result.add(Violation(
                    rule="R4.2",
                    line=i,
                    message=f"使用未论证夸大词汇：'{word}'",
                    severity="error",
                    fix_hint="替换为客观、谦逊的表述。如'首次证实'→'初步表明'，'突破性'→'具有一定改进'",
                ))


# ── R6.1 标题冒号检查 ──────────────────────────────────────

def check_heading_colon(lines: list[str], result: VerifyResult) -> None:
    """R6.1 检查标题中的中文冒号。"""
    for i, line in enumerate(lines, 1):
        parsed = parse_heading(line)
        if parsed is None:
            continue
        _level, text = parsed
        if "：" in text:
            result.add(Violation(
                rule="R6.1",
                line=i,
                message=f"标题中包含冒号：'{text.strip()}'",
                severity="error",
                fix_hint="将冒号标题改为其他表述方式（如将'A：B'改为'B的A'）",
            ))


# ── R6.3 禁止回引 ──────────────────────────────────────────

# 默认回引正则模式（当 spec 未配置时使用）
_DEFAULT_BACK_REF_PATTERNS = [
    r'见本文\s*\d',
    r'如前文\s*\d',
    r'如上文\s*\d',
    r'本研究\s*\d+\.\d+',
    r'前述\s*\d',
    r'同\s*\d+\.\d+',
    r'详见\s*\d',
]

def check_back_reference(
    lines: list[str],
    result: VerifyResult,
    *,
    back_reference_patterns: list[str] | None = None,
) -> None:
    """R6.3 检查回引。

    back_reference_patterns 通过 spec 配置注入，未配置时使用默认模式。
    """
    if back_reference_patterns is None:
        back_reference_patterns = _DEFAULT_BACK_REF_PATTERNS
    in_code_block = False
    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        if is_code_block_start(stripped):
            in_code_block = not in_code_block
            continue
        if in_code_block:
            continue
        for pattern in back_reference_patterns:
            if re.search(pattern, line):
                result.add(Violation(
                    rule="R6.3",
                    line=i,
                    message=f"疑似回引：'{stripped[:60]}'",
                    severity="error",
                    fix_hint="删除回引，改为在当前位置直接陈述观点。学术论文中不应出现'见本文X节'等回引",
                ))
                break  # 每行只报一次


# ── R7.3 用户意见标记 ──────────────────────────────────────

def check_user_feedback_markers(lines: list[str], result: VerifyResult) -> None:
    """R7.3 扫描 【...】 标记，报告数量和位置，severity 为 info。"""
    count = 0
    positions: list[int] = []
    in_code_block = False
    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        if is_code_block_start(stripped):
            in_code_block = not in_code_block
            continue
        if in_code_block:
            continue
        markers = re.findall(r'【[^】]+】', line)
        if markers:
            count += len(markers)
            positions.append(i)
    if count > 0:
        result.add(Violation(
            rule="R7.3",
            line=positions[0],
            message=f"共有{count}处【】用户意见标记待处理",
            severity="info",
            fix_hint=f"标记位置：L{', L'.join(str(p) for p in positions)}",
        ))


# ── 导出 ──────────────────────────────────────────────────

ALL_LANGUAGE_CHECKS = {
    "R0.1": check_language_chinese,
    "R0.2": check_heading_language,
    "R1.3": check_no_list_in_body,
    "R1.4": check_no_bold_in_body,
    "R3.1": check_required_sections_chinese,
    "R4.1": check_abbreviation_consistency,
    "R4.2": check_humble_language,
    "R6.1": check_heading_colon,
    "R6.2": check_humble_language,  # 复用
    "R6.3": check_back_reference,
    "R7.3": check_user_feedback_markers,
}
