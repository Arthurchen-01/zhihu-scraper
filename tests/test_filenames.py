import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from zhihu_scraper.filenames import safe_filename


class CrossPlatformFilenameTests(unittest.TestCase):
    def test_replaces_reserved_characters_and_trailing_dots(self):
        self.assertEqual("问题_答案", safe_filename('问题:/\\*?"<>|答案. '))

    def test_protects_windows_reserved_names_case_insensitively(self):
        self.assertEqual("_con", safe_filename("con"))
        self.assertEqual("_Lpt9.txt", safe_filename("Lpt9.txt"))

    def test_truncation_is_deterministic_and_preserves_suffix_when_present(self):
        value = "很长的标题" * 40 + ".html"

        result = safe_filename(value, max_length=80)

        self.assertLessEqual(len(result), 80)
        self.assertTrue(result.endswith(".html"))
        self.assertEqual(result, safe_filename(value, max_length=80))

    def test_default_component_budget_leaves_room_for_windows_archive_nesting(self):
        for value in ("很长的知乎标题" * 80, "🧠" * 200):
            with self.subTest(value=value[:4]):
                result = safe_filename(value)

                self.assertLessEqual(len(result), 80)
                self.assertLessEqual(len(result.encode("utf-8")), 240)
                with TemporaryDirectory() as temporary_directory:
                    Path(temporary_directory, result).mkdir()

    def test_empty_or_dot_only_names_are_replaced(self):
        self.assertEqual("未命名", safe_filename("..."))


if __name__ == "__main__":
    unittest.main()
