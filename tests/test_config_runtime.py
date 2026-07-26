import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from core.config_schema import Config
from core.config_runtime import resolve_project_path
from core.logging_setup import summarize_text_for_logs
from core.config_runtime import ConfigLoader


class ConfigRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.loader = ConfigLoader()
        self.original_config = self.loader._config
        self.loader._config = None

    def tearDown(self):
        self.loader._config = self.original_config

    def test_loader_reads_explicit_yaml_path(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.yaml"
            config_path.write_text(
                "local:\n"
                "  output_dir: custom-data\n"
                "logging:\n"
                "  level: DEBUG\n",
                encoding="utf-8",
            )

            config = self.loader.load(config_path)

        self.assertIsInstance(config, Config)
        self.assertEqual(config.local.output_dir, "custom-data")
        self.assertEqual(config.logging.level, "DEBUG")

    def test_loader_missing_file_falls_back_to_defaults(self):
        config = self.loader.load(Path("/tmp/definitely-missing-config.yaml"))
        self.assertEqual(config.local.output_dir, "data")
        self.assertTrue(config.zhihu.cookies_required)

    def test_loader_missing_file_still_initializes_logging_and_override_level(self):
        with patch("core.config_runtime.setup_logging") as mocked_setup_logging:
            config = self.loader.load(
                Path("/tmp/definitely-missing-config.yaml"),
                override_level="DEBUG",
            )

        self.assertEqual(config.logging.level, "DEBUG")
        mocked_setup_logging.assert_called_once_with(config)

    def test_loader_invalid_yaml_still_initializes_logging_and_override_level(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.yaml"
            config_path.write_text("zhihu: [broken", encoding="utf-8")

            with patch("core.config_runtime.setup_logging") as mocked_setup_logging:
                config = self.loader.load(config_path, override_level="WARNING")

        self.assertEqual(config.logging.level, "WARNING")
        mocked_setup_logging.assert_called_once_with(config)

    def test_config_facade_reexports_path_and_log_helpers(self):
        project_path = resolve_project_path("data")
        summary = summarize_text_for_logs("secret-cookie", kind="cookie")

        self.assertTrue(project_path.is_absolute())
        self.assertIn("cookie_redacted", summary)

    def test_update_config_filters_invalid_keys_preventing_drift(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.yaml"
            config_path.write_text("logging:\n  level: INFO\n", encoding="utf-8")

            with patch("core.config_runtime.get_project_root", return_value=Path(tmpdir)):
                from core.config_runtime import update_config, get_config

                # Update with a valid key and an invalid key
                update_config({
                    "logging": {"level": "DEBUG", "invalid_garbage": "should_be_gced"},
                    "completely_invalid_root": {"garbage": 123}
                })

                # Check parsed config
                config = get_config(config_path)
                self.assertEqual(config.logging.level, "DEBUG")

                # Ensure the invalid keys were never persisted
                import yaml
                raw = yaml.safe_load(config_path.read_text(encoding="utf-8"))
                self.assertEqual(raw["logging"]["level"], "DEBUG")
                self.assertNotIn("invalid_garbage", raw["logging"])
                self.assertNotIn("completely_invalid_root", raw)


if __name__ == "__main__":
    unittest.main()
