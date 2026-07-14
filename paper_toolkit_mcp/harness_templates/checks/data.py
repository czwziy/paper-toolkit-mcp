"""R2 数据格式检查模块。

检查项：
- R2.1  P值格式
- R2.2  均值±标准差格式
- R2.3  推断统计量小数位
- R2.4  百分率格式
- R2.5  数据一致性
"""

from __future__ import annotations

import re

from . import (
    Violation,
    VerifyResult,
    is_code_block_start,
)


# ── R2.1 P值格式 ──────────────────────────────────────────

def check_p_value_format(lines: list[str], result: VerifyResult) -> None:
    """R2.1 — 检查P值格式。

    1. 小写 p= → error "P值应大写"
    2. P=0.000x → error "P值极小应报告为P<0.001"
    3. 0.001≤P<0.01 时小数位 > 3 → error
    注意：不再强制 P≥0.01 时保留2位小数（英文期刊允许3位）
    """
    in_code_block = False

    for i, line in enumerate(lines, 1):
        if is_code_block_start(line):
            in_code_block = not in_code_block
            continue
        if in_code_block:
            continue

        # 检查小写 p
        for m in re.finditer(r'(?<![A-Za-z])p\s*([=<>])', line):
            result.add(Violation(
                rule="R2.1", line=i,
                message=f"P值应大写：'p{m.group(1)}'",
                severity="error",
                fix_hint="将p改为大写P",
            ))

        # 检查 P=0.000x
        for m in re.finditer(r'P\s*=\s*(0\.0{3,}\d+)', line):
            result.add(Violation(
                rule="R2.1", line=i,
                message=f"P值极小应报告为P<0.001：'P={m.group(1)}'",
                severity="error",
                fix_hint="改为P<0.001",
            ))

        # 0.001≤P<0.01 时小数位 > 3 → error
        for m in re.finditer(r'P\s*=\s*(0\.00[1-9]\d*)', line):
            val = m.group(1)
            decimal_part = val.split('.')[1]
            if len(decimal_part) > 3 and 0.001 <= float(val) < 0.01:
                result.add(Violation(
                    rule="R2.1", line=i,
                    message=f"0.001≤P<0.01应保留3位小数：'P={val}'",
                    severity="error",
                    fix_hint=f"改为P={round(float(val), 3)}",
                ))


# ── R2.2 均值±标准差格式 ──────────────────────────────────

def check_mean_sd_format(lines: list[str], result: VerifyResult) -> None:
    """R2.2 — 检查均值±标准差格式。

    匹配 数值±数值 模式，检查小数位一致性。
    """
    in_code_block = False

    for i, line in enumerate(lines, 1):
        if is_code_block_start(line):
            in_code_block = not in_code_block
            continue
        if in_code_block:
            continue

        for m in re.finditer(r'(\d+\.\d+)\s*[±]\s*(\d+\.\d+)', line):
            mean_dec = len(m.group(1).split('.')[1])
            sd_dec = len(m.group(2).split('.')[1])
            if mean_dec != sd_dec:
                result.add(Violation(
                    rule="R2.2", line=i,
                    message=f"均值与标准差小数位不一致：'{m.group(0)}'",
                    severity="error",
                    fix_hint="标准差小数位须与均值一致",
                ))


# ── R2.3 推断统计量小数位 ─────────────────────────────────

def check_statistic_format(lines: list[str], result: VerifyResult) -> None:
    """R2.3 — 检查推断统计量小数位。

    χ²=xx.x 须保留2位小数；Cramér's V 须保留2位小数。
    """
    in_code_block = False

    for i, line in enumerate(lines, 1):
        if is_code_block_start(line):
            in_code_block = not in_code_block
            continue
        if in_code_block:
            continue

        # χ²=xx.x 格式检查
        for m in re.finditer(r'χ²\s*=\s*(\d+\.\d+)', line):
            dec = len(m.group(1).split('.')[1])
            if dec != 2:
                result.add(Violation(
                    rule="R2.3", line=i,
                    message=f"χ²应保留2位小数：'χ²={m.group(1)}'",
                    severity="error",
                    fix_hint=f"改为χ²={float(m.group(1)):.2f}",
                ))

        # Cramér's V 检查
        for m in re.finditer(r"V\s*=\s*(\d+\.\d+)", line):
            if "Cramér" in line or "cramér" in line.lower():
                dec = len(m.group(1).split('.')[1])
                if dec != 2:
                    result.add(Violation(
                        rule="R2.3", line=i,
                        message=f"Cramér's V应保留2位小数：'{m.group(1)}'",
                        severity="error",
                        fix_hint=f"改为V={float(m.group(1)):.2f}",
                    ))


