import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from zhihu_scraper.domain import Article
from zhihu_scraper.facade import build_workflow, check_session
from zhihu_scraper.http import LoginStatus
from zhihu_scraper.settings import ArchiveSettings, BrowserFallback


class FakeClient:
    def __init__(self):
        self.calls = []

    def get_json(self, url):
        self.calls.append(url)
        return {
            "id": 1,
            "title": "公共接口文章",
            "content": "<p>正文</p>",
            "author": {"id": "author", "name": "作者"},
        }

    def get_html(self, url):
        raise AssertionError("HTML fallback should not be used")


class FakeSink:
    def __init__(self):
        self.saved = []

    def archive(self, target):
        self.saved.append(target)
        return "saved"


class PublicApiTests(unittest.TestCase):
    def test_build_workflow_exposes_injectable_source_and_sink_boundaries(self):
        client = FakeClient()
        sink = FakeSink()
        workflow = build_workflow(
            ArchiveSettings(
                media_download=False,
                browser_fallback=BrowserFallback.NEVER,
            ),
            client=client,
            sink=sink,
        )

        report = workflow.run("https://zhuanlan.zhihu.com/p/1")

        self.assertIsInstance(report.target, Article)
        self.assertEqual("saved", report.receipt)
        self.assertEqual(["/api/v4/articles/1"], client.calls)
        self.assertEqual([report.target], sink.saved)

    def test_session_check_without_cookie_file_is_local_and_reports_both_names(self):
        report = check_session(ArchiveSettings())

        self.assertEqual(("z_c0", "d_c0"), report.cookie_diagnostic.missing)
        self.assertIsNone(report.login_status)

    def test_session_check_loads_configured_file_but_never_returns_cookie_values(self):
        secret = "must-not-appear-in-report"
        with tempfile.TemporaryDirectory() as temporary_directory:
            cookie_path = Path(temporary_directory) / "cookies.json"
            cookie_path.write_text(
                '{"z_c0": "' + secret + '", "d_c0": "another-secret"}',
                encoding="utf-8",
            )
            fake_client = Mock()
            fake_client.check_login.return_value = LoginStatus(
                authenticated=True,
                member_id="member",
                name="用户",
            )
            with patch(
                "zhihu_scraper.facade.ZhihuHttpClient",
                return_value=fake_client,
            ):
                report = check_session(
                    ArchiveSettings(cookie_file=cookie_path)
                )

        self.assertTrue(report.cookie_diagnostic.is_complete)
        self.assertTrue(report.login_status.authenticated)
        self.assertNotIn(secret, repr(report))


if __name__ == "__main__":
    unittest.main()
