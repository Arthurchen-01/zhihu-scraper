import io
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from zhihu_scraper.cli import run_cli
from zhihu_scraper.http import CookieDiagnostic, LoginStatus


class NewCommandLineTests(unittest.TestCase):
    def test_help_exposes_only_the_small_supported_command_surface(self):
        output = io.StringIO()

        with redirect_stdout(output), self.assertRaises(SystemExit) as raised:
            run_cli(["--help"])

        self.assertEqual(0, raised.exception.code)
        rendered = output.getvalue()
        self.assertIn("fetch", rendered)
        self.assertIn("check", rendered)
        self.assertIn("init", rendered)
        self.assertNotIn("tui", rendered.casefold())
        self.assertNotIn("translate", rendered.casefold())

    def test_fetch_applies_command_overrides_and_prints_readable_paths(self):
        receipt = SimpleNamespace(
            entry_directory=Path("/archive/文章"),
            markdown_path=Path("/archive/文章/文章.md"),
            html_path=Path("/archive/文章/文章.html"),
            database_path=Path("/archive/zhihu.db"),
        )
        report = SimpleNamespace(
            target=SimpleNamespace(title="文章"),
            receipt=receipt,
            used_browser=False,
        )
        output = io.StringIO()

        with patch("zhihu_scraper.cli.archive_url", return_value=report) as archive:
            with redirect_stdout(output):
                exit_code = run_cli(
                    [
                        "fetch",
                        "https://zhuanlan.zhihu.com/p/1",
                        "--output",
                        "/archive",
                        "--comments",
                        "--no-media",
                        "--browser",
                        "never",
                    ]
                )

        self.assertEqual(0, exit_code)
        settings = archive.call_args.args[1]
        self.assertEqual(Path("/archive"), settings.output_dir)
        self.assertTrue(settings.comments)
        self.assertFalse(settings.media_download)
        self.assertEqual("never", settings.browser_fallback.value)
        self.assertIn("归档完成：文章", output.getvalue())
        self.assertIn("HTTP/API", output.getvalue())

    def test_check_reports_real_status_without_printing_identity_or_cookie_values(self):
        report = SimpleNamespace(
            cookie_diagnostic=CookieDiagnostic(missing=()),
            login_status=LoginStatus(
                authenticated=True,
                member_id="private-member-id",
                name="private-name",
            ),
        )
        output = io.StringIO()

        with patch("zhihu_scraper.cli.check_session", return_value=report):
            with redirect_stdout(output):
                exit_code = run_cli(["check"])

        rendered = output.getvalue()
        self.assertEqual(0, exit_code)
        self.assertIn("登录状态有效", rendered)
        self.assertNotIn("private-member-id", rendered)
        self.assertNotIn("private-name", rendered)

    def test_fetch_reports_nonfatal_media_failures_without_marking_archive_failed(self):
        receipt = SimpleNamespace(
            entry_directory=Path("/archive/文章"),
            markdown_path=Path("/archive/文章/文章.md"),
            html_path=Path("/archive/文章/文章.html"),
            database_path=Path("/archive/zhihu.db"),
        )
        failure = SimpleNamespace(display_message="正文媒体下载失败，已保留远程链接：image-1")
        report = SimpleNamespace(
            target=SimpleNamespace(title="文章"),
            receipt=receipt,
            used_browser=False,
            media_failures=(failure,),
        )
        output = io.StringIO()

        with patch("zhihu_scraper.cli.archive_url", return_value=report):
            with redirect_stdout(output):
                exit_code = run_cli(["fetch", "https://zhuanlan.zhihu.com/p/1"])

        self.assertEqual(0, exit_code)
        self.assertIn("媒体警告：1 个", output.getvalue())
        self.assertIn("image-1", output.getvalue())

    def test_init_never_overwrites_existing_settings(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            path = Path(temporary_directory) / "settings.toml"

            self.assertEqual(0, run_cli(["init", str(path)]))
            generated = path.read_text(encoding="utf-8")
            path.write_text("keep = true", encoding="utf-8")
            self.assertEqual(0, run_cli(["init", str(path)]))

            self.assertIn("[archive]", generated)
            self.assertEqual("keep = true", path.read_text(encoding="utf-8"))

    def test_errors_use_stderr_and_nonzero_exit_code(self):
        error_output = io.StringIO()

        with patch(
            "zhihu_scraper.cli.archive_url",
            side_effect=RuntimeError("抓取失败"),
        ):
            with redirect_stderr(error_output):
                exit_code = run_cli(["fetch", "https://zhuanlan.zhihu.com/p/1"])

        self.assertEqual(1, exit_code)
        self.assertIn("错误：抓取失败", error_output.getvalue())


if __name__ == "__main__":
    unittest.main()
