"""R5 / R6 文献引用检查模块。

检查项：
- R5.1  引用格式验证（增强 cite_key 验证）
- R5.2  待引证标记
- R5.3  引用密度
- R5.4  文献总量
- R6.1  引用位置
- R6.2  多文献同引格式
"""

from __future__ import annotations

import re

from . import (
    Violation,
    VerifyResult,
    find_ref_section_start,
    is_code_block_start,
)


# ── R5.1 引用格式验证（增强版）────────────────────────────

def check_citation_format(lines: list[str], result: VerifyResult) -> None:
    """R5.1 — 验证引用格式。

    1. 检测 APA 格式 (Author et al., Year) → 应改为 [@cite_key]
    2. 检测数字引用 [1] → 应改为 [@cite_key]
    3. 校验 [@cite_key] 中 cite_key 的合法性：
       - 禁止 doi:/pmid:/arxiv: 等前缀
       - 禁止包含 /（DOI 特征）
       - 禁止 .后跟数字（DOI 特征如 10.1234）
    """
    ref_start = find_ref_section_start(lines)
    in_code_block = False

    for i, line in enumerate(lines, 1):
        if is_code_block_start(line):
            in_code_block = not in_code_block
            continue
        if in_code_block:
            continue
        # 跳过参考文献列表区域
        if i - 1 >= ref_start:
            continue

        # ── 检查 APA 引用格式 (Author et al., Year) ──
        for m in re.finditer(
            r'\([A-Z][a-z]+\s+et\s+al\.?,?\s*\d{4}\)', line
        ):
            result.add(
                Violation(
                    rule="R5.1",
                    line=i,
                    message=f"使用APA引用格式而非[@cite_key]：'{m.group(0)}'",
                    severity="error",
                    fix_hint="使用 search_papers 搜索文献标题，从返回结果中获取 cite_key，然后使用 [@cite_key] 格式引用",
                )
            )

        # ── 检查数字引用 [1] ──
        for m in re.finditer(r'(?<!\[)\[(\d+)\](?!\])', line):
            result.add(
                Violation(
                    rule="R5.1",
                    line=i,
                    message=f"使用数字引用格式而非[@cite_key]：'[{m.group(1)}]'",
                    severity="error",
                    fix_hint="使用 search_papers 搜索文献标题，从返回结果中获取 cite_key，然后使用 [@cite_key] 格式引用",
                )
            )

        # ── 检查 [@...] 中 cite_key 合法性 ──
        for m in re.finditer(r'\[@([^\]]+)\]', line):
            key = m.group(1).strip()

            # 禁止 doi:/pmid:/arxiv: 前缀
            if re.match(r'^(doi|pmid|arxiv|DOI|PMID|ARXIV)\s*:', key):
                result.add(
                    Violation(
                        rule="R5.1",
                        line=i,
                        message=f"cite_key 包含标识符前缀：'[@{key}]'",
                        severity="error",
                        fix_hint=f"使用 search_papers 搜索文献标题获取 cite_key。cite_key 由工具自动生成（如 'aeW'、'HBc'），不包含 doi:/pmid: 等前缀",
                    )
                )
            # 禁止包含 /（DOI 特征）
            elif '/' in key:
                result.add(
                    Violation(
                        rule="R5.1",
                        line=i,
                        message=f"cite_key 疑似 DOI（包含/）：'[@{key}]'",
                        severity="error",
                        fix_hint="使用 get_paper_by_doi 查询该 DOI，从返回结果中获取 cite_key，替换为 [@cite_key] 格式",
                    )
                )
            # 禁止 .后跟数字（DOI 特征如 10.1234）
            elif re.search(r'\.\d', key):
                result.add(
                    Violation(
                        rule="R5.1",
                        line=i,
                        message=f"cite_key 疑似 DOI（包含数字编号）：'[@{key}]'",
                        severity="warning",
                        fix_hint="确认该标识符是否为 DOI。如果是，使用 get_paper_by_doi 查询获取 cite_key",
                    )
                )


# ── R5.2 待引证标记 ───────────────────────────────────────

def check_pending_citations(lines: list[str], result: VerifyResult) -> None:
    """R5.2 — 扫描 [待引证] 标记，报告数量和位置。"""
    pending_positions: list[int] = []
    in_code_block = False

    for i, line in enumerate(lines, 1):
        if is_code_block_start(line):
            in_code_block = not in_code_block
            continue
        if in_code_block:
            continue
        if '[待引证]' in line:
            pending_positions.append(i)

    if pending_positions:
        locations = ", ".join(f"L{p}" for p in pending_positions)
        result.add(
            Violation(
                rule="R5.2",
                line=pending_positions[0],
                message=f"发现 {len(pending_positions)} 处待引证标记：{locations}",
                severity="warning",
                fix_hint="使用 search_papers 搜索相关文献，获取 cite_key 后替换 [待引证] 为 [@cite_key]",
            )
        )


# ── R5.3 引用密度 ─────────────────────────────────────────

