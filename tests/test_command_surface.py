import unittest
from pathlib import Path

from cli.app import app


REPO_ROOT = Path(__file__).resolve().parent.parent
EXPECTED_COMMANDS = {
    "check",
    "config",
    "fetch",
    "query",
}
EXPECTED_DOC_SNIPPETS = (
    "zhihu fetch",
    "zhihu query",
    "zhihu config",
    "zhihu check",
)


class CommandSurfaceTests(unittest.TestCase):
    def test_typer_registered_commands_match_expected_surface(self):
        registered = {command.name for command in app.registered_commands}
        registered.update({group.name for group in app.registered_groups})
        self.assertEqual(registered, EXPECTED_COMMANDS)

    def test_readmes_document_current_command_surface(self):
        readme_cn = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
        readme_en = (REPO_ROOT / "README_EN.md").read_text(encoding="utf-8")
        data_readme = (REPO_ROOT / "data" / "README.md").read_text(encoding="utf-8")

        for snippet in EXPECTED_DOC_SNIPPETS:
            self.assertIn(snippet, readme_cn)
            self.assertIn(snippet, readme_en)

        self.assertIn("zhihu fetch --file", readme_cn)
        self.assertIn("zhihu fetch --file", readme_en)
        self.assertNotIn("zhihu batch", readme_cn)
        self.assertNotIn("zhihu batch", readme_en)
        self.assertIn("fetch --file", data_readme)
        self.assertNotIn("creator", data_readme)
        self.assertNotIn("monitor", data_readme)
        self.assertNotIn("`batch`", data_readme)

    def test_locale_copy_does_not_advertise_removed_legacy_flag(self):
        for locale_path in (REPO_ROOT / "core" / "locales").glob("*.json"):
            locale_text = locale_path.read_text(encoding="utf-8")
            self.assertNotIn("zhihu interactive --legacy", locale_text, locale_path.name)

    def test_cli_main_uses_help_for_bare_entrypoint(self):
        app_text = (REPO_ROOT / "cli" / "app.py").read_text(encoding="utf-8")

        self.assertIn("no_args_is_help=True", app_text)
        self.assertNotIn("@app.command(\"interactive\")", app_text)

    def test_cli_app_no_longer_keeps_dead_save_or_batch_helpers(self):
        app_text = (REPO_ROOT / "cli" / "app.py").read_text(encoding="utf-8")

        self.assertNotIn("def print_result(", app_text)
        self.assertNotIn("def build_output_folder_name(", app_text)
        self.assertNotIn("def resolve_entries_output_dir(", app_text)
        self.assertNotIn("def resolve_creator_output_dir(", app_text)
        self.assertNotIn("def _batch_concurrent(", app_text)

    def test_query_surface_uses_content_key_label(self):
        app_text = (REPO_ROOT / "cli" / "app.py").read_text(encoding="utf-8")

        self.assertIn('table.add_column("Content Key"', app_text)
        self.assertNotIn('table.add_column("Zhihu ID"', app_text)

    def test_config_view_docstring_matches_current_config_command(self):
        config_view_text = (REPO_ROOT / "cli" / "config_view.py").read_text(encoding="utf-8")

        self.assertIn("zhihu config", config_view_text)
        self.assertNotIn("zhihu config --show", config_view_text)


if __name__ == "__main__":
    unittest.main()
