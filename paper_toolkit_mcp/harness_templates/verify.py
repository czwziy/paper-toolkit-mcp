#!/usr/bin/env python3
"""
学术论文格式自动化验证脚本
基于 .harness/rules.md 中定义的规则，对 Markdown 论文进行格式检查。

引用格式：使用 [@cite_key] 格式，cite_key 由 paper-toolkit 工具自动生成。
通过 search_papers、get_paper_by_doi 或 library_search 获取。

语言要求：全文必须使用中文撰写。

用法：
    # 全量检查（默认，定稿阶段使用）
    python .harness/verify.py manuscript.md
    python .harness/verify.py manuscript.md --verbose
    python .harness/verify.py manuscript.md --rule R0.1 R5.1

    # 按模式检查
    python .harness/verify.py manuscript.md --mode chapter   # 子代理单章节
    python .harness/verify.py manuscript.md --mode draft     # 全文撰写中
    python .harness/verify.py manuscript.md --mode final     # 定稿（同默认）
"""

import sys
import argparse
from pathlib import Path
from typing import Optional
import functools
import io

# ── Windows 终端 UTF-8 兼容 ──────────────────────────────
# Windows 默认终端编码为 GBK，无法输出 emoji 等 Unicode 字符。
# 强制重新绑定 stdout/stderr 为 UTF-8 编码，确保跨平台兼容。
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

# ── 导入检查模块 ──────────────────────────────────────────
sys.path.insert(0, str(Path(__file__).parent))
from checks import VerifyResult, load_markdown
from checks.language import (
    ALL_LANGUAGE_CHECKS,
    check_humble_language,
    check_back_reference,
    _DEFAULT_BOAST_WORDS,
    _DEFAULT_BACK_REF_PATTERNS,
)
from checks.structure import (
    check_heading_hierarchy,
    check_heading_length,
    check_total_word_count,
    check_paragraph_word_count,
    check_abstract_word_count,
)
from checks.citations import (
    ALL_CITATION_CHECKS,
    check_total_reference_count,
    check_citation_density,
)
from checks.data import ALL_DATA_CHECKS


# ── 规则 scope 定义 ──────────────────────────────────────
# local: 子代理可独立检查的规则（不依赖全局统计）
# global: 仅全文合并后才有意义的规则

RULE_SCOPES: dict[str, str] = {
    # R0 语言
    "R0.1": "local",
    "R0.2": "local",
    # R1 结构
    "R1.1": "local",
    "R1.2": "local",
    "R1.3": "local",
    "R1.4": "local",
    # R2 数据
    "R2.1": "local",
    "R2.2": "local",
    "R2.3": "local",
    "R2.4": "local",
    "R2.5": "global",
    # R3 章节
    "R3.1": "global",
    # R4 行文
    "R4.1": "local",
    "R4.2": "local",
    # R5 引用
    "R5.1": "local",
    "R5.2": "local",
    "R5.3": "local",
    "R5.4": "global",
    # R6 引用格式
    "R6.1": "local",
    "R6.2": "local",
    "R6.3": "local",
    # R7 AI痕迹
    "R7.1": "local",
    "R7.2": "local",
    "R7.3": "local",
    # R8 字数与流程
    "R8.1": "global",
    "R8.2": "local",
    "R8.3": "global",
    "R8.6": "local",
    # R9 图表
    "R9.1": "local",
    "R9.2": "local",
    "R9.3": "global",
    "R9.4": "local",
    "R9.5": "local",
}

# draft 模式下跳过的规则（摘要/关键词/参考文献列表在定稿后才生成）
DRAFT_SKIP_RULES = {"R8.3", "R5.4"}


# ── 合并所有检查 ──────────────────────────────────────────

