import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from core.contracts import SavePipelineError, SaveRunResult
from cli.contracts import BatchWorkflowResult, UrlTaskResult
from core.save_pipeline import SavePipelineSettings
from cli.workflow_service import (
    DEFAULT_QUESTION_LIMIT,
    ArchiveWorkflowService,
    WorkflowServiceConfig,
    build_scrape_config_for_url,
)
from core.monitor import CollectionDelta
from core.scraper_contracts import ScrapedItem


class WorkflowContractTests(unittest.TestCase):
    def test_batch_workflow_result_aggregates_counts(self):
        result = BatchWorkflowResult(
            items=(
                UrlTaskResult(url="u1", success=True),
                UrlTaskResult(url="u2", success=False, error="boom"),
            )
        )
        self.assertEqual(result.total_count, 2)
        self.assertEqual(result.success_count, 1)
        self.assertEqual(result.failed_count, 1)
        self.assertTrue(result.has_failures)

    def test_print_failed_url_reasons_reports_each_failure(self):
        from cli.app import print_failed_url_reasons

        captured = []
        result = BatchWorkflowResult(
            items=(
                UrlTaskResult(url="ok", success=True),
                UrlTaskResult(url="bad", success=False, error="HTTP 403"),
            )
        )

        with unittest.mock.patch("cli.app.rprint", side_effect=captured.append):
            print_failed_url_reasons(result)

        output = "\n".join(captured)
        self.assertIn("bad", output)
        self.assertIn("HTTP 403", output)
        self.assertNotIn("ok", output)

    def test_cookie_diagnostic_message_reports_partial_cookie(self):
        from core.api_client import ZhihuAPIClient

        client = object.__new__(ZhihuAPIClient)
        client._cookies_dict = {"z_c0": "token"}

        warning = client.cookie_diagnostic_message()

        self.assertIsNotNone(warning)
        assert warning is not None
        self.assertIn("d_c0", warning)

    def test_http_status_failure_descriptions_include_cookie_and_content_hints(self):
        from core.api_client import ZhihuAPIClient

        client = object.__new__(ZhihuAPIClient)

        self.assertIn("z_c0 / d_c0", client._describe_http_status_failure(403, route="API"))
        self.assertIn("不存在", client._describe_http_status_failure(404, route="API"))


class ApiClientRetryTests(unittest.TestCase):
    def _make_client(self, responses):
        from core.api_client import ZhihuAPIClient

        class FakeSession:
            def __init__(self, sequence):
                self.sequence = list(sequence)
                self.calls = 0

            def get(self, *_args, **_kwargs):
                self.calls += 1
                if not self.sequence:
                    raise RuntimeError("no more responses")
                return self.sequence.pop(0)

        client = object.__new__(ZhihuAPIClient)
        client.log = MagicMock()
        client.session = FakeSession(responses)
        client._get_signature = lambda _path: {}
        return client

    def test_fetch_api_retries_transient_status_with_retry_after(self):
        from core.api_client import ZhihuAPIClient
        from core.config_schema import Config

        class Response:
            def __init__(self, status_code, body=None, headers=None):
                self.status_code = status_code
                self.text = body or ""
                self.headers = headers or {}

            def json(self):
                return {"ok": True}

        client = self._make_client(
            (
                Response(503, body="service unavailable", headers={"Retry-After": "0.25"}),
                Response(200),
            )
        )

        cfg = Config.from_dict(
            {"crawler": {"retry": {"max_attempts": 2, "base_delay": 10.0, "jitter": False}}}
        )
        with patch("core.api_client.get_config", return_value=cfg):
            with patch("core.api_client.time.sleep") as mocked_sleep:
                result = ZhihuAPIClient.fetch_api(client, "/api/v4/demo")

        self.assertEqual(result, {"ok": True})
        self.assertEqual(client.session.calls, 2)
        mocked_sleep.assert_called_once_with(0.25)

    def test_fetch_api_does_not_retry_content_not_found(self):
        from core.api_client import ZhihuAPIClient
        from core.config_schema import Config

        class Response:
            status_code = 404
            text = "not found"
            headers = {}

        client = self._make_client((Response(),))
        cfg = Config.from_dict({"crawler": {"retry": {"max_attempts": 3, "jitter": False}}})

        with patch("core.api_client.get_config", return_value=cfg):
            with patch("core.api_client.time.sleep") as mocked_sleep:
                with self.assertRaises(Exception) as captured:
                    ZhihuAPIClient.fetch_api(client, "/api/v4/missing")

        self.assertIn("HTTP 404", str(captured.exception))
        self.assertEqual(client.session.calls, 1)
        mocked_sleep.assert_not_called()


