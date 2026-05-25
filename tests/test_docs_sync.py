import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent


import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent


class DocsSyncTests(unittest.TestCase):
    def test_readmes_keep_textual_tui_wording(self):
        readme_cn = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
        readme_en = (REPO_ROOT / "README_EN.md").read_text(encoding="utf-8")

        self.assertIn("Textual TUI", readme_cn)
        self.assertIn("Textual TUI", readme_en)
        self.assertIn("全屏工作台", readme_cn)
        self.assertIn("full-screen workbench", readme_en)
        self.assertIn("协议优先", readme_cn)
        self.assertIn("protocol-first", readme_en)

    def test_governance_docs_reference_constitution(self):
        agents_text = (REPO_ROOT / "AGENTS.md").read_text(encoding="utf-8")

        self.assertTrue((REPO_ROOT / "CONSTITUTION.md").exists())
        self.assertIn("CONSTITUTION.md", agents_text)
        self.assertIn("tests.test_docs_sync", agents_text)
        self.assertIn("tests.test_command_surface", agents_text)


if __name__ == "__main__":
    unittest.main()