def _build_all_checks(spec: dict) -> dict:
    """合并所有检查模块的规则，根据 spec 配置包装需要参数的函数。"""
    all_checks = {}
    all_checks.update(ALL_DATA_CHECKS)
    all_checks.update(ALL_LANGUAGE_CHECKS)

    # ── citations 模块：需要参数注入的函数 ──
    ct = spec.get("citations", {})
    all_checks["R5.3"] = functools.partial(
        check_citation_density,
        max_per_sentence=ct.get("max_per_sentence", 2),
    )
    all_checks["R5.4"] = functools.partial(
        check_total_reference_count,
        min_total=ct.get("min_total", 20),
        max_total=ct.get("max_total", 45),
    )
    # R5.1, R5.2, R6.1, R6.2, R6.3 不需要参数，从 ALL_CITATION_CHECKS 复制
    for key in ("R5.1", "R5.2", "R6.1", "R6.2", "R6.3"):
        if key in ALL_CITATION_CHECKS:
            all_checks[key] = ALL_CITATION_CHECKS[key]

    # ── structure 模块：需要参数注入的函数 ──
    wc = spec.get("word_count", {})
    st = spec.get("structure", {})

    all_checks["R1.1"] = functools.partial(
        check_heading_hierarchy,
        heading_max_depth=st.get("heading_max_depth", 4),
    )
    all_checks["R1.2"] = functools.partial(
        check_heading_length,
        heading_max_length=st.get("heading_max_length", 15),
    )
    all_checks["R8.1"] = functools.partial(
        check_total_word_count,
        total_min=wc.get("total_min", 3000),
        total_max=wc.get("total_max", 8000),
    )
    all_checks["R8.2"] = functools.partial(
        check_paragraph_word_count,
        paragraph_min=wc.get("paragraph_min", 30),
        paragraph_max=wc.get("paragraph_max", 500),
    )
    all_checks["R8.3"] = functools.partial(
        check_abstract_word_count,
        abstract_min=wc.get("abstract_min", 200),
        abstract_max=wc.get("abstract_max", 500),
    )

    # ── language 模块：需要参数注入的函数 ──
    lang = spec.get("language", {})
    boast_words = lang.get("boast_words", _DEFAULT_BOAST_WORDS)
    back_ref_patterns = lang.get("back_reference_patterns", _DEFAULT_BACK_REF_PATTERNS)

    # R4.2 / R7.2 共用 check_humble_language，注入 boast_words
    all_checks["R4.2"] = functools.partial(
        check_humble_language,
        boast_words=boast_words,
    )
    all_checks["R7.2"] = functools.partial(
        check_humble_language,
        boast_words=boast_words,
    )
    # R7.3 注入 back_reference_patterns
    all_checks["R7.3"] = functools.partial(
        check_back_reference,
        back_reference_patterns=back_ref_patterns,
    )
    # R0.1, R0.2, R1.3, R1.4, R3.1, R4.1, R7.1, R8.6 不需要参数
    for key in ("R0.1", "R0.2", "R1.3", "R1.4", "R3.1", "R4.1", "R7.1", "R8.6"):
        if key in ALL_LANGUAGE_CHECKS:
            all_checks[key] = ALL_LANGUAGE_CHECKS[key]

    return all_checks


