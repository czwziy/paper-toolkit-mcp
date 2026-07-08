"""Pandoc helper module for converting Markdown to Word documents."""

import os
import shutil
import subprocess


def pandoc_available() -> bool:
    """Check if pandoc is installed and available.

    Returns:
        True if pandoc is available, False otherwise.
    """
    return shutil.which("pandoc") is not None


def convert_to_docx(
    markdown_path: str,
    output_path: str,
    bib_path: str | None = None,
    csl_file: str | None = None,
    metadata: dict | None = None,
) -> dict:
    """Convert a Markdown file to Word (.docx) using pandoc.

    Args:
        markdown_path: Path to input Markdown file.
        output_path: Path to output Word file.
        bib_path: Optional path to BibTeX bibliography file.
        csl_file: Optional path to CSL style file.
        metadata: Optional dict of metadata (title, author, etc.).

    Returns:
        Dict with 'success' boolean and optional 'error' message.
    """
    if not os.path.exists(markdown_path):
        return {"success": False, "error": f"Input file not found: {markdown_path}"}

    cmd = ["pandoc", markdown_path, "-o", output_path]

    if bib_path:
        cmd.extend(["--bibliography", bib_path])
        cmd.append("--citeproc")

    if csl_file and os.path.exists(csl_file):
        cmd.extend(["--csl", csl_file])

    if metadata:
        for key, value in metadata.items():
            cmd.extend(["--metadata", f"{key}={value}"])

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=60,
        )

        if result.returncode == 0:
            return {"success": True, "output": output_path}
        else:
            return {
                "success": False,
                "error": result.stderr.strip() or "Unknown pandoc error",
            }
    except subprocess.TimeoutExpired:
        return {"success": False, "error": "Pandoc conversion timed out"}
    except FileNotFoundError:
        return {"success": False, "error": "pandoc is not installed"}
    except Exception as e:
        return {"success": False, "error": str(e)}
