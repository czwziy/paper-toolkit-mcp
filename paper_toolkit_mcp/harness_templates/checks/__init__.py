# paper_toolkit_mcp/harness_templates/checks/
"""Harness 检查模块集合。

模块划分：
- language.py: R0 语言强制 + R4 语言行文 + R6 AI痕迹
- structure.py: R1 结构编号 + R3 章节 + R8 字数
- citations.py: R5 文献引用
- data.py: R2 数据格式
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional


# ── 共享数据结构 ──────────────────────────────────────────

@dataclass
class Violation:
    rule: str
    line: int
    message: str
    severity: str = "error"  # error | warning | info
    fix_hint: str = ""


@dataclass
class VerifyResult:
    total_checks: int = 0
    errors: list = field(default_factory=list)
    warnings: list = field(default_factory=list)
    infos: list = field(default_factory=list)

    def add(self, v: Violation):
        if v.severity == "error":
            self.errors.append(v)
        elif v.severity == "warning":
            self.warnings.append(v)
        else:
            self.infos.append(v)

    def summary(self) -> str:
        lines = [
            f"检查完成：共 {self.total_checks} 项检查",
            f"  错误：{len(self.errors)}",
            f"  警告：{len(self.warnings)}",
            f"  提示：{len(self.infos)}",
        ]
        if self.errors:
            lines.append("\n[ERROR] 错误详情：")
            for v in self.errors:
                lines.append(f"  [{v.rule}] L{v.line}: {v.message}")
                if v.fix_hint:
                    lines.append(f"    FIX: {v.fix_hint}")
        if self.warnings:
            lines.append("\n[WARN] 警告详情：")
            for v in self.warnings:
                lines.append(f"  [{v.rule}] L{v.line}: {v.message}")
                if v.fix_hint:
                    lines.append(f"    HINT: {v.fix_hint}")
        if self.infos:
            lines.append("\n[INFO] 提示详情：")
            for v in self.infos:
                lines.append(f"  [{v.rule}] L{v.line}: {v.message}")
        return "\n".join(lines)


# ── 共享辅助函数 ──────────────────────────────────────────

def is_code_block_start(line: str) -> bool:
    return line.strip().startswith("```")


def parse_heading(line: str) -> Optional[tuple[int, str]]:
    """解析标题行，返回 (层级, 标题文字)。"""
    m = re.match(r'^(#{1,6})\s+(.+)', line.strip())
    if not m:
        return None
    return len(m.group(1)), m.group(2)


def extract_heading_number(text: str) -> Optional[str]:
    """提取标题中的编号，如 '1', '2.1', '3.2.1' 等。"""
    m = re.match(r'^(\d+(?:\.\d+)*)\s*', text)
    return m.group(1) if m else None


def find_ref_section_start(lines: list[str]) -> int:
    """找到参考文献章节起始行索引。"""
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.lower().startswith('## references') or stripped.lower().startswith('## 参考文献'):
            return i
    return len(lines)


def count_chinese_chars(text: str) -> int:
    """统计中文字符数。"""
    return len(re.findall(r'[\u4e00-\u9fff]', text))


def count_words(text: str) -> int:
    """统计字数：中文字符每个算1字，英文单词算1字。"""
    cn = count_chinese_chars(text)
    # 去掉中文后统计英文单词
    no_cn = re.sub(r'[\u4e00-\u9fff]', ' ', text)
    en = len(re.findall(r'[a-zA-Z]+', no_cn))
    return cn + en


def load_markdown(filepath: str) -> list[str]:
    """加载 Markdown 文件，返回行列表。"""
    import sys
    from pathlib import Path
    path = Path(filepath)
    if not path.exists():
        print(f"[ERROR] 文件不存在：{filepath}")
        sys.exit(1)
    return path.read_text(encoding="utf-8").splitlines()
