import unittest
from pathlib import Path
from unittest.mock import patch

from cli.healthcheck import collect_environment_checks, summarize_playwright_failure
from core.errors import ConfigError, AntiDetectionError, classify_error
from core.save_pipeline import build_output_folder_name
from core.config_schema import Config
from core.cookie_manager import RuntimePathResolution
from core.utils import sanitize_filename


class ConfigCompatibilityTests(unittest.TestCase):
    def test_output_download_images_is_accepted_for_backward_compatibility(self):
        config = Config.from_dict(
            {
                "output": {
                    "directory": "data",
                    "folder_format": "[{date}] {title}",
                    "download_images": True,
                }
            }
        )
        self.assertEqual(config.local.output_dir, "data")
        self.assertEqual(config.output.folder_format, "[{date}] {title}")
        self.assertTrue(config.output.download_images)

    def test_build_output_folder_name_is_shell_safe(self):
        folder = build_output_folder_name(
            "2026-03-31",
            "如何看待伊朗驻华大使馆认为日本是二战受害者？",
            "玄睛",
            "answer-2022365612303741181",
        )
        self.assertIn("2026-03-31", folder)
        self.assertIn("answer-2022365612303741181", folder)
        self.assertNotIn("[", folder)
        self.assertNotIn("]", folder)
        self.assertNotIn("(", folder)
        self.assertNotIn(")", folder)
        self.assertNotIn(" ", folder)

    def test_shell_safe_filename_removes_common_shell_metacharacters(self):
        value = sanitize_filename("[draft] hello (world) & more", shell_safe=True)
        self.assertEqual(value, "draft_hello_world_more")


class UserVisibleErrorTests(unittest.TestCase):
    def test_config_error_accepts_custom_cookie_hint(self):
        error = ConfigError(
            "Cookie expired",
            recoverable_hint="刷新 z_c0 / d_c0 后重试",
        )

        self.assertIn("z_c0", error.recoverable_hint)
        self.assertIn("d_c0", error.recoverable_hint)

    def test_http_block_errors_include_cookie_recovery_hint(self):
        error = classify_error(
            RuntimeError(
                "请求遭到 HTTP 403 拦截，重试 3 次后仍失败。"
                "请检查 .local/cookies.json 中的 z_c0 / d_c0 是否缺失或过期。"
            )
        )

        self.assertIsInstance(error, AntiDetectionError)
        self.assertIsNotNone(error.recoverable_hint)
        assert error.recoverable_hint is not None
        self.assertIn("zhihu check", error.recoverable_hint)

    def test_content_not_found_keeps_original_http_reason(self):
        error = classify_error(
            RuntimeError("回答 1 API 抓取失败: API 请求返回 HTTP 404，内容可能不存在。")
        )

        self.assertIn("HTTP 404", error.message)
        self.assertIn("回答 1", error.message)


class HealthcheckSummaryTests(unittest.TestCase):
    def test_playwright_permission_failure_is_summarized(self):
        detail, hint = summarize_playwright_failure(
            RuntimeError(
                "BrowserType.launch: Target page, context or browser has been closed\n"
                "[FATAL] bootstrap_check_in org.chromium.Chromium: Permission denied (1100)"
            )
        )
        self.assertIn("Chromium", detail)
        self.assertIsNotNone(hint)
        assert hint is not None
        self.assertIn("受限沙箱", hint)

    def test_playwright_missing_binary_failure_is_summarized(self):
        detail, hint = summarize_playwright_failure(RuntimeError("Executable doesn't exist at /tmp/chromium"))
        self.assertIn("Playwright 浏览器未安装完整", detail)
        self.assertIsNotNone(hint)
        assert hint is not None
        self.assertIn("playwright install chromium", hint)

    def test_collect_environment_checks_reports_configured_cookie_path(self):
        cfg = Config.from_dict(
            {
                "local": {"cookies_file": ".local/cookies.json"},
                "zhihu": {"cookies": {"required": True}},
            }
        )
        with patch("cli.healthcheck.get_config", return_value=cfg):
            with patch("core.cookie_manager.has_real_cookie_values", return_value=True):
                with patch("core.cookie_manager.count_available_cookie_sources", return_value=1):
                    with patch(
                        "core.cookie_manager.describe_cookie_file_path",
                        return_value=RuntimePathResolution(
                            configured_path=Path("/repo/.local/cookies.json"),
                            active_path=Path("/repo/.local/cookies.json"),
                        ),
                    ):
                        with patch(
                            "cli.healthcheck.asyncio.run",
                            side_effect=lambda coro: coro.close(),
                        ):
                            items = collect_environment_checks()

        cookie_path = next(item for item in items if item.label == "Cookie 路径 / Cookie path")
        self.assertEqual(cookie_path.status, "ok")
        self.assertIn("configured /repo/.local/cookies.json -> active /repo/.local/cookies.json", cookie_path.detail)


if __name__ == "__main__":
    unittest.main()
