import unittest
from pathlib import Path

from core.contracts import SavePipelineError, SaveRunResult, SavedContentRecord
from core.scraper_contracts import ScrapedItem


class SaveContractTests(unittest.TestCase):
    def test_save_run_result_roundtrips_to_legacy_records(self):
        record = SavedContentRecord(
            item=ScrapedItem(
                id="123",
                type="answer",
                url="https://www.zhihu.com/question/1/answer/123",
                title="问题",
                author="作者",
                html="<p>body</p>",
                date="2026-04-03",
            ),
            folder=Path("data/entries/demo--answer-123"),
            markdown_path=Path("data/entries/demo--answer-123/index.md"),
        )
        result = SaveRunResult(
            source_url="https://www.zhihu.com/question/1/answer/123",
            content_root=Path("data/entries"),
            records=(record,),
            collection_id="42",
        )

        legacy = result.to_legacy_records()

        self.assertEqual(result.saved_count, 1)
        self.assertEqual(result.markdown_paths, ("data/entries/demo--answer-123/index.md",))
        self.assertEqual(legacy[0]["item"]["id"], "123")

    def test_save_pipeline_error_exposes_partial_result(self):
        record = SavedContentRecord(
            item=ScrapedItem(
                id="123",
                type="answer",
                url="https://www.zhihu.com/question/1/answer/123",
                title="问题",
                author="作者",
                html="<p>body</p>",
                date="2026-04-03",
            ),
            folder=Path("data/entries/demo--answer-123"),
            markdown_path=Path("data/entries/demo--answer-123/index.md"),
        )
        partial_result = SaveRunResult(
            source_url="https://www.zhihu.com/question/1/answer/123",
            content_root=Path("data/entries"),
            records=(record,),
        )
        failed_item = ScrapedItem(
            id="124",
            type="article",
            url="https://zhuanlan.zhihu.com/p/124",
            title="失败条目",
            author="作者",
            html="<p>body</p>",
            date="2026-04-03",
        )

        error = SavePipelineError(
            "SQLite save failed after writing Markdown for article:124; 1 item(s) were already archived to disk",
            partial_result=partial_result,
            failed_item=failed_item,
            failed_markdown_path=Path("data/entries/demo--article-124/index.md"),
        )

        self.assertEqual(error.saved_count, 1)
        self.assertEqual(error.partial_result.saved_count, 1)
        self.assertEqual(error.failed_item.id, "124")
        self.assertIn("SQLite save failed", str(error))


if __name__ == "__main__":
    unittest.main()
