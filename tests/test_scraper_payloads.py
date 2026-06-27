import unittest

from core.scraper_payloads import (
    build_answer_item,
    build_article_item,
    build_question_answer_item,
)


class ScraperPayloadTests(unittest.TestCase):
    def test_build_article_item_preserves_header_image(self):
        item = build_article_item(
            url="https://zhuanlan.zhihu.com/p/1",
            article_id="1",
            data={
                "title": "专栏标题",
                "content": "<p>body</p>",
                "image_url": "https://pic.zhimg.com/v2-demo.jpg",
                "author": {"name": "作者"},
                "created": 1712073600,
            },
        )
        self.assertEqual(item["type"], "article")
        self.assertIn("TitleImage", item["html"])
        self.assertEqual(item["author"], "作者")

    def test_build_answer_item_uses_question_title(self):
        item = build_answer_item(
            url="https://www.zhihu.com/question/1/answer/2",
            answer_id="2",
            data={
                "question": {"title": "问题标题"},
                "author": {"name": "回答者"},
                "content": "<p>answer</p>",
            },
        )
        self.assertEqual(item["title"], "问题标题")
        self.assertEqual(item["author"], "回答者")

    def test_build_question_answer_item_generates_question_answer_url(self):
        item = build_question_answer_item(
            question_id="123",
            data={
                "id": "456",
                "question": {"title": "问题"},
                "author": {"name": "作者"},
            },
        )
        self.assertEqual(item["url"], "https://www.zhihu.com/question/123/answer/456")

if __name__ == "__main__":
    unittest.main()
