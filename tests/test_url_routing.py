import unittest

from zhihu_scraper.urls import (
    TargetKind,
    UnsupportedZhihuUrlError,
    route_zhihu_url,
)


class ZhihuUrlRoutingTests(unittest.TestCase):
    def test_routes_and_normalizes_a_zhuanlan_article(self):
        target = route_zhihu_url(
            " http://ZHUANLAN.ZHIHU.COM/p/357892158/?utm_source=share#comments "
        )

        self.assertEqual(TargetKind.ARTICLE, target.kind)
        self.assertEqual("357892158", target.content_id)
        self.assertIsNone(target.question_id)
        self.assertEqual(
            "https://zhuanlan.zhihu.com/p/357892158",
            target.canonical_url,
        )

    def test_routes_both_single_answer_url_forms(self):
        cases = (
            (
                "https://www.zhihu.com/question/28696373/answer/2835848212/",
                "https://www.zhihu.com/question/28696373/answer/2835848212",
                "28696373",
            ),
            (
                "https://www.zhihu.com/answer/2835848212?utm_campaign=share",
                "https://www.zhihu.com/answer/2835848212",
                None,
            ),
        )

        for raw_url, canonical_url, question_id in cases:
            with self.subTest(raw_url=raw_url):
                target = route_zhihu_url(raw_url)

                self.assertEqual(TargetKind.ANSWER, target.kind)
                self.assertEqual("2835848212", target.content_id)
                self.assertEqual(question_id, target.question_id)
                self.assertEqual(canonical_url, target.canonical_url)

    def test_routes_a_question_as_the_multiple_answer_target(self):
        target = route_zhihu_url("https://www.zhihu.com/question/28696373?utm_source=share#answers")

        self.assertEqual(TargetKind.QUESTION, target.kind)
        self.assertEqual("28696373", target.content_id)
        self.assertEqual("28696373", target.question_id)
        self.assertEqual(
            "https://www.zhihu.com/question/28696373",
            target.canonical_url,
        )

    def test_routes_an_entire_column_and_preserves_its_token(self):
        target = route_zhihu_url(
            "https://www.zhihu.com/column/Machine-Learning_PKU/?utm_source=share"
        )

        self.assertEqual(TargetKind.COLUMN, target.kind)
        self.assertEqual("Machine-Learning_PKU", target.content_id)
        self.assertIsNone(target.question_id)
        self.assertEqual(
            "https://www.zhihu.com/column/Machine-Learning_PKU",
            target.canonical_url,
        )

    def test_routes_a_standalone_zvideo(self):
        target = route_zhihu_url("https://www.zhihu.com/zvideo/1666569497233207296/#player")

        self.assertEqual(TargetKind.VIDEO, target.kind)
        self.assertEqual("1666569497233207296", target.content_id)
        self.assertIsNone(target.question_id)
        self.assertEqual(
            "https://www.zhihu.com/zvideo/1666569497233207296",
            target.canonical_url,
        )

    def test_rejected_zhihu_sections_explain_which_capability_is_unsupported(self):
        cases = (
            ("https://www.zhihu.com/people/example", "作者主页"),
            ("https://www.zhihu.com/collection/123", "收藏夹"),
            ("https://www.zhihu.com/search?q=机器学习", "搜索结果"),
            ("https://www.zhihu.com/pin/123", "想法"),
            ("https://www.zhihu.com/market/paid_column/123", "盐选"),
            ("https://www.zhihu.com/salt/123", "盐选"),
        )

        for raw_url, capability in cases:
            with self.subTest(raw_url=raw_url):
                with self.assertRaisesRegex(
                    UnsupportedZhihuUrlError,
                    rf"{capability}.*暂不支持",
                ):
                    route_zhihu_url(raw_url)

    def test_rejects_unknown_hosts_without_accepting_lookalike_domains(self):
        cases = (
            "https://example.com/question/123",
            "https://www.zhihu.com.example.org/question/123",
        )

        for raw_url in cases:
            with self.subTest(raw_url=raw_url):
                with self.assertRaisesRegex(
                    UnsupportedZhihuUrlError,
                    r"仅支持知乎官方域名.*example",
                ):
                    route_zhihu_url(raw_url)

    def test_unknown_zhihu_routes_list_the_supported_target_types(self):
        with self.assertRaisesRegex(
            UnsupportedZhihuUrlError,
            r"仅支持.*文章、回答、问题、专栏和独立视频",
        ):
            route_zhihu_url("https://www.zhihu.com/hot")

    def test_malformed_inputs_have_actionable_errors(self):
        cases = (
            ("", "链接不能为空"),
            ("www.zhihu.com/question/123", "http:// 或 https://"),
            ("ftp://www.zhihu.com/question/123", "http:// 或 https://"),
            ("https://[invalid", "无法解析"),
        )

        for raw_url, explanation in cases:
            with self.subTest(raw_url=raw_url):
                with self.assertRaisesRegex(
                    UnsupportedZhihuUrlError,
                    explanation,
                ):
                    route_zhihu_url(raw_url)


if __name__ == "__main__":
    unittest.main()
