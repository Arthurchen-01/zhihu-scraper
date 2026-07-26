import unittest
from datetime import datetime, timezone

from zhihu_scraper.normalize import normalize_article


class ZhihuPayloadNormalizationTests(unittest.TestCase):
    def test_article_payload_keeps_identity_timestamps_and_all_column_memberships(self):
        payload = {
            "id": 357892158,
            "title": " 一文归纳Ai数据增强之法 ",
            "content": "<p>数据决定了 AI 模型学习的上限。</p>",
            "created": 1615950180,
            "updated": 1617090407,
            "voteup_count": 7,
            "image_url": "https://pic.example/cover.jpg",
            "author": {
                "id": "0d5f195831e5e99bf216291b05f553a0",
                "name": "泳鱼",
                "url_token": "yong-yu",
            },
            "column": {
                "id": "hsmyy",
                "title": "无痛的机器学习",
                "url": "https://www.zhihu.com/column/hsmyy",
            },
            "contributions": [
                {
                    "id": "machinelearningpku",
                    "title": "机器学习",
                    "url": "https://www.zhihu.com/column/machinelearningpku",
                }
            ],
        }

        article = normalize_article(
            payload,
            source_url="https://zhuanlan.zhihu.com/p/357892158",
        )

        self.assertEqual("357892158", article.id)
        self.assertEqual("一文归纳Ai数据增强之法", article.title)
        self.assertEqual("泳鱼", article.author.name)
        self.assertEqual(
            "0d5f195831e5e99bf216291b05f553a0",
            article.author.id,
        )
        self.assertEqual("https://www.zhihu.com/people/yong-yu", article.author.url)
        self.assertEqual(
            datetime.fromtimestamp(1615950180, tz=timezone.utc),
            article.published_at,
        )
        self.assertEqual(
            datetime.fromtimestamp(1617090407, tz=timezone.utc),
            article.updated_at,
        )
        self.assertEqual(7, article.voteup_count)
        self.assertEqual("https://pic.example/cover.jpg", article.cover_url)
        self.assertEqual(
            ("hsmyy", "machinelearningpku"),
            tuple(column.token for column in article.columns),
        )
        self.assertIsNone(article.comments)
