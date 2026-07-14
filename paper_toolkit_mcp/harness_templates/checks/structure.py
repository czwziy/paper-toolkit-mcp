"""R1 结构编号 + R8 字数检查。"""

from __future__ import annotations

import re
from functools import partial

from . import (
    VerifyResult,
    Violation,
    count_words,
    extract_heading_number,
    is_code_block_start,
    parse_heading,
)


# ── R1.1 标题层级编号格式 ──────────────────────────────────

def check_heading_hierarchy(lines: list[str], result: VerifyResult):
    """R1.1 检查标题层级编号格式。"""
    # 先检测Markdown标题偏移量：论文标题用 #，则 ## 对应编号1级
    # 找到第一个编号标题的Markdown层级来确定偏移
    offset = 1  # 默认偏移：# 为论文标题，## 为编号1级
    for line in lines:
        parsed = parse_heading(line)
        if parsed is None:
            continue
        level, text = parsed
        number = extract_heading_number(text)
        if number and len(number.split(".")) == 1:
            # 找到第一个单级编号（如"1""2"），其Markdown层级减1即为偏移
            offset = level - 1
            break

    for i, line in enumerate(lines, 1):
        parsed = parse_heading(line)
        if parsed is None:
            continue
        level, text = parsed
        number = extract_heading_number(text)
        if number is None:
            # 无编号标题（如"摘要""关键词"等），跳过
            continue
        parts = number.split(".")
        # 检查层级深度
        if len(parts) > 4:
            result.add(Violation(
                rule="R1.1", line=i,
                message=f"标题层级超过4级：'{text.strip()}'",
                severity="error",
                fix_hint="减少层级深度，不超过4级（如1.1.1.1）"
            ))
        # 检查编号与Markdown层级是否匹配（考虑偏移）
        expected_md_level = len(parts) + offset
        if level != expected_md_level:
            result.add(Violation(
                rule="R1.1", line=i,
                message=f"编号层级({number})与Markdown标题层级({'#' * level})不匹配",
                severity="warning",
                fix_hint=f"调整Markdown标题为{'#' * expected_md_level}级"
            ))


# ── R1.2 标题长度 ─────────────────────────────────────────

def check_heading_length(lines: list[str], result: VerifyResult):
    """R1.2 检查标题长度不超过15字。"""
    is_first_heading = True
    for i, line in enumerate(lines, 1):
        parsed = parse_heading(line)
        if parsed is None:
            continue
        level, text = parsed
        # 跳过论文标题（第一个#标题）
        if is_first_heading and level == 1:
            is_first_heading = False
            continue
        is_first_heading = False
        # 去掉编号部分
        number = extract_heading_number(text)
        if number:
            title_text = text[len(number):].strip()
        else:
            title_text = text.strip()
        # 计算中文字符数（中文算1字，英文单词算1字）
        char_count = len(title_text)
        if char_count > 15:
            result.add(Violation(
                rule="R1.2", line=i,
                message=f"标题超15字（{char_count}字）：'{title_text}'",
                severity="warning",
                fix_hint="精简标题，控制在15字以内"
            ))
        # 检查末尾标点
        if title_text and title_text[-1] in "。！？；：":
            result.add(Violation(
                rule="R1.2", line=i,
                message=f"标题末尾有标点：'{title_text}'",
                severity="error",
                fix_hint="删除标题末尾标点"
            ))


# ── R8.1 全文总字数 ───────────────────────────────────────

def check_total_word_count(
    lines: list[str],
    result: VerifyResult,
    *,
    total_min: int = 3000,
    total_max: int = 8000,
):
    """R8.1 统计全文总字数（排除代码块、参考文献列表）。"""
    in_code_block = False
    ref_section_start = len(lines)
    for idx, line in enumerate(lines):
        stripped = line.strip()
        if stripped.lower().startswith("## references") or stripped.lower().startswith("## 参考文献"):
            ref_section_start = idx
            break

    words_lines: list[str] = []
    for i, line in enumerate(lines):
        if i >= ref_section_start:
            break
        stripped = line.strip()
        if is_code_block_start(stripped):
            in_code_block = not in_code_block
            continue
        if in_code_block:
            continue
        words_lines.append(line)

    current = count_words("\n".join(words_lines))
    if current < total_min:
        result.add(Violation(
            rule="R8.1", line=0,
            message=f"全文仅{current}字，未达到下限{total_min}字。请扩充研究背景、方法描述或讨论部分",
            severity="error",
            fix_hint=f"扩充内容至{total_min}字以上",
        ))
    elif current > total_max:
        result.add(Violation(
            rule="R8.1", line=0,
            message=f"全文{current}字，超过上限{total_max}字。请精简冗余内容",
            severity="warning",
            fix_hint=f"精简内容至{total_max}字以内",
        ))
    else:
        result.add(Violation(
            rule="R8.1", line=0,
            message=f"全文{current}字，在{total_min}-{total_max}字范围内",
            severity="info",
        ))


# ── R8.2 正文段落字数 ─────────────────────────────────────

