import unittest
from pathlib import Path

from cli.config_view import build_config_snapshot, render_config_panel
from core.config_schema import Config
from core.cookie_manager import RuntimePathResolution


class ConfigViewTests(unittest.TestCase):
    def test_build_config_snapshot_resolves_paths_and_modes(self):
        cfg = Config.from_dict(
            {
                "local": {"cookies_file": ".local/cookies.json", "output_dir": "data"},
                "zhihu": {"cookies": {"required": True}, "browser": {"headless": False}},
                "crawler": {"retry": {"max_attempts": 5}, "images": {"concurrency": 6}},
                "logging": {"file": ".local/logs/app.log", "level": "DEBUG"},
            }
        )

        snapshot = build_config_snapshot(
            cfg=cfg,
            config_path=Path("/repo/config.yaml"),
            resolve_project_path=lambda raw: Path("/repo") / raw,
            describe_cookie_file_path=lambda raw: RuntimePathResolution(
                configured_path=Path("/repo") / raw,
                active_path=Path("/active") / Path(raw).name,
            ),
        )

        self.assertEqual(snapshot.output_directory, "/repo/data")
        self.assertEqual(snapshot.browser_mode, "Visible / 有头")
        self.assertEqual(snapshot.retry_attempts, 5)
        self.assertEqual(snapshot.image_concurrency, 6)
        self.assertEqual(snapshot.configured_cookie_path, Path("/repo/.local/cookies.json"))
        self.assertEqual(snapshot.active_cookie_path, Path("/active/cookies.json"))
        self.assertEqual(snapshot.cookie_mode, "Single .local/cookies.json file / 单主 Cookie 文件")

    def test_render_config_panel_contains_key_labels(self):
        cfg = Config.from_dict({"local": {"output_dir": "data"}})
        snapshot = build_config_snapshot(
            cfg=cfg,
            config_path=Path("/repo/config.yaml"),
            resolve_project_path=lambda raw: Path("/repo") / raw,
            describe_cookie_file_path=lambda raw: RuntimePathResolution(
                configured_path=Path("/repo") / raw,
                active_path=Path("/repo") / raw,
            ),
        )
        rendered = render_config_panel(snapshot)
        text = rendered.renderable.plain

        self.assertIn("Config Path", text)
        self.assertIn("Output Directory", text)
        self.assertIn("Active Cookie", text)
        self.assertIn("Cookie Path Status", text)
        self.assertIn("Cookie Mode", text)


if __name__ == "__main__":
    unittest.main()
