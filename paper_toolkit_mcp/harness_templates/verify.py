#!/usr/bin/env python3
"""
学术论文格式自动化验证脚本
基于 .harness/rules.md 中定义的规则，对 Markdown 论文进行格式检查。

引用格式：使用 [@cite_key] 格式，cite_key 由 paper-toolkit 工具自动生成。
通过 search_papers、get_paper_by_doi 或 library_search 获取。

语言要求：全文必须使用中文撰写。

用法：
    python .harness/verify.py manuscript.md
    python .harness/verify.py manuscript.md --verbose
    python .harness/verify.py manuscript.md --rule R0.1 R5.1
"""

import sys
import argparse
from pathlib import Path
from typing import Optional
import functools

# ── 导入检查模块 ──────────────────────────────────────────
sys.path.insert(0, str(Path(__file__).parent))
from checks import VerifyResult, load_markdown
from checks.language import ALL_LANGUAGE_CHECKS
from checks.structure import ALL_STRUCTURE_CHECKS, check_total_word_count, check_paragraph_word_count, check_abstract_word_count
from checks.citations import ALL_CITATION_CHECKS, check_total_reference_count
from checks.data import ALL_DATA_CHECKS


# ── 合并所有检查 ──────────────────────────────────────────

def _build_all_checks(spec: dict) -> dict:
    """合并所有检查模块的规则，根据 spec 配置包装 R8 函数。"""
    all_checks = {}
    all_checks.update(ALL_DATA_CHECKS)
    all_checks.update(ALL_LANGUAGE_CHECKS)
    all_checks.update(ALL_CITATION_CHECKS)

    # structure 模块的 R8 函数需要配置参数
    wc = spec.get("word_count", {})
    all_checks["R1.1"] = ALL_STRUCTURE_CHECKS["R1.1"]
    all_checks["R1.2"] = ALL_STRUCTURE_CHECKS["R1.2"]

    # citations 模块的 R5.4 函数需要配置参数
    ct = spec.get("citations", {})
    all_checks["R5.4"] = functools.partial(
        check_total_reference_count,
        min_total=ct.get("min_total", 20),
        max_total=ct.get("max_total", 45),
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
        abstract_min=200,
        abstract_max=500,
    )
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
    """简单的 YAML 解析（仅支持单层键值对和嵌套2层）。"""
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

def verify(filepath: str, rules: Optional[list[str]] = None, verbose: bool = False) -> VerifyResult:
    lines = load_markdown(filepath)
    spec = _load_spec()
    all_checks = _build_all_checks(spec)
    result = VerifyResult()

    checks_to_run = rules if rules else list(all_checks.keys())
    seen_funcs = set()

    for rule_id in checks_to_run:
        func = all_checks.get(rule_id)
        if func is None:
            print(f"⚠️ 未知规则：{rule_id}")
            continue
        # 去重（多个规则ID可能共用同一函数）
        real_func = func.func if isinstance(func, functools.partial) else func
        if real_func in seen_funcs:
            continue
        seen_funcs.add(real_func)
        if verbose:
            print(f"🔍 检查 {rule_id}...")
        func(lines, result)
        result.total_checks += 1

    return result


def main():
    parser = argparse.ArgumentParser(description="学术论文格式自动化验证")
    parser.add_argument("filepath", help="Markdown 论文文件路径")
    parser.add_argument("--rule", nargs="*", dest="rules", help="指定检查规则（如 R0.1 R5.1）")
    parser.add_argument("--verbose", "-v", action="store_true", help="显示详细检查过程")
    parser.add_argument("--strict", action="store_true", help="严格模式：警告也视为错误")
    args = parser.parse_args()

    result = verify(args.filepath, args.rules, args.verbose)
    print(result.summary())

    if args.strict:
        exit_code = 1 if (result.errors or result.warnings) else 0
    else:
        exit_code = 1 if result.errors else 0

    sys.exit(exit_code)


if __name__ == "__main__":
    main()
