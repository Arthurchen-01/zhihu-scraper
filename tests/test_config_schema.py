import unittest

from core.config_schema import Config, build_config_from_dict, build_default_config


class ConfigSchemaTests(unittest.TestCase):
    def test_build_config_from_dict_keeps_backward_compat_fields(self):
        config = build_config_from_dict(
            {
                "zhihu": {
                    "cookies": {"file": ".local/cookies.json"},
                    "browser": {"headless": False},
                },
                "crawler": {"images": {"concurrency": 8}},
                "output": {
                    "directory": "data",
                    "folder_format": "[{date}] {title}",
                    "download_images": True,
                },
                "logging": {"level": "DEBUG"},
            }
        )

        self.assertIsInstance(config, Config)
        self.assertFalse(config.zhihu.browser.headless)
        self.assertEqual(config.local.cookies_file, ".local/cookies.json")
        self.assertEqual(config.local.output_dir, "data")
        self.assertEqual(config.crawler.images.concurrency, 8)
        self.assertTrue(config.output.download_images)
        self.assertEqual(config.logging.level, "DEBUG")

    def test_build_default_config_is_safe_and_complete(self):
        config = build_default_config()
        self.assertEqual(config.local.output_dir, "data")
        self.assertEqual(config.local.cookies_file, ".local/cookies.json")
        self.assertTrue(config.zhihu.cookies_required)
        self.assertEqual(config.crawler.retry.max_attempts, 3)

    def test_default_config_does_not_expose_removed_translation_settings(self):
        config = build_default_config()
        self.assertFalse(hasattr(config, "translation"))

    def test_default_config_does_not_expose_removed_language_settings(self):
        config = build_default_config()
        self.assertFalse(hasattr(config, "globals"))


if __name__ == "__main__":
    unittest.main()
