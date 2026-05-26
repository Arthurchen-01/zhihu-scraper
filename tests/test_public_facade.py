import unittest
from pathlib import Path

import tomllib

import zhihu_scraper
from cli.save_pipeline import SavePipelineSettings as InternalSavePipelineSettings
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

    def test_pyproject_packages_include_public_facade(self):
        pyproject = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
        includes = pyproject["tool"]["setuptools"]["packages"]["find"]["include"]
        self.assertIn("zhihu_scraper*", includes)


if __name__ == "__main__":
    unittest.main()