def check_citation_density(
    lines: list[str],
    result: VerifyResult,
    *,
    max_per_sentence: int = 2,
) -> None:
    """R5.3 — 检测同一句子内引用超过阈值的情况。

    max_per_sentence 通过 spec 配置注入，默认 2。
    """
    ref_start = find_ref_section_start(lines)
    in_code_block = False
    # 简单按句分割（中文句号/分号/问号/叹号，英文句号/问号/叹号）
    sentence_split_re = re.compile(r'[。；？！.?!]')

    for i, line in enumerate(lines, 1):
        if is_code_block_start(line):
            in_code_block = not in_code_block
            continue
        if in_code_block:
            continue
        if i - 1 >= ref_start:
            continue

        # 按句末标点分割
        sentences = sentence_split_re.split(line)
        for sentence in sentences:
            cite_keys = re.findall(r'@([^\]\s,;]+)', sentence)
            if len(cite_keys) > max_per_sentence:
                result.add(
                    Violation(
                        rule="R5.3",
                        line=i,
                        message=f"单句内引用 {len(cite_keys)} 篇文献（超过 {max_per_sentence} 篇），密度过高",
                        severity="warning",
                        fix_hint=f"单句引用超过 {max_per_sentence} 篇时建议精简或分散到上下文，避免堆砌引用",
                    )
                )


# ── R5.4 文献总量 ──────────────────────────────────────────

def check_total_reference_count(
    lines: list[str],
    result: VerifyResult,
    *,
    min_total: int = 20,
    max_total: int = 45,
) -> None:
    """R5.4 — 统计全文唯一 cite_key 数量并评估范围。"""
    unique_keys: set[str] = set()
    in_code_block = False

    for line in lines:
        if is_code_block_start(line):
            in_code_block = not in_code_block
            continue
        if in_code_block:
            continue
        for m in re.finditer(r'\[@([^\]]+)\]', line):
            # 支持多个 key：[@key1, key2] → 拆分
            raw = m.group(1)
            for part in raw.split(','):
                key = part.strip()
                if key:
                    unique_keys.add(key)

    count = len(unique_keys)
    if count == 0:
        result.add(
            Violation(
                rule="R5.4",
                line=0,
                message="全文未发现任何引用标记 [@cite_key]",
                severity="error",
                fix_hint="使用 search_papers 搜索相关文献，获取 cite_key 后使用 [@cite_key] 格式引用",
            )
        )
    elif count < min_total:
        result.add(
            Violation(
                rule="R5.4",
                line=0,
                message=f"全文仅引用 {count} 篇文献，偏少（建议 {min_total}-{max_total} 篇）",
                severity="warning",
                fix_hint="补充更多相关文献引用以增强论证支撑",
            )
        )
    elif count > max_total:
        result.add(
            Violation(
                rule="R5.4",
                line=0,
                message=f"全文引用 {count} 篇文献，偏多（建议 {min_total}-{max_total} 篇）",
                severity="warning",
                fix_hint="精简引用，保留最相关和最核心的文献",
            )
        )
    else:
        result.add(
            Violation(
                rule="R5.4",
                line=0,
                message=f"全文引用 {count} 篇文献，数量合理",
                severity="info",
            )
        )


# ── R6.1 引用位置 ─────────────────────────────────────────

def check_citation_position(lines: list[str], result: VerifyResult) -> None:
    """R6.1 — 引用标记应紧跟论点末尾、句末标点之前。

    检测 [@cite_key] 后是否紧跟句末标点（。；？！.?!），
    如果引用标记后是普通文字而非标点则报警。
    """
    in_code_block = False
    # 匹配 [@...] 后面紧跟的非空白字符
    cite_pattern = re.compile(r'\[@[^\]]+\]')

    for i, line in enumerate(lines, 1):
        if is_code_block_start(line):
            in_code_block = not in_code_block
            continue
        if in_code_block:
            continue

        for m in cite_pattern.finditer(line):
            end_pos = m.end()
            # 查看 cite 标记之后的内容
            rest = line[end_pos:].lstrip()
            if rest and rest[0] not in '。；？！.?!，,、：:）)】\n':
                # 如果下一个非空字符不是标点，则认为位置不当
                if not rest[0].isspace():
                    result.add(
                        Violation(
                            rule="R6.1",
                            line=i,
                            message=f"引用标记 '{m.group()}' 后紧跟非标点文本，位置不当",
                            severity="warning",
                            fix_hint="引用标记应紧跟论点末尾、句末标点之前。如'...具有重要意义[@aeW]。'而非'...具有重要意义[@aeW] 进一步研究...'",
                        )
                    )


# ── R6.2 多文献同引格式 ───────────────────────────────────

def check_multi_citation_format(lines: list[str], result: VerifyResult) -> None:
    """R6.2 — 检测连续的 ][@ 模式（应合并为一个标记）。"""
    in_code_block = False
    multi_cite_pattern = re.compile(r'\]\s*\[@')

    for i, line in enumerate(lines, 1):
        if is_code_block_start(line):
            in_code_block = not in_code_block
            continue
        if in_code_block:
            continue

        for m in multi_cite_pattern.finditer(line):
            result.add(
                Violation(
                    rule="R6.2",
                    line=i,
                    message=f"多个引用未合并：'{m.group()}' 应合并为一个标记",
                    severity="error",
                    fix_hint="将多个引用合并为一个标记：[@key1, key2] 而非 [@key1][@key2]",
                )
            )


# ── 导出 ──────────────────────────────────────────────────

ALL_CITATION_CHECKS = {
    "R5.1": check_citation_format,
    "R5.2": check_pending_citations,
    "R5.3": check_citation_density,
    "R5.4": check_total_reference_count,
    "R6.1": check_citation_position,
    "R6.2": check_multi_citation_format,
}
