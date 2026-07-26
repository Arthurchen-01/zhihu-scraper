import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent


class DocsSyncTests(unittest.TestCase):
    def test_readmes_keep_cli_only_wording(self):
        readme_cn = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
        readme_en = (REPO_ROOT / "README_EN.md").read_text(encoding="utf-8")

        self.assertIn("CLI", readme_cn)
        self.assertIn("CLI", readme_en)
        self.assertIn("协议优先", readme_cn)
        self.assertIn("protocol-first", readme_en)
        self.assertNotIn("Textual TUI", readme_cn)
        self.assertNotIn("Textual TUI", readme_en)

    def test_repository_uses_the_small_governance_set(self):
        agents_text = (REPO_ROOT / "AGENTS.md").read_text(encoding="utf-8")

        self.assertTrue((REPO_ROOT / "AGENTS.md").exists())
        self.assertTrue((REPO_ROOT / "docs" / "ARCHITECTURE.md").exists())
        self.assertTrue((REPO_ROOT / "docs" / "FEATURE_TODO.md").exists())
        self.assertFalse((REPO_ROOT / "CONSTITUTION.md").exists())
        self.assertFalse((REPO_ROOT / "docs" / "TENCENT_QINGYUN_DEMO.md").exists())
        self.assertFalse((REPO_ROOT / "docs" / "agent-skills").exists())
        self.assertFalse((REPO_ROOT / "docs" / "PROJECT_CONVERGENCE_REPORT.md").exists())
        self.assertIn("docs/ARCHITECTURE.md", agents_text)
        self.assertIn("docs/FEATURE_TODO.md", agents_text)
        self.assertNotIn("maintenance freeze", agents_text.lower())


if __name__ == "__main__":
    unittest.main()
