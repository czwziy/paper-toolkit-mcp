"""MCP tools for harness initialization."""
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
          - verifier_models.json: Citation verification model config
          - Harness.md: Usage guide

        After initialization, users should run verification commands
        directly in the terminal (see CLAUDE.md for details), not via MCP.

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

        # Generate verifier_models.json template if not already present
        verifier_config_path = os.path.join(target, "verifier_models.json")
        if not os.path.isfile(verifier_config_path):
            from ..verifier import write_default_config

            write_default_config(verifier_config_path)
            harness_actions.append({"file": "verifier_models.json", "status": "created"})

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
                "Edit .harness/verifier_models.json to configure citation verification models (at least 2 models recommended)",
                "Run: python .harness/verify.py <your_manuscript.md>",
            ],
        }
        return json.dumps(result, indent=2, ensure_ascii=False)


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

