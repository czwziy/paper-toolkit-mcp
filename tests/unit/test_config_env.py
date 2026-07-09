import os
import shutil
import tempfile
import unittest
from unittest.mock import patch

from paper_toolkit_mcp import config


class TestConfigEnv(unittest.TestCase):
    def test_prefixed_env_has_priority_over_legacy(self):
        with patch.dict(
            os.environ,
            {
                "paper_toolkit_mcp_ENV_FILE": "/tmp/paper-toolkit-mcp-missing.env",
                "paper_toolkit_mcp_CORE_API_KEY": "prefixed-value",
                "CORE_API_KEY": "legacy-value",
            },
            clear=True,
        ):
            self.assertEqual(config.get_env("CORE_API_KEY", ""), "prefixed-value")

    def test_legacy_env_fallback_still_works(self):
        with patch.dict(
            os.environ,
            {
                "paper_toolkit_mcp_ENV_FILE": "/tmp/paper-toolkit-mcp-missing.env",
                "CORE_API_KEY": "legacy-value",
            },
            clear=True,
        ):
            self.assertEqual(config.get_env("CORE_API_KEY", ""), "legacy-value")

    def test_empty_prefixed_value_blocks_legacy_fallback(self):
        with patch.dict(
            os.environ,
            {
                "paper_toolkit_mcp_ENV_FILE": "/tmp/paper-toolkit-mcp-missing.env",
                "paper_toolkit_mcp_CORE_API_KEY": "",
                "CORE_API_KEY": "legacy-value",
            },
            clear=True,
        ):
            self.assertEqual(config.get_env("CORE_API_KEY", "default"), "")

    def test_loads_from_custom_env_file(self):
        # Write to a temp dir and CLOSE the file before load_env_file reads it.
        # NamedTemporaryFile(delete=True) keeps the handle open on Windows,
        # which locks the file and causes PermissionError when load_env_file
        # reopens it for reading.
        tmpdir = tempfile.mkdtemp()
        try:
            env_path = os.path.join(tmpdir, "custom.env")
            with open(env_path, "w", encoding="utf-8") as f:
                f.write("paper_toolkit_mcp_UNPAYWALL_EMAIL=test@example.com\n")

            with patch.dict(
                os.environ,
                {
                    "paper_toolkit_mcp_ENV_FILE": env_path,
                },
                clear=True,
            ):
                config.load_env_file(force=True)
                self.assertEqual(config.get_env("UNPAYWALL_EMAIL", ""), "test@example.com")
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