def _load_spec() -> dict:
    """加载 manuscript-spec.yaml 配置。"""
    spec_path = Path(__file__).parent / "specs" / "manuscript-spec.yaml"
    if not spec_path.exists():
        return {}
    try:
        import yaml
        with open(spec_path, encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except ImportError:
        # 无 PyYAML 时使用简单解析
        return _simple_yaml_parse(spec_path)


def _simple_yaml_parse(path: Path) -> dict:
    """简单的 YAML 解析（仅支持单层键值对和嵌套2层，不支持列表值）。"""
    result: dict = {}
    current_section: Optional[str] = None
    current_dict: dict = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if not line.startswith(" ") and ":" in stripped:
            if current_section and current_dict:
                result[current_section] = current_dict
                current_dict = {}
            current_section = stripped.split(":")[0].strip()
        elif line.startswith("  ") and ":" in stripped:
            key, _, val = stripped.partition(":")
            val = val.strip().strip('"').strip("'")
            try:
                val = int(val)
            except ValueError:
                try:
                    val = float(val)
                except ValueError:
                    pass
            current_dict[key.strip()] = val
    if current_section and current_dict:
        result[current_section] = current_dict
    return result


# ── 主流程 ────────────────────────────────────────────────

# 验证模式定义
# chapter: 子代理写单章节 — 只跑 local 规则 + 跳过定稿规则
# draft:   全文撰写中 — 跑所有规则但跳过定稿规则（R8.3/R5.4）
# final:   定稿验证 — 全量检查，不跳过任何规则
MODE_DEFINITIONS: dict[str, dict] = {
    "chapter": {"scope": "local", "skip_draft_rules": True},
    "draft":   {"scope": None,    "skip_draft_rules": True},
    "final":   {"scope": None,    "skip_draft_rules": False},
}


def verify(
    filepath: str,
    rules: Optional[list[str]] = None,
    verbose: bool = False,
    mode: Optional[str] = None,
) -> VerifyResult:
    """执行验证。

    Args:
        filepath: Markdown 文件路径
        rules: 指定检查规则列表
        verbose: 显示详细检查过程
        mode: 验证模式。
            "chapter" — 子代理单章节：只跑 local 规则，跳过定稿规则
            "draft"   — 全文撰写中：跑所有规则，但跳过定稿规则(R8.3/R5.4)
            "final"   — 定稿验证：全量检查
            None      — 从 spec 读取 mode.default
    """
    lines = load_markdown(filepath)
    spec = _load_spec()
    all_checks = _build_all_checks(spec)
    result = VerifyResult()

    # 确定验证模式
    if mode is None:
        mode_cfg = spec.get("mode", {})
        mode = mode_cfg.get("default", "draft")

    # 解析模式配置
    mode_def = MODE_DEFINITIONS.get(mode)
    if mode_def is None:
        print(f"[WARN] 未知模式：{mode}，可用模式：{list(MODE_DEFINITIONS.keys())}")
        mode_def = MODE_DEFINITIONS["draft"]

    scope_filter = mode_def["scope"]
    skip_draft_rules = mode_def["skip_draft_rules"]

    # 确定要运行的规则
    checks_to_run = rules if rules else list(all_checks.keys())

    # scope 过滤
    if scope_filter:
        checks_to_run = [r for r in checks_to_run if RULE_SCOPES.get(r) == scope_filter]

    # draft 规则过滤
    if skip_draft_rules:
        before = set(checks_to_run)
        checks_to_run = [r for r in checks_to_run if r not in DRAFT_SKIP_RULES]
        skipped = before - set(checks_to_run)
        if skipped and verbose:
            print(f"[INFO] 撰写模式：已跳过定稿规则 {sorted(skipped)}")

    seen_funcs = set()

    for rule_id in checks_to_run:
        func = all_checks.get(rule_id)
        if func is None:
            print(f"[WARN] 未知规则：{rule_id}")
            continue
        # 去重（多个规则ID可能共用同一函数）
        real_func = func.func if isinstance(func, functools.partial) else func
        if real_func in seen_funcs:
            continue
        seen_funcs.add(real_func)
        if verbose:
            print(f"[CHECK] 检查 {rule_id}...")
        func(lines, result)
        result.total_checks += 1

    return result


def main():
    parser = argparse.ArgumentParser(description="学术论文格式自动化验证")
    parser.add_argument("filepath", help="Markdown 论文文件路径")
    parser.add_argument("--rule", nargs="*", dest="rules", help="指定检查规则（如 R0.1 R5.1）")
    parser.add_argument("--verbose", "-v", action="store_true", help="显示详细检查过程")
    parser.add_argument("--strict", action="store_true", help="严格模式：警告也视为错误")
    parser.add_argument(
        "--mode",
        choices=list(MODE_DEFINITIONS.keys()),
        help="验证模式：chapter=子代理单章节(仅local规则)，draft=全文撰写中(跳过定稿规则)，final=定稿全量检查",
    )
    args = parser.parse_args()

    result = verify(args.filepath, args.rules, args.verbose, args.mode)
    print(result.summary())

    if args.strict:
        exit_code = 1 if (result.errors or result.warnings) else 0
    else:
        exit_code = 1 if result.errors else 0

    sys.exit(exit_code)


if __name__ == "__main__":
    main()