# ── R2.4 百分率格式 ───────────────────────────────────────

def check_percentage_format(lines: list[str], result: VerifyResult) -> None:
    """R2.4 — 检查百分率格式。

    表格数据行中 % → warning "应提取到表头"；正文中百分率小数位 > 2 → error。
    """
    in_code_block = False

    for i, line in enumerate(lines, 1):
        if is_code_block_start(line):
            in_code_block = not in_code_block
            continue
        if in_code_block:
            continue

        stripped = line.strip()

        # 检测表格行
        if stripped.startswith("|") and stripped.endswith("|"):
            # 跳过分隔行（|---|---|）
            if re.match(r'^\|[\s\-:|]+\|$', stripped):
                continue
            cells = [c.strip() for c in stripped.split("|")[1:-1]]
            # 表头行允许包含 %
            is_header = (
                any(re.search(r'[\u4e00-\u9fff]', c) for c in cells)
                and not any(re.match(r'^\d+\.?\d*（', c) for c in cells)
            )
            if is_header:
                continue
            # 数据行中包含 % → warning
            cells_with_pct = [c for c in cells if "%" in c]
            if cells_with_pct:
                result.add(Violation(
                    rule="R2.4", line=i,
                    message=f"表格数据单元格中包含%符号，应提取到表头统一标注：'{cells_with_pct[0][:30]}'",
                    severity="warning",
                    fix_hint="在表头/列标题中标注（%），单元格内只写数值",
                ))

        # 正文中小数位 > 2 → error
        if not stripped.startswith("|"):
            for m in re.finditer(r'(\d+(?:\.\d+)?)%', stripped):
                pct_str = m.group(1)
                if "." in pct_str:
                    dec = len(pct_str.split(".")[1])
                    if dec > 2:
                        result.add(Violation(
                            rule="R2.4", line=i,
                            message=f"百分率小数位超过2位：'{m.group(0)}'",
                            severity="error",
                            fix_hint="百分率保留1~2位小数",
                        ))


# ── R2.5 数据一致性 ───────────────────────────────────────

def check_data_consistency(lines: list[str], result: VerifyResult) -> None:
    """R2.5 — 检查摘要与正文关键数值一致性。

    提取摘要和正文中的 M1-M4 数值，交叉比对。
    """
    full_text = "\n".join(lines)

    # 提取摘要区域
    abstract_match = re.search(
        r'\*\*摘要\*\*\s*\n(.*?)(?=\n---|\n\*\*关键词\*\*|\n## )',
        full_text,
        re.DOTALL,
    )
    if not abstract_match:
        return

    abstract = abstract_match.group(1)
    body_start = abstract_match.end()
    body = full_text[body_start:]

    # 检查 M1-M4 数值
    metrics = ["M1", "M2", "M3", "M4"]
    for metric_name in metrics:
        abstract_vals = re.findall(
            rf'{metric_name}[为是]?\s*(\d+\.\d+)%', abstract,
        )
        body_vals = re.findall(
            rf'{metric_name}[为是]?\s*(\d+\.\d+)%', body,
        )
        if abstract_vals and body_vals:
            if abstract_vals[0] != body_vals[0]:
                result.add(Violation(
                    rule="R2.5", line=0,
                    message=(
                        f"{metric_name}数值不一致：摘要={abstract_vals[0]}%，"
                        f"正文={body_vals[0]}%"
                    ),
                    severity="error",
                    fix_hint="确保同一指标在摘要和正文中数值完全一致",
                ))


# ── 导出 ──────────────────────────────────────────────────

ALL_DATA_CHECKS = {
    "R2.1": check_p_value_format,
    "R2.2": check_mean_sd_format,
    "R2.3": check_statistic_format,
    "R2.4": check_percentage_format,
    "R2.5": check_data_consistency,
}
