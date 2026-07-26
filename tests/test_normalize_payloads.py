import unittest
from datetime import datetime, timezone

from zhihu_scraper.domain import MediaKind
from zhihu_scraper.normalize import (
    normalize_answer,
    normalize_article,
    normalize_column,
    normalize_question,
    normalize_video,
)


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

    def test_answer_payload_keeps_its_question_relationship(self):
        answer = normalize_answer(
            {
                "id": 2835848212,
                "content": "<p>这是一条回答。</p>",
                "created_time": 1672502400,
                "updated_time": 1672588800,
                "voteup_count": 42,
                "author": {"id": "author-id", "name": "回答者"},
                "question": {"id": 28696373, "title": "如何理解机器学习？"},
            }
        )

        self.assertEqual("2835848212", answer.id)
        self.assertEqual("28696373", answer.question.id)
        self.assertEqual("如何理解机器学习？", answer.title)
        self.assertEqual(
            "https://www.zhihu.com/question/28696373/answer/2835848212",
            answer.source_url,
        )
        self.assertEqual(42, answer.voteup_count)
        self.assertIsNone(answer.comments)

    def test_question_payload_keeps_detail_and_counts(self):
        question = normalize_question(
            {
                "id": 28696373,
                "title": "如何理解机器学习？",
                "detail": "<p>请给出直观解释。</p>",
                "created": 1451606400,
                "updated_time": 1451692800,
                "answer_count": 123,
                "follower_count": 456,
            }
        )

        self.assertEqual("28696373", question.id)
        self.assertEqual("如何理解机器学习？", question.title)
        self.assertEqual(1, len(question.detail))
        self.assertEqual(123, question.answer_count)
        self.assertEqual(456, question.follower_count)

    def test_column_payload_uses_items_count_and_canonical_url(self):
        column = normalize_column(
            {
                "id": "machinelearningpku",
                "title": "机器学习",
                "description": "介绍深度学习与自然语言处理",
                "items_count": 81,
                "author": {
                    "id": "column-author",
                    "name": "习翔宇",
                    "url_token": "xi-xiang-yu",
                },
            }
        )

        self.assertEqual("machinelearningpku", column.token)
        self.assertEqual(81, column.item_count)
        self.assertEqual(
            "https://www.zhihu.com/column/machinelearningpku",
            column.source_url,
        )

    def test_video_payload_retains_all_renditions_for_highest_quality_selection(self):
        video = normalize_video(
            {
                "id": 1666569497233207296,
                "title": "哑铃全身训练方案",
                "description": "<p>一对哑铃练遍全身。</p>",
                "published_at": 1680000000,
                "author": {"id": "fitness", "name": "飞特那斯"},
                "thumbnail": "https://pic.example/cover.jpg",
                "video": {
                    "playlist": {
                        "hd": {
                            "play_url": "https://video.example/720.mp4",
                            "width": 1280,
                            "height": 720,
                            "size": 20,
                            "format": "mp4",
                        },
                        "fhd": {
                            "play_url": "https://video.example/1080.mp4",
                            "width": 1920,
                            "height": 1080,
                            "size": 40,
                            "format": "mp4",
                        },
                    }
                },
            }
        )

        self.assertEqual(MediaKind.VIDEO, video.asset.kind)
        self.assertEqual(2, len(video.asset.renditions))
        self.assertEqual(
            "https://video.example/1080.mp4",
            max(
                video.asset.renditions,
                key=lambda item: (item.width or 0) * (item.height or 0),
            ).source_url,
        )
        self.assertEqual("https://pic.example/cover.jpg", video.cover_url)
