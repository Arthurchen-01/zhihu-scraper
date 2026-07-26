import unittest
from pathlib import Path

import tomllib


REPO_ROOT = Path(__file__).resolve().parent.parent


class InstallContractTests(unittest.TestCase):
    def test_pyproject_exposes_expected_console_entrypoint(self):
        pyproject = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
        scripts = pyproject["project"]["scripts"]
        self.assertEqual(scripts["zhihu"], "cli.app:main")

    def test_pyproject_does_not_offer_removed_openai_translation(self):
        pyproject = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
        optional_dependencies = pyproject["project"]["optional-dependencies"]

        self.assertNotIn("translate", optional_dependencies)
        all_dependencies = [
            dependency
            for dependencies in optional_dependencies.values()
            for dependency in dependencies
        ]
        self.assertFalse(any(dependency.startswith("openai") for dependency in all_dependencies))

    def test_install_script_keeps_editable_full_install_and_runtime_init(self):
        install_script = (REPO_ROOT / "install.sh").read_text(encoding="utf-8")
        self.assertIn('pip install -e ".[full]"', install_script)
        self.assertIn('cli/app.py check', install_script)
        self.assertIn('install_global_launcher', install_script)
        self.assertIn('.local/cookies.json', install_script)
        self.assertIn('sys.version_info >= (3, 14)', install_script)
        self.assertNotIn('cli/app.py check || true', install_script)
        self.assertNotIn('zhihu manual', install_script)
        self.assertNotIn('cli/app.py manual', install_script)
        self.assertIn("zhihu fetch", install_script)
        self.assertIn('cli/app.py --help', install_script)
        self.assertNotIn("cookie_pool", install_script)
        self.assertNotIn("zhihu interactive", install_script)

    def test_ci_workflow_matches_documented_validation_baseline(self):
        workflow = (REPO_ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")

        expected_unittest = (
            "python -m unittest -q tests.test_cli_compat tests.test_docs_sync "
            "tests.test_command_surface tests.test_save_pipeline "
            "tests.test_save_contracts tests.test_config_view tests.test_scraper_payloads "
            "tests.test_scraper_contracts tests.test_config_schema tests.test_config_runtime "
            "tests.test_install_contract tests.test_workflow_service tests.test_db_contract "
            "tests.test_public_facade"
        )

        self.assertIn("pip install -e .", workflow)
        self.assertIn(expected_unittest, workflow)
        self.assertNotIn("python -m pytest tests/", workflow)
        self.assertNotIn("pip-audit", workflow)


if __name__ == "__main__":
    unittest.main()
