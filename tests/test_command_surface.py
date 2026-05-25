import unittest
from pathlib import Path

from cli.app import app


REPO_ROOT = Path(__file__).resolve().parent.parent
EXPECTED_COMMANDS = {
    "check",
    "config",
    "creator",
    "fetch",
    "interactive",
    "monitor",
    "query",
}
EXPECTED_DOC_SNIPPETS = (
    "zhihu fetch",
    "zhihu creator",
    "zhihu monitor",
    "zhihu query",
    "zhihu interactive",
    "zhihu config",
    "zhihu check",
)


class CommandSurfaceTests(unittest.TestCase):
    def test_typer_registered_commands_match_expected_surface(self):
        registered = {command.name for command in app.registered_commands}
        registered.update({group.name for group in app.registered_groups})
        self.assertEqual(registered, EXPECTED_COMMANDS)



    def test_tui_use_execution_bridge_instead_of_cli_app_privates(self):
        runner_text = (REPO_ROOT / "cli" / "tui" / "runner.py").read_text(encoding="utf-8")

        self.assertIn("from cli.archive_execution import fetch_and_save_result", runner_text)
        self.assertNotIn("from cli.app import _fetch_and_save_result", runner_text)

    def test_launcher_marks_textual_as_default(self):
        launcher_text = (REPO_ROOT / "cli" / "launcher_flow.py").read_text(encoding="utf-8")

        self.assertIn("Textual TUI 归档工作台（推荐）", launcher_text)
        self.assertIn("`zhihu` 或 `zhihu interactive` 直达 Textual TUI", launcher_text)

    def test_cli_main_keeps_bare_entrypoint_on_textual_tui(self):
        app_text = (REPO_ROOT / "cli" / "app.py").read_text(encoding="utf-8")

        self.assertIn("if len(sys.argv) == 1:", app_text)
        self.assertIn("Bare `zhihu`", app_text)

    def test_cli_app_no_longer_keeps_dead_save_or_batch_helpers(self):
        app_text = (REPO_ROOT / "cli" / "app.py").read_text(encoding="utf-8")

        self.assertNotIn("def print_result(", app_text)
        self.assertNotIn("def build_output_folder_name(", app_text)
        self.assertNotIn("def resolve_entries_output_dir(", app_text)
        self.assertNotIn("def resolve_creator_output_dir(", app_text)
        self.assertNotIn("def _batch_concurrent(", app_text)

    def test_tui_runner_reuses_workflow_scrape_config_helper(self):
        runner_text = (REPO_ROOT / "cli" / "tui" / "runner.py").read_text(encoding="utf-8")

        self.assertIn("build_scrape_config_for_url", runner_text)
        self.assertNotIn("def _build_scrape_config(", runner_text)



    def test_query_surface_uses_content_key_label(self):
        app_text = (REPO_ROOT / "cli" / "app.py").read_text(encoding="utf-8")

        self.assertIn('table.add_column("Content Key"', app_text)
        self.assertNotIn('table.add_column("Zhihu ID"', app_text)


if __name__ == "__main__":
    unittest.main()