def check_paragraph_word_count(
    lines: list[str],
    result: VerifyResult,
    *,
    paragraph_min: int = 80,
    paragraph_max: int = 300,
):
    """R8.2 检查正文段落字数。

    仅检查正文段落，跳过：
    - 代码块
    - 标题行
    - 表格行
    - 列表项（由 R1.3 单独检查）
    - 参考文献区域
    """
    in_code_block = False
    current_paragraph: list[str] = []
    paragraph_start_line = 0
    list_pattern = re.compile(r'^(?:[-*]\s+|\d+[.)]\s+)')

    # 找到参考文献起始位置
    ref_start = len(lines)
    for idx, line in enumerate(lines):
        stripped = line.strip()
        if stripped.lower().startswith("## references") or stripped.lower().startswith("## 参考文献"):
            ref_start = idx
            break

    def _flush_paragraph():
        if not current_paragraph:
            return
        text = "\n".join(current_paragraph)
        wc = count_words(text)
        if wc < paragraph_min:
            result.add(Violation(
                rule="R8.2", line=paragraph_start_line,
                message=f"该段落仅{wc}字，建议扩充至{paragraph_min}字以上",
                severity="warning",
                fix_hint=f"扩充段落内容至{paragraph_min}字以上",
            ))
        elif wc > paragraph_max:
            result.add(Violation(
                rule="R8.2", line=paragraph_start_line,
                message=f"该段落{wc}字，建议精简至{paragraph_max}字以内",
                severity="warning",
                fix_hint=f"精简段落内容至{paragraph_max}字以内",
            ))
        current_paragraph.clear()

    for i, line in enumerate(lines, 1):
        # 跳过参考文献区域
        if i - 1 >= ref_start:
            _flush_paragraph()
            continue

        stripped = line.strip()
        # 代码块边界
        if is_code_block_start(stripped):
            in_code_block = not in_code_block
            if in_code_block:
                _flush_paragraph()
            continue
        if in_code_block:
            continue
        # 标题行：结束当前段落
        if parse_heading(line) is not None:
            _flush_paragraph()
            continue
        # 表格行：跳过
        if stripped.startswith("|") and stripped.endswith("|"):
            _flush_paragraph()
            continue
        # 空行：段落分隔
        if not stripped:
            _flush_paragraph()
            continue
        # 列表项：跳过（由 R1.3 单独检查）
        if list_pattern.match(stripped):
            _flush_paragraph()
            continue
        # 连续非空行属于同一段落
        if not current_paragraph:
            paragraph_start_line = i
        current_paragraph.append(stripped)

    # 文末最后一段
    _flush_paragraph()


# ── R8.3 摘要字数 ─────────────────────────────────────────

def check_abstract_word_count(
    lines: list[str],
    result: VerifyResult,
    *,
    abstract_min: int = 200,
    abstract_max: int = 500,
):
    """R8.3 检查摘要字数。"""
    abstract_start = -1
    abstract_end = len(lines)

    for i, line in enumerate(lines):
        stripped = line.strip()
        # 检测摘要起始：**摘要** 或 ## 摘要
        if stripped in ("**摘要**",) or re.match(r"^#{1,6}\s+摘要\s*$", stripped):
            abstract_start = i + 1
            continue
        # 检测摘要结束：**关键词** 或 ## 关键词 或下一个 ## 标题
        if abstract_start >= 0:
            if stripped in ("**关键词**",) or re.match(r"^#{1,6}\s+关键词\s*$", stripped):
                abstract_end = i
                break
            if re.match(r"^#{1,6}\s+", stripped) and not re.match(r"^#{1,6}\s+摘要\s*$", stripped):
                abstract_end = i
                break

    if abstract_start < 0:
        result.add(Violation(
            rule="R8.3", line=0,
            message="未检测到摘要区域",
            severity="warning",
            fix_hint="添加**摘要**或## 摘要标记",
        ))
        return

    abstract_text = "\n".join(lines[abstract_start:abstract_end])
    current = count_words(abstract_text)

    if current < abstract_min:
        result.add(Violation(
            rule="R8.3", line=abstract_start,
            message=f"摘要仅{current}字，建议扩充至{abstract_min}-{abstract_max}字",
            severity="warning",
            fix_hint=f"扩充摘要内容至{abstract_min}字以上",
        ))
    elif current > abstract_max:
        result.add(Violation(
            rule="R8.3", line=abstract_start,
            message=f"摘要{current}字，建议精简至{abstract_min}-{abstract_max}字",
            severity="warning",
            fix_hint=f"精简摘要内容至{abstract_max}字以内",
        ))
    else:
        result.add(Violation(
            rule="R8.3", line=abstract_start,
            message=f"摘要{current}字，在{abstract_min}-{abstract_max}字范围内",
            severity="info",
        ))


# ── 导出 ──────────────────────────────────────────────────

# R8.* 函数需要额外参数（字数范围），verify.py 主入口会从 manuscript-spec.yaml
# 读取配置后通过 functools.partial 或 lambda 包装来适配统一调用签名 (lines, result)。
ALL_STRUCTURE_CHECKS = {
    "R1.1": check_heading_hierarchy,
    "R1.2": check_heading_length,
    "R8.1": check_total_word_count,
    "R8.2": check_paragraph_word_count,
    "R8.3": check_abstract_word_count,
}
