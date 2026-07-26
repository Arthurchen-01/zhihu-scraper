import unittest
from datetime import datetime, timezone

from zhihu_scraper.comments import fetch_comment_thread


class FakeClient:
    def __init__(self, responses):
        self.responses = dict(responses)
        self.calls = []

    def get_json(self, url):
        self.calls.append(url)
        return self.responses[url]


class CommentFetchingTests(unittest.TestCase):
    def test_article_comments_preserve_api_order_and_normalize_replies(self):
        root_url = (
            "/api/v4/comment_v5/articles/123/root_comment"
            "?limit=10&offset="
        )
        reply_url = (
            "/api/v4/comment_v5/comment/900/child_comment"
            "?limit=10&offset="
        )
        client = FakeClient(
            {
                root_url: {
                    "data": [
                        {
                            "id": 900,
                            "content": "<p>一级 <strong>评论</strong></p>",
                            "created_time": 1_700_000_000,
                            "like_count": 7,
                            "author": {
                                "member": {
                                    "id": "member-1",
                                    "name": "甲",
                                    "url_token": "member-one",
                                }
                            },
                        }
                    ],
                    "paging": {"is_end": True, "next": ""},
                },
                reply_url: {
                    "data": [
                        {
                            "id": "901",
                            "content": "<p>二级回复</p>",
                            "created_time": 1_700_000_001,
                            "like_count": 2,
                            "author": None,
                        }
                    ],
                    "paging": {"is_end": True, "next": None},
                },
            }
        )

        thread = fetch_comment_thread(
            client,
            target_kind="article",
            target_id="123",
        )

        self.assertEqual(client.calls, [root_url, reply_url])
        self.assertEqual(tuple(comment.id for comment in thread.comments), ("900",))
        self.assertEqual(thread.order, "api_returned")
        self.assertTrue(thread.roots_complete)
        root = thread.comments[0]
        self.assertEqual(root.author.name, "甲")
        self.assertEqual(
            root.author.url,
            "https://www.zhihu.com/people/member-one",
        )
        self.assertEqual(
            root.created_at,
            datetime.fromtimestamp(1_700_000_000, tz=timezone.utc),
        )
        self.assertEqual(root.like_count, 7)
        self.assertEqual(root.replies[0].id, "901")
        self.assertIsNone(root.replies[0].author)
        self.assertTrue(root.replies_complete)

    def test_root_pagination_stops_at_the_injected_limit_and_marks_truncation(self):
        first_page = (
            "/api/v4/comment_v5/answers/456/root_comment"
            "?limit=3&offset="
        )
        second_page = (
            "https://www.zhihu.com/api/v4/comment_v5/answers/456/root_comment"
            "?offset=cursor-2&limit=3"
        )
        empty_replies = {
            (
                f"/api/v4/comment_v5/comment/{comment_id}/child_comment"
                "?limit=10&offset="
            ): {
                "data": [],
                "paging": {"is_end": True, "next": ""},
            }
            for comment_id in ("1", "2", "3")
        }
        client = FakeClient(
            {
                first_page: {
                    "data": [
                        _comment_payload(1, "第一条"),
                        _comment_payload(2, "第二条"),
                    ],
                    "paging": {"is_end": False, "next": second_page},
                },
                second_page: {
                    "data": [
                        _comment_payload(3, "第三条"),
                        _comment_payload(4, "不应保留"),
                    ],
                    "paging": {"is_end": True, "next": ""},
                },
                **empty_replies,
            }
        )

        thread = fetch_comment_thread(
            client,
            target_kind="answer",
            target_id="456",
            root_limit=3,
        )

        self.assertEqual(tuple(comment.id for comment in thread.comments), ("1", "2", "3"))
        self.assertFalse(thread.roots_complete)
        self.assertIn(second_page, client.calls)
        self.assertNotIn(
            "/api/v4/comment_v5/comment/4/child_comment?limit=10&offset=",
            client.calls,
        )

    def test_reply_pagination_is_bounded_independently_for_zvideo(self):
        root_url = (
            "/api/v4/comment_v5/zvideos/789/root_comment"
            "?limit=10&offset="
        )
        first_replies = (
            "/api/v4/comment_v5/comment/20/child_comment"
            "?limit=3&offset="
        )
        second_replies = (
            "https://www.zhihu.com/api/v4/comment_v5/comment/20/child_comment"
            "?offset=cursor-2&limit=3"
        )
        client = FakeClient(
            {
                root_url: {
                    "data": [_comment_payload(20, "视频一级评论")],
                    "paging": {"is_end": True, "next": ""},
                },
                first_replies: {
                    "data": [
                        _comment_payload(21, "回复一"),
                        _comment_payload(22, "回复二"),
                    ],
                    "paging": {"is_end": False, "next": second_replies},
                },
                second_replies: {
                    "data": [
                        _comment_payload(23, "回复三"),
                        _comment_payload(24, "不应保留"),
                    ],
                    "paging": {"is_end": True, "next": ""},
                },
            }
        )

        thread = fetch_comment_thread(
            client,
            target_kind="zvideo",
            target_id="789",
            reply_limit=3,
        )

        self.assertTrue(thread.roots_complete)
        self.assertEqual(
            tuple(reply.id for reply in thread.comments[0].replies),
            ("21", "22", "23"),
        )
        self.assertFalse(thread.comments[0].replies_complete)
        self.assertEqual(thread.reply_limit, 3)

    def test_comment_limits_must_be_positive_integers(self):
        client = FakeClient({})

        invalid_limits = (
            {"root_limit": 0},
            {"root_limit": -1},
            {"root_limit": True},
            {"reply_limit": 0},
            {"reply_limit": 1.5},
        )
        for limits in invalid_limits:
            with self.subTest(limits=limits):
                with self.assertRaisesRegex(
                    ValueError,
                    "positive integer",
                ):
                    fetch_comment_thread(
                        client,
                        target_kind="article",
                        target_id="123",
                        **limits,
                    )

        self.assertEqual(client.calls, [])

    def test_explicit_zero_child_count_needs_no_second_request(self):
        root_url = (
            "/api/v4/comment_v5/articles/321/root_comment"
            "?limit=10&offset="
        )
        root = _comment_payload(30, "没有回复")
        root["child_comment_count"] = 0
        client = FakeClient(
            {
                root_url: {
                    "data": [root],
                    "paging": {"is_end": True, "next": ""},
                }
            }
        )

        thread = fetch_comment_thread(
            client,
            target_kind="article",
            target_id="321",
        )

        self.assertEqual(client.calls, [root_url])
        self.assertEqual(thread.comments[0].replies, ())
        self.assertTrue(thread.comments[0].replies_complete)

    def test_anonymous_and_deleted_authors_are_normalized_without_fake_identity(self):
        root_url = (
            "/api/v4/comment_v5/answers/654/root_comment"
            "?limit=10&offset="
        )
        anonymous = _comment_payload(40, "匿名评论")
        anonymous["author"] = {
            "id": "",
            "name": "匿名用户",
            "url_token": "",
            "is_anonymous": True,
        }
        anonymous["child_comment_count"] = 0
        deleted = _comment_payload(41, "作者已删除")
        deleted["author"] = {}
        deleted["child_comment_count"] = 0
        client = FakeClient(
            {
                root_url: {
                    "data": [anonymous, deleted],
                    "paging": {"is_end": True, "next": ""},
                }
            }
        )

        thread = fetch_comment_thread(
            client,
            target_kind="answer",
            target_id="654",
        )

        self.assertEqual(
            tuple(comment.id for comment in thread.comments),
            ("40", "41"),
        )
        self.assertEqual(thread.comments[0].author.name, "匿名用户")
        self.assertIsNone(thread.comments[0].author.id)
        self.assertIsNone(thread.comments[0].author.url)
        self.assertIsNone(thread.comments[1].author)

    def test_malformed_comment_scalars_are_rejected_instead_of_guessed(self):
        root_url = (
            "/api/v4/comment_v5/articles/987/root_comment"
            "?limit=10&offset="
        )
        for field, invalid_value in (
            ("created_time", "昨天"),
            ("like_count", "很多"),
        ):
            with self.subTest(field=field):
                malformed = _comment_payload(50, "坏数据")
                malformed[field] = invalid_value
                client = FakeClient(
                    {
                        root_url: {
                            "data": [malformed],
                            "paging": {"is_end": True, "next": ""},
                        }
                    }
                )

                with self.assertRaisesRegex(ValueError, field):
                    fetch_comment_thread(
                        client,
                        target_kind="article",
                        target_id="987",
                    )


def _comment_payload(comment_id, content):
    return {
        "id": comment_id,
        "content": f"<p>{content}</p>",
        "created_time": 1_700_000_000,
        "like_count": 0,
        "author": {"member": {"name": "测试用户"}},
    }


if __name__ == "__main__":
    unittest.main()
