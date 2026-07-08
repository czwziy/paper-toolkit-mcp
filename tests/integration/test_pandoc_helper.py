# tests/test_pandoc_helper.py
import unittest

from paper_toolkit_mcp.pandoc_helper import convert_to_docx, pandoc_available


class TestPandocHelper(unittest.TestCase):
    def test_pandoc_available_returns_bool(self):
        """Test that pandoc_available returns a boolean."""
        result = pandoc_available()
        self.assertIsInstance(result, bool)

    @unittest.skipIf(not pandoc_available(), "pandoc not installed")
    def test_convert_to_docx_success(self):
        """Test successful conversion with pandoc installed."""
        import os
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            md_path = os.path.join(tmpdir, "test.md")
            docx_path = os.path.join(tmpdir, "test.docx")

            with open(md_path, "w", encoding="utf-8") as f:
                f.write("# Test\n\nThis is a test document.")

            result = convert_to_docx(md_path, docx_path)

            self.assertTrue(result["success"])
            self.assertTrue(os.path.exists(docx_path))

    def test_convert_nonexistent_file(self):
        """Test conversion with non-existent input file."""
        result = convert_to_docx("/nonexistent/file.md", "/tmp/output.docx")
        self.assertFalse(result["success"])
        self.assertIn("error", result)


if __name__ == "__main__":
    unittest.main()
