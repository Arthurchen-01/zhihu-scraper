"""Opt-in Zhihu smoke tests.

These tests never run from the normal unit-test command unless the operator
explicitly supplies both ``ZHIHU_LIVE=1`` and ``ZHIHU_COOKIE_FILE``. Cookie
values are never read from a repository-default path or printed.
"""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from typing import cast
from urllib.request import Request, urlopen

from zhihu_scraper import ArchiveSettings, archive_url
from zhihu_scraper.archive import ArchiveReceipt
from zhihu_scraper.domain import Article, Video
from zhihu_scraper.settings import BrowserFallback

LIVE_ENABLED = os.environ.get("ZHIHU_LIVE") == "1"
COOKIE_FILE = os.environ.get("ZHIHU_COOKIE_FILE", "").strip()


@unittest.skipUnless(
    LIVE_ENABLED and COOKIE_FILE,
    "set ZHIHU_LIVE=1 and ZHIHU_COOKIE_FILE to run controlled online smoke tests",
)
class LiveArchiveTests(unittest.TestCase):
    def settings(self, output_dir: Path) -> ArchiveSettings:
        return ArchiveSettings(
            output_dir=output_dir,
            cookie_file=Path(COOKIE_FILE),
            media_download=False,
            browser_fallback=BrowserFallback.AUTO,
            headless=True,
            timeout=45.0,
            retries=2,
        )

    def test_formula_article_writes_real_markdown_mathml_and_sqlite(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            report = archive_url(
                "https://zhuanlan.zhihu.com/p/11617075708",
                self.settings(Path(temporary_directory)),
            )

            assert isinstance(report.target, Article)
            receipt = cast(ArchiveReceipt, report.receipt)
            self.assertGreater(len(report.target.blocks), 100)
            assert receipt.markdown_path is not None
            assert receipt.html_path is not None
            assert receipt.database_path is not None
            markdown = receipt.markdown_path.read_text(encoding="utf-8")
            rendered_html = receipt.html_path.read_text(encoding="utf-8")

            self.assertIn("$$", markdown)
            self.assertGreater(rendered_html.count("<math"), 100)
            self.assertIn("data-tex=", rendered_html)
            self.assertTrue(receipt.database_path.is_file())

    def test_zvideo_exposes_highest_rendition_and_accepts_range_probe(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            report = archive_url(
                "https://www.zhihu.com/zvideo/1666569497233207296",
                self.settings(Path(temporary_directory)),
            )

            assert isinstance(report.target, Video)
            receipt = cast(ArchiveReceipt, report.receipt)
            renditions = tuple(
                rendition
                for rendition in report.target.asset.renditions
                if rendition.width and rendition.height
            )
            self.assertTrue(renditions)
            highest = max(
                renditions,
                key=lambda rendition: (
                    (rendition.width or -1) * (rendition.height or -1),
                    rendition.bitrate or -1,
                    rendition.size_bytes or -1,
                ),
            )
            assert highest.width is not None
            assert highest.height is not None
            self.assertGreaterEqual(highest.width, 1920)
            self.assertGreaterEqual(highest.height, 1080)

            request = Request(
                highest.source_url,
                headers={
                    "Range": "bytes=0-0",
                    "Referer": "https://www.zhihu.com/",
                    "User-Agent": "zhihu-scraper-live-smoke/4",
                },
            )
            with urlopen(request, timeout=30.0) as response:
                self.assertIn(response.status, {200, 206})
                self.assertEqual(len(response.read(1)), 1)

            assert receipt.markdown_path is not None
            markdown = receipt.markdown_path.read_text(encoding="utf-8")
            self.assertIn("原始视频链接", markdown)


if __name__ == "__main__":
    unittest.main()
