import asyncio
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from core.contracts import SavePipelineError
from core.save_pipeline import (
    SavePipelineSettings,
    build_output_folder_name,
    resolve_entries_output_dir,
    save_items_result,
)


class OutputPathTests(unittest.TestCase):
    def test_build_output_folder_name_keeps_suffix_and_shell_safe(self):
        folder = build_output_folder_name(
            "2026-03-31",
            "如何看待伊朗驻华大使馆认为日本是二战受害者？",
            "玄睛",
            "answer-2022365612303741181",
            folder_template="[{date}] {title}",
        )
        self.assertIn("2026-03-31", folder)
        self.assertIn("answer-2022365612303741181", folder)
        self.assertNotIn("[", folder)
        self.assertNotIn("]", folder)
        self.assertNotIn("(", folder)
        self.assertNotIn(")", folder)
        self.assertNotIn(" ", folder)

    def test_entries_output_dir_only_appends_entries_once(self):
        self.assertEqual(resolve_entries_output_dir(Path("data")), Path("data/entries"))
        self.assertEqual(resolve_entries_output_dir(Path("entries")), Path("entries"))

class SavePipelineFailureTests(unittest.TestCase):
    def test_save_items_result_raises_typed_error_with_partial_context(self):
        class FailingDb:
            def __init__(self, *_args, **_kwargs):
                self.closed = False
                self.calls = 0

            def save_article(self, *_args, **_kwargs):
                self.calls += 1
                return self.calls == 1

            def close(self):
                self.closed = True

        items = [
            {
                "id": "42",
                "type": "answer",
                "url": "https://www.zhihu.com/question/1/answer/42",
                "title": "Demo",
                "author": "Tester",
                "html": "<p>hello</p>",
                "date": "2026-04-03",
            },
            {
                "id": "43",
                "type": "article",
                "url": "https://zhuanlan.zhihu.com/p/43",
                "title": "Second",
                "author": "Tester",
                "html": "<p>world</p>",
                "date": "2026-04-03",
            },
        ]

        with tempfile.TemporaryDirectory() as tmpdir:
            settings = SavePipelineSettings(
                folder_template="[{date}] {title}",
                images_subdir="images",
                image_concurrency=4,
                image_timeout=30,
            )
            with patch("core.save_pipeline.ZhihuDatabase", FailingDb):
                with self.assertRaises(SavePipelineError) as captured:
                    asyncio.run(
                        save_items_result(
                            items=items,
                            content_root=Path(tmpdir) / "entries",
                            db_root=Path(tmpdir),
                            settings=settings,
                            download_images=False,
                            source_url_fallback=items[0]["url"],
                            event_sink=lambda *_args, **_kwargs: None,
                        )
                    )
                error = captured.exception
                self.assertEqual(error.saved_count, 1)
                self.assertEqual(error.partial_result.saved_count, 1)
                self.assertEqual(error.failed_item.id, "43")
                self.assertTrue(error.failed_markdown_path.exists())
                self.assertIn("SQLite save failed", str(error))
                self.assertIn("1 item(s) were already archived to disk", str(error))


if __name__ == "__main__":
    unittest.main()
