"""MCP tools for harness initialization and management."""
from __future__ import annotations

import json
import os
import shutil


def register(mcp) -> None:
    """Register harness-related MCP tools."""

    @mcp.tool()
    def harness_init(
        project_dir: str = "",
        force: bool = False,
    ) -> str:
        """Initialize harness infrastructure for academic paper writing.

        Creates the following structure in the project directory:
        - CLAUDE.md: Project map for AI Agent (in project root)
        - .harness/: Harness directory containing:
          - rules.md: Writing rules (R0-R9)
          - verify.py: Automated verification script
          - checks/: Verification rule implementations
          - specs/manuscript-spec.yaml: Configurable standards
          - checklist.md: Manual review checklist
          - Harness.md: Usage guide

        Args:
            project_dir: Target project directory path. Defaults to current working directory.
            force: If True, overwrite existing .harness/ directory. Defaults to False.

        Returns:
            JSON string with initialization status and next steps.
        """
        # Find harness templates in package
        package_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        templates_dir = os.path.join(package_dir, "harness_templates")

        if not os.path.isdir(templates_dir):
            return json.dumps({
                "error": "Harness templates not found in package",
                "hint": "Please reinstall paper-toolkit-mcp package"
            }, indent=2)

        # Determine project directory
        if not project_dir:
            project_dir = os.getcwd()

        if not os.path.isdir(project_dir):
            return json.dumps({
                "error": f"Project directory not found: {project_dir}",
            }, indent=2)

        # --- Handle CLAUDE.md in project root ---
        claude_src = os.path.join(templates_dir, "CLAUDE.md")
        claude_dst = os.path.join(project_dir, "CLAUDE.md")
        claude_action: dict = {}

        if os.path.isfile(claude_dst):
            # CLAUDE.md already exists, save as backup and warn user
            backup_name = "CLAUDE.md.bak"
            backup_dst = os.path.join(project_dir, backup_name)
            counter = 1
            while os.path.exists(backup_dst):
                counter += 1
                backup_name = f"CLAUDE.md.bak.{counter}"
                backup_dst = os.path.join(project_dir, backup_name)
            shutil.copy2(claude_dst, backup_dst)
            claude_action = {
                "file": "CLAUDE.md",
                "status": "backup_created",
                "backup": backup_name,
                "hint": (
                    f"CLAUDE.md already exists. Backup saved as {backup_name}. "
                    "Please manually merge the template into your existing CLAUDE.md."
                ),
            }
        else:
            # Copy CLAUDE.md template to project root
            shutil.copy2(claude_src, claude_dst)
            claude_action = {"file": "CLAUDE.md", "status": "created"}

        # --- Handle .harness/ directory ---
        target = os.path.join(project_dir, ".harness")

        if os.path.isdir(target) and not force:
            existing = []
            for root, _dirs, files in os.walk(target):
                for f in files:
                    existing.append(os.path.relpath(os.path.join(root, f), target))
            result = {
                "status": "partial",
                "claude_md": claude_action,
                "harness_dir": {
                    "status": "already_exists",
                    "target_dir": target,
                    "existing_files": existing,
                    "hint": "Use force=True to overwrite .harness/",
                },
                "next_steps": [
                    "Review and edit CLAUDE.md in project root (fill in {PROJECT_NAME} and {PROJECT_DESCRIPTION})",
                    "Review and edit .harness/specs/manuscript-spec.yaml for your paper",
                    "Run: python .harness/verify.py <your_manuscript.md>",
                ],
            }
            return json.dumps(result, indent=2, ensure_ascii=False)

        # Copy harness templates
        harness_actions = _copy_tree(templates_dir, target, force=force)
        # Filter out CLAUDE.md from harness_actions since we handled it separately
        harness_actions = [a for a in harness_actions if a.get("file") != "CLAUDE.md"]

        result = {
            "status": "initialized",
            "claude_md": claude_action,
            "harness_dir": {
                "target_dir": target,
                "files": harness_actions,
            },
            "next_steps": [
                "Review and edit CLAUDE.md in project root (fill in {PROJECT_NAME} and {PROJECT_DESCRIPTION})",
                "Review and edit .harness/specs/manuscript-spec.yaml for your paper",
                "Run: python .harness/verify.py <your_manuscript.md>",
            ],
        }
        return json.dumps(result, indent=2, ensure_ascii=False)

    @mcp.tool()
    def harness_verify(
        manuscript_path: str,
        verbose: bool = False,
    ) -> str:
        """Verify a manuscript against harness rules.

        Runs the harness verification script on the specified manuscript file
        and returns a JSON report of violations, warnings, and info messages.

        Args:
            manuscript_path: Path to the manuscript markdown file.
            verbose: If True, include detailed violation information. Defaults to False.

        Returns:
            JSON string with verification results including error count, warning count,
            and detailed violation information.
        """
        # Find verify.py in .harness directory
        manuscript_dir = os.path.dirname(os.path.abspath(manuscript_path))
        project_dir = _find_project_root(manuscript_dir)
        verify_script = os.path.join(project_dir, ".harness", "verify.py")

        if not os.path.isfile(verify_script):
            return json.dumps({
                "error": "verify.py not found in .harness/ directory",
                "hint": "Run harness_init first to initialize harness infrastructure",
                "searched_in": verify_script,
            }, indent=2)

        if not os.path.isfile(manuscript_path):
            return json.dumps({
                "error": f"Manuscript file not found: {manuscript_path}",
            }, indent=2)

        # Import and run verification
        import subprocess
        import sys

        cmd = [sys.executable, verify_script, manuscript_path]
        if verbose:
            cmd.append("--verbose")

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                cwd=project_dir,
                timeout=60,
            )
            return json.dumps({
                "exit_code": result.returncode,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "passed": result.returncode == 0,
            }, indent=2, ensure_ascii=False)
        except subprocess.TimeoutExpired:
            return json.dumps({
                "error": "Verification timed out (60 seconds)",
            }, indent=2)
        except Exception as e:
            return json.dumps({
                "error": f"Verification failed: {str(e)}",
            }, indent=2)

    @mcp.tool()
    def harness_list_rules() -> str:
        """List all harness rules with their descriptions.

        Returns a summary of all verification rules (R0-R9) including
        rule ID, name, severity, scope, and brief description.

        Scope:
        - "local": Rules that can be checked on a single chapter/section
          by a sub-agent independently (e.g., language, format).
        - "global": Rules that only make sense when checking the full
          merged manuscript (e.g., total word count, total references).

        Draft mode:
        - In draft mode (writing phase), rules for abstract word count (R8.3)
          and total reference count (R5.4) are skipped, since abstracts and
          reference lists are generated after the manuscript is finalized.

        Returns:
            JSON string with list of all rules.
        """
        rules = [
            {"id": "R0.1", "name": "全文语言中文", "severity": "error", "scope": "local", "desc": "全文必须使用中文撰写"},
            {"id": "R0.2", "name": "标题语言中文", "severity": "error", "scope": "local", "desc": "标题必须使用中文"},
            {"id": "R1.1", "name": "标题层级", "severity": "error", "scope": "local", "desc": "采用阿拉伯数字层级法，不超过4级"},
            {"id": "R1.2", "name": "标题长度", "severity": "warning", "scope": "local", "desc": "标题不超过15字"},
            {"id": "R1.3", "name": "禁止列表", "severity": "error", "scope": "local", "desc": "正文中禁止使用列表格式"},
            {"id": "R1.4", "name": "禁止加粗", "severity": "error", "scope": "local", "desc": "正文中禁止使用加粗标记"},
            {"id": "R2.1", "name": "P值格式", "severity": "error", "scope": "local", "desc": "P值须符合规范格式"},
            {"id": "R2.2", "name": "均值标准差", "severity": "warning", "scope": "local", "desc": "均值与标准差小数位一致"},
            {"id": "R2.3", "name": "推断统计量", "severity": "error", "scope": "local", "desc": "t/F/χ²/r等保留2位小数"},
            {"id": "R2.4", "name": "百分率", "severity": "error", "scope": "local", "desc": "百分率格式规范"},
            {"id": "R2.5", "name": "数据一致性", "severity": "warning", "scope": "global", "desc": "摘要、正文、表格数值一致"},
            {"id": "R3.1", "name": "必备章节", "severity": "error", "scope": "global", "desc": "须包含引言、方法、结果、讨论、结论"},
            {"id": "R4.1", "name": "术语缩写", "severity": "warning", "scope": "local", "desc": "术语统一，首次出现时定义缩写"},
            {"id": "R4.2", "name": "行文谦逊", "severity": "error", "scope": "local", "desc": "禁用'首次证实''颠覆性'等词汇"},
            {"id": "R5.1", "name": "引用格式", "severity": "error", "scope": "local", "desc": "使用[@cite_key]格式"},
            {"id": "R5.2", "name": "待引证标记", "severity": "warning", "scope": "local", "desc": "无文献支撑时使用[待引证]"},
            {"id": "R5.3", "name": "引用密度", "severity": "warning", "scope": "local", "desc": "单句引用不超过指定篇数"},
            {"id": "R5.4", "name": "文献总量", "severity": "warning", "scope": "global", "draft_skip": True, "desc": "全文引用30-45篇文献（定稿阶段生效）"},
            {"id": "R6.1", "name": "引用位置", "severity": "error", "scope": "local", "desc": "引用标记紧跟句末标点之前"},
            {"id": "R6.2", "name": "多文献同引", "severity": "error", "scope": "local", "desc": "使用[@id1, id2]格式"},
            {"id": "R7.1", "name": "标题冒号", "severity": "error", "scope": "local", "desc": "标题中不使用冒号"},
            {"id": "R7.2", "name": "自我夸大", "severity": "error", "scope": "local", "desc": "禁用夸大词汇"},
            {"id": "R7.3", "name": "回引", "severity": "error", "scope": "local", "desc": "禁止'见本文X.X节'"},
            {"id": "R7.4", "name": "用户意见", "severity": "warning", "scope": "local", "desc": "处理【】中的用户意见"},
            {"id": "R8.1", "name": "全文字数", "severity": "warning", "scope": "global", "desc": "全文3000-8000字"},
            {"id": "R8.2", "name": "段落字数", "severity": "warning", "scope": "local", "desc": "段落30-500字"},
            {"id": "R8.3", "name": "摘要字数", "severity": "warning", "scope": "global", "draft_skip": True, "desc": "摘要200-500字（定稿阶段生效）"},
            {"id": "R9.1", "name": "表格结构", "severity": "warning", "scope": "local", "desc": "三线表，无竖线"},
            {"id": "R9.2", "name": "表格数据", "severity": "warning", "scope": "local", "desc": "数据格式规范"},
            {"id": "R9.3", "name": "表格一致性", "severity": "warning", "scope": "global", "desc": "表格与正文数值一致"},
            {"id": "R9.4", "name": "图片质量", "severity": "warning", "scope": "local", "desc": "分辨率≥300dpi"},
            {"id": "R9.5", "name": "图片编号", "severity": "warning", "scope": "local", "desc": "按顺序编号，先文后图"},
        ]
        return json.dumps({
            "total_rules": len(rules),
            "rules": rules,
            "scope_legend": {
                "local": "子代理可独立检查（不依赖全局统计）",
                "global": "仅全文合并后检查（依赖全局统计）",
            },
            "draft_skip_note": "draft_skip=True 的规则在 --mode chapter/draft 下跳过，--mode final 下执行",
        }, indent=2, ensure_ascii=False)


def _copy_tree(src: str, dst: str, *, force: bool = False) -> list[dict]:
    """Recursively copy *src* into *dst*, returning a manifest of actions."""
    actions: list[dict] = []
    for root, _dirs, files in os.walk(src):
        rel = os.path.relpath(root, src)
        target_dir = os.path.join(dst, rel) if rel != "." else dst
        for fname in files:
            src_file = os.path.join(root, fname)
            dst_file = os.path.join(target_dir, fname)
            if os.path.exists(dst_file) and not force:
                actions.append({"file": os.path.relpath(dst_file, dst), "status": "skipped"})
                continue
            os.makedirs(target_dir, exist_ok=True)
            shutil.copy2(src_file, dst_file)
            actions.append({"file": os.path.relpath(dst_file, dst), "status": "created"})
    return actions


def _find_project_root(start_path: str) -> str:
    """Find project root by looking for .harness directory."""
    current = os.path.abspath(start_path)
    for _ in range(10):  # Limit search depth
        if os.path.isdir(os.path.join(current, ".harness")):
            return current
        parent = os.path.dirname(current)
        if parent == current:
            break
        current = parent
    return start_path