class WorkflowServiceTests(unittest.IsolatedAsyncioTestCase):
    def _make_service(self, **kwargs):
        return ArchiveWorkflowService(
            WorkflowServiceConfig(
                save_settings=SavePipelineSettings(
                    folder_template="[{date}] {title}",
                    images_subdir="images",
                    image_concurrency=4,
                    image_timeout=30,
                ),
                printer=lambda *_args, **_kwargs: None,
                logger=None,
            ),
            **kwargs,
        )

    async def test_run_fetch_urls_builds_question_scrape_config(self):
        captured = []

        async def fake_fetch_runner(**kwargs):
            captured.append(kwargs)
            return SaveRunResult(source_url=kwargs["url"], content_root=Path("data/entries"), records=())

        service = self._make_service(fetch_runner=fake_fetch_runner)
        await service.run_fetch_urls(
            urls=["https://www.zhihu.com/question/123"],
            output_dir=Path("data"),
            limit=5,
            download_images=False,
            headless=True,
        )

        self.assertEqual(captured[0]["scrape_config"], {"start": 0, "limit": 5})

    def test_build_scrape_config_for_url_uses_limit_for_question_urls(self):
        self.assertEqual(
            build_scrape_config_for_url(
                "https://www.zhihu.com/question/123",
                question_limit=5,
            ),
            {"start": 0, "limit": 5},
        )

    def test_build_scrape_config_for_url_can_apply_default_question_limit(self):
        self.assertEqual(
            build_scrape_config_for_url(
                "https://www.zhihu.com/question/123",
                default_question_limit=DEFAULT_QUESTION_LIMIT,
            ),
            {"start": 0, "limit": DEFAULT_QUESTION_LIMIT},
        )

    def test_build_scrape_config_for_url_skips_non_question_urls(self):
        self.assertEqual(
            build_scrape_config_for_url(
                "https://www.zhihu.com/question/123/answer/456",
                question_limit=5,
            ),
            {},
        )

    async def test_run_monitor_only_advances_pointer_when_all_success(self):
        class FakeMonitor:
            def __init__(self, data_dir):
                self.data_dir = data_dir
                self.marked = None

            def get_new_items(self, collection_id):
                return CollectionDelta(
                    items=(
                        {"url": "https://www.zhihu.com/question/1/answer/2"},
                        {"url": "https://zhuanlan.zhihu.com/p/3"},
                    ),
                    next_pointer="latest-id",
                    unseen_count=2,
                    unsupported_count=0,
                )

            def mark_updated(self, collection_id, new_last_id):
                self.marked = (collection_id, new_last_id)

        monitor = FakeMonitor("data")

        async def fake_fetch_runner(**kwargs):
            return SaveRunResult(source_url=kwargs["url"], content_root=Path("data/entries"), records=())

        async def no_sleep(_delay: float):
            return None

        service = self._make_service(
            fetch_runner=fake_fetch_runner,
            monitor_factory=lambda data_dir: monitor,
            sleep=no_sleep,
        )
        result = await service.run_monitor(
            collection_id="78170682",
            output_dir=Path("data"),
            concurrency=4,
            download_images=False,
            headless=True,
        )

        self.assertEqual(result.discovered_count, 2)
        self.assertTrue(result.pointer_advanced)
        self.assertEqual(monitor.marked, ("78170682", "latest-id"))

    async def test_run_monitor_advances_pointer_for_unsupported_only_activity(self):
        class FakeMonitor:
            def __init__(self, data_dir):
                self.data_dir = data_dir
                self.marked = None

            def get_new_items(self, collection_id):
                return CollectionDelta(
                    items=(),
                    next_pointer="latest-unsupported-id",
                    unseen_count=2,
                    unsupported_count=2,
                )

            def mark_updated(self, collection_id, new_last_id):
                self.marked = (collection_id, new_last_id)

        monitor = FakeMonitor("data")
        service = self._make_service(
            monitor_factory=lambda data_dir: monitor,
            error_handler=lambda *_args, **_kwargs: None,
        )
        result = await service.run_monitor(
            collection_id="78170682",
            output_dir=Path("data"),
            concurrency=4,
            download_images=False,
            headless=True,
        )

        self.assertEqual(result.discovered_count, 0)
        self.assertEqual(result.unsupported_count, 2)
        self.assertTrue(result.pointer_advanced)
        self.assertTrue(result.has_new_activity)
        self.assertFalse(result.has_new_items)
        self.assertEqual(monitor.marked, ("78170682", "latest-unsupported-id"))

    async def test_run_monitor_keeps_pointer_when_supported_items_have_failures(self):
        class FakeMonitor:
            def __init__(self, data_dir):
                self.data_dir = data_dir
                self.marked = None

            def get_new_items(self, collection_id):
                return CollectionDelta(
                    items=(
                        {"url": "https://www.zhihu.com/question/1/answer/2"},
                        {"url": "https://zhuanlan.zhihu.com/p/3"},
                    ),
                    next_pointer="latest-id",
                    unseen_count=2,
                    unsupported_count=1,
                )

            def mark_updated(self, collection_id, new_last_id):
                self.marked = (collection_id, new_last_id)

        async def flaky_fetch_runner(**kwargs):
            if kwargs["url"].endswith("/3"):
                raise RuntimeError("boom")
            return SaveRunResult(source_url=kwargs["url"], content_root=Path("data/entries"), records=())

        async def no_sleep(_delay: float):
            return None

        monitor = FakeMonitor("data")
        service = self._make_service(
            fetch_runner=flaky_fetch_runner,
            monitor_factory=lambda data_dir: monitor,
            error_handler=lambda *_args, **_kwargs: None,
            sleep=no_sleep,
        )
        result = await service.run_monitor(
            collection_id="78170682",
            output_dir=Path("data"),
            concurrency=4,
            download_images=False,
            headless=True,
        )

        self.assertEqual(result.discovered_count, 2)
        self.assertEqual(result.unsupported_count, 1)
        self.assertFalse(result.pointer_advanced)
        self.assertTrue(result.has_new_activity)
        self.assertIsNone(monitor.marked)

    async def test_run_monitor_treats_known_head_pointer_as_no_new_activity(self):
        class FakeMonitor:
            def __init__(self, data_dir):
                self.data_dir = data_dir
                self.marked = None

            def get_new_items(self, collection_id):
                return CollectionDelta(
                    items=(),
                    next_pointer="known-id",
                    unseen_count=0,
                    unsupported_count=0,
                )

            def mark_updated(self, collection_id, new_last_id):
                self.marked = (collection_id, new_last_id)

        monitor = FakeMonitor("data")
        service = self._make_service(
            monitor_factory=lambda data_dir: monitor,
            error_handler=lambda *_args, **_kwargs: None,
        )
        result = await service.run_monitor(
            collection_id="78170682",
            output_dir=Path("data"),
            concurrency=4,
            download_images=False,
            headless=True,
        )

        self.assertFalse(result.has_new_activity)
        self.assertFalse(result.pointer_advanced)
        self.assertIsNone(result.next_pointer)
        self.assertIsNone(monitor.marked)

    async def test_run_single_fetch_returns_failure_result_without_raising(self):
        async def broken_fetch_runner(**_kwargs):
            raise RuntimeError("boom")

        service = self._make_service(fetch_runner=broken_fetch_runner, error_handler=lambda *_args, **_kwargs: None)
        result = await service.run_single_fetch(
            url="https://www.zhihu.com/question/1/answer/2",
            output_dir=Path("data"),
            scrape_config={},
            download_images=False,
            headless=True,
        )

        self.assertFalse(result.success)
        self.assertIn("boom", result.error)

    async def test_run_single_fetch_keeps_partial_save_context_for_save_pipeline_error(self):
        partial_result = SaveRunResult(
            source_url="https://www.zhihu.com/question/1/answer/2",
            content_root=Path("data/entries"),
            records=(),
        )
        failed_item = ScrapedItem(
            id="2",
            type="answer",
            url="https://www.zhihu.com/question/1/answer/2",
            title="Demo",
            author="Tester",
            html="<p>hello</p>",
            date="2026-04-03",
        )

        async def broken_fetch_runner(**_kwargs):
            raise SavePipelineError(
                "SQLite save failed after writing Markdown for answer:2; 0 item(s) were already archived to disk",
                partial_result=partial_result,
                failed_item=failed_item,
                failed_markdown_path=Path("data/entries/demo/index.md"),
            )

        service = self._make_service(fetch_runner=broken_fetch_runner, error_handler=lambda *_args, **_kwargs: None)
        result = await service.run_single_fetch(
            url="https://www.zhihu.com/question/1/answer/2",
            output_dir=Path("data"),
            scrape_config={},
            download_images=False,
            headless=True,
        )

        self.assertFalse(result.success)
        self.assertIs(result.partial_save_result, partial_result)
        self.assertIn("SQLite save failed", result.error)


if __name__ == "__main__":
    unittest.main()
