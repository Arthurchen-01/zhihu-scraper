import unittest
from pathlib import Path
from unittest.mock import patch

import tomllib

import zhihu_scraper
from cli.contracts import BatchWorkflowResult, UrlTaskResult
from core.save_pipeline import SavePipelineSettings as InternalSavePipelineSettings
from cli.workflow_service import ArchiveWorkflowService as InternalArchiveWorkflowService
from core.config_schema import Config as InternalConfig
from core.converter import ZhihuConverter as InternalZhihuConverter
from core.db import ZhihuDatabase as InternalZhihuDatabase
from core.scraper import ZhihuDownloader as InternalZhihuDownloader
from core.scraper_contracts import ScrapedItem as InternalScrapedItem
from zhihu_scraper.config import Config
from zhihu_scraper.fetching import ZhihuDownloader
from zhihu_scraper.markdown import ZhihuConverter
from zhihu_scraper.models import ScrapedItem
from zhihu_scraper.services import ArchiveWorkflowService
from zhihu_scraper.storage import SavePipelineSettings, ZhihuDatabase
from zhihu_scraper.api import ArchiveOptions, archive_url


REPO_ROOT = Path(__file__).resolve().parent.parent


class PublicFacadeTests(unittest.TestCase):
    def test_public_modules_reexport_existing_objects(self):
        self.assertIs(Config, InternalConfig)
        self.assertIs(ScrapedItem, InternalScrapedItem)
        self.assertIs(ArchiveWorkflowService, InternalArchiveWorkflowService)
        self.assertIs(ZhihuDownloader, InternalZhihuDownloader)
        self.assertIs(SavePipelineSettings, InternalSavePipelineSettings)
        self.assertIs(ZhihuDatabase, InternalZhihuDatabase)
        self.assertIs(ZhihuConverter, InternalZhihuConverter)

    def test_top_level_facade_exposes_minimal_public_imports(self):
        self.assertIs(zhihu_scraper.Config, InternalConfig)
        self.assertIs(zhihu_scraper.ScrapedItem, InternalScrapedItem)
        self.assertIs(zhihu_scraper.ArchiveWorkflowService, InternalArchiveWorkflowService)
        self.assertIs(zhihu_scraper.ZhihuDownloader, InternalZhihuDownloader)
        self.assertIs(zhihu_scraper.SavePipelineSettings, InternalSavePipelineSettings)
        self.assertIs(zhihu_scraper.ZhihuDatabase, InternalZhihuDatabase)
        self.assertIs(zhihu_scraper.ZhihuConverter, InternalZhihuConverter)
        self.assertIs(zhihu_scraper.ArchiveOptions, ArchiveOptions)
        self.assertIs(zhihu_scraper.archive_url, archive_url)

    def test_pyproject_packages_include_public_facade(self):
        pyproject = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
        includes = pyproject["tool"]["setuptools"]["packages"]["find"]["include"]
        self.assertIn("zhihu_scraper*", includes)


class PublicApiTests(unittest.IsolatedAsyncioTestCase):
    async def test_archive_url_wraps_workflow_service_with_question_config(self):
        captured = {}

        class FakeService:
            async def run_single_fetch(self, **kwargs):
                captured.update(kwargs)
                return UrlTaskResult(url=kwargs["url"], success=True)

        with patch("zhihu_scraper.api.get_workflow_service", return_value=FakeService()):
            result = await zhihu_scraper.archive_url(
                "https://www.zhihu.com/question/123",
                ArchiveOptions(output_dir="tmp-data", question_limit=7, download_images=False),
            )

        self.assertTrue(result.success)
        self.assertEqual(captured["output_dir"], Path("tmp-data"))
        self.assertEqual(captured["scrape_config"], {"start": 0, "limit": 7})
        self.assertFalse(captured["download_images"])

    async def test_archive_urls_returns_batch_contract(self):
        class FakeService:
            async def run_fetch_urls(self, **kwargs):
                return BatchWorkflowResult(
                    items=tuple(UrlTaskResult(url=url, success=True) for url in kwargs["urls"])
                )

        with patch("zhihu_scraper.api.get_workflow_service", return_value=FakeService()):
            result = await zhihu_scraper.archive_urls(
                ("https://zhuanlan.zhihu.com/p/1", "https://zhuanlan.zhihu.com/p/2"),
                ArchiveOptions(stop_on_error=False),
            )

        self.assertEqual(result.total_count, 2)
        self.assertEqual(result.success_count, 2)


if __name__ == "__main__":
    unittest.main()
