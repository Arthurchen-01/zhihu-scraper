import unittest
from datetime import datetime, timezone

from zhihu_scraper.domain import (
    Answer,
    Article,
    Author,
    Column,
    ColumnArchive,
    ColumnRef,
    Comment,
    CommentThread,
    InlineFormula,
    Link,
    MediaAsset,
    MediaKind,
    MediaRendition,
    Paragraph,
    Question,
    QuestionArchive,
    QuestionRef,
    Text,
    Video,
)
from zhihu_scraper.render import (
    ColumnRenderContext,
    HtmlRenderer,
    MarkdownRenderer,
    RenderNavigationItem,
)


UTC = timezone.utc


def paragraph(value: str) -> Paragraph:
    return Paragraph(inlines=(Text(value),))


class ArchiveTargetRenderingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.author = Author(
            id="author-1",
            name="泳鱼",
            url="https://www.zhihu.com/people/swimmer",
        )
        self.root_comment = Comment(
            id="comment-1",
            author=self.author,
            blocks=(paragraph("一级评论正文"),),
            created_at=datetime(2025, 2, 3, tzinfo=UTC),
            like_count=7,
            replies=(
                Comment(
                    id="comment-2",
                    author=None,
                    blocks=(paragraph("二级回复正文"),),
                    created_at=None,
                    like_count=1,
                    replies_complete=True,
                ),
            ),
            replies_complete=True,
        )
        self.comments = CommentThread(
            comments=(self.root_comment,),
            order="api_returned",
            roots_complete=True,
        )

    def test_article_has_compact_column_context_and_comment_thread(self):
        article = Article(
            id="357892158",
            title="一文归纳AI数据增强之法",
            source_url="https://zhuanlan.zhihu.com/p/357892158",
            author=self.author,
            published_at=datetime(2021, 3, 17, tzinfo=UTC),
            blocks=(paragraph("文章正文"),),
            columns=(
                ColumnRef(
                    token="hsmyy",
                    title="机器学习与数学",
                    url="https://www.zhihu.com/column/hsmyy",
                ),
                ColumnRef(
                    token="machinelearningpku",
                    title="机器学习",
                    url="https://www.zhihu.com/column/machinelearningpku",
                ),
            ),
            comments=self.comments,
        )
        context = ColumnRenderContext(
            column=article.columns[1],
            directory=RenderNavigationItem(
                title="机器学习",
                markdown_href="../机器学习.md",
                html_href="../机器学习.html",
            ),
            previous=RenderNavigationItem(
                title="上一篇",
                markdown_href="上一篇.md",
                html_href="上一篇.html",
            ),
            next=RenderNavigationItem(
                title="下一篇",
                markdown_href="下一篇.md",
                html_href="下一篇.html",
            ),
        )

        markdown = MarkdownRenderer().render(article, column_context=context)
        rendered_html = HtmlRenderer().render(article, column_context=context)

        self.assertIn("收录专栏：", markdown)
        self.assertIn("[机器学习与数学]", markdown)
        self.assertIn("本次归档自：[机器学习]", markdown)
        self.assertIn("[查看完整目录](../机器学习.md)", markdown)
        self.assertIn("[上一篇：上一篇](上一篇.md)", markdown)
        self.assertIn("[下一篇：下一篇](下一篇.md)", markdown)
        self.assertIn("[返回目录](../机器学习.md)", markdown)
        self.assertIn("一级评论正文", markdown)
        self.assertIn("二级回复正文", markdown)

        self.assertIn('href="../机器学习.html"', rendered_html)
        self.assertIn('href="上一篇.html"', rendered_html)
        self.assertIn('href="../assets/archive.css"', rendered_html)
        self.assertIn('class="comments"', rendered_html)
        self.assertIn("二级回复正文", rendered_html)

    def test_answer_and_question_archive_render_without_article_assumptions(self):
        question_ref = QuestionRef(
            id="100",
            title="为什么要做归一化内容模型？",
            url="https://www.zhihu.com/question/100",
        )
        answer = Answer(
            id="200",
            question=question_ref,
            source_url="https://www.zhihu.com/question/100/answer/200",
            author=self.author,
            published_at=datetime(2025, 1, 2, tzinfo=UTC),
            blocks=(paragraph("回答正文"),),
            voteup_count=12,
            comments=self.comments,
        )
        second = Answer(
            id="201",
            question=question_ref,
            source_url="https://www.zhihu.com/question/100/answer/201",
            author=Author(id=None, name="匿名用户"),
            published_at=None,
            blocks=(paragraph("第二个回答"),),
        )
        archive = QuestionArchive(
            question=Question(
                id="100",
                title=question_ref.title,
                source_url=question_ref.url,
                detail=(paragraph("问题详情"),),
                answer_count=2,
            ),
            answers=(answer, second),
            archived_at=datetime(2025, 2, 1, tzinfo=UTC),
        )

        standalone = MarkdownRenderer().render(answer)
        markdown = MarkdownRenderer().render(archive)
        rendered_html = HtmlRenderer().render(archive)

        self.assertIn("# 为什么要做归一化内容模型？", standalone)
        self.assertIn("回答正文", standalone)
        self.assertIn("12 赞同", standalone)
        self.assertIn("共归档 2 个回答", markdown)
        self.assertIn("## 回答 1 · 泳鱼", markdown)
        self.assertIn("## 回答 2 · 匿名用户", markdown)
        self.assertIn("回答正文", markdown)
        self.assertIn("第二个回答", rendered_html)
        self.assertEqual(rendered_html.count('class="answer"'), 2)

    def test_column_is_a_year_grouped_directory_not_an_article_dump(self):
        column_ref = ColumnRef(
            token="machinelearningpku",
            title="机器学习",
            url="https://www.zhihu.com/column/machinelearningpku",
        )
        articles = (
            Article(
                id="1",
                title="新文章",
                source_url="https://zhuanlan.zhihu.com/p/1",
                author=self.author,
                published_at=datetime(2025, 1, 1, tzinfo=UTC),
                blocks=(paragraph("不应出现在专栏目录的正文甲"),),
                columns=(column_ref,),
            ),
            Article(
                id="2",
                title="旧文章",
                source_url="https://zhuanlan.zhihu.com/p/2",
                author=self.author,
                published_at=datetime(2023, 6, 1, tzinfo=UTC),
                blocks=(paragraph("不应出现在专栏目录的正文乙"),),
                columns=(column_ref,),
            ),
        )
        archive = ColumnArchive(
            column=Column(
                token=column_ref.token,
                title=column_ref.title,
                source_url=column_ref.url,
                description="介绍深度学习、传统机器学习、自然语言处理算法及实现",
                author=self.author,
                item_count=81,
            ),
            articles=articles,
            archived_at=datetime(2025, 2, 1, tzinfo=UTC),
        )

        markdown = MarkdownRenderer().render(archive)
        rendered_html = HtmlRenderer().render(archive)

        self.assertIn("本栏目共 81 篇", markdown)
        self.assertIn("## 2025 年", markdown)
        self.assertIn("## 2023 年", markdown)
        self.assertIn("[Markdown](内容/新文章.md)", markdown)
        self.assertIn("[HTML](内容/新文章.html)", markdown)
        self.assertNotIn("不应出现在专栏目录的正文", markdown)
        self.assertIn("本栏目共 81 篇", rendered_html)
        self.assertIn('href="内容/旧文章.html"', rendered_html)
        self.assertIn('href="内容/旧文章.md"', rendered_html)
        self.assertNotIn("不应出现在专栏目录的正文", rendered_html)

    def test_video_uses_local_media_and_retains_original_link(self):
        original = "https://video.example/highest.mp4"
        video = Video(
            id="1666569497233207296",
            title="哑铃全身训练方案",
            source_url="https://www.zhihu.com/zvideo/1666569497233207296",
            author=self.author,
            published_at=datetime(2023, 1, 1, tzinfo=UTC),
            description=(paragraph("视频简介"),),
            asset=MediaAsset(
                id="video-1",
                kind=MediaKind.VIDEO,
                renditions=(MediaRendition(source_url=original, width=1920, height=1080),),
            ),
        )
        paths = {original: "media/哑铃全身训练方案.mp4"}

        markdown = MarkdownRenderer().render(video, media_paths=paths)
        rendered_html = HtmlRenderer().render(video, media_paths=paths)

        self.assertIn("[播放或下载视频](media/哑铃全身训练方案.mp4)", markdown)
        self.assertIn(f"[原始视频链接]({original})", markdown)
        self.assertIn('src="media/哑铃全身训练方案.mp4"', rendered_html)
        self.assertIn(f'href="{original}"', rendered_html)
        self.assertNotIn("<script", rendered_html)

    def test_unsafe_links_are_not_emitted_as_clickable_urls(self):
        article = Article(
            id="unsafe",
            title="安全测试",
            source_url="https://zhuanlan.zhihu.com/p/unsafe",
            author=self.author,
            published_at=None,
            blocks=(
                Paragraph(
                    inlines=(
                        Link(label="危险链接", url="javascript:alert(1)"),
                        Text(" "),
                        InlineFormula(tex="<img onerror=alert(1)>"),
                    ),
                ),
            ),
        )

        markdown = MarkdownRenderer().render(article)
        rendered_html = HtmlRenderer().render(article)

        self.assertNotIn("javascript:", markdown)
        self.assertNotIn("javascript:", rendered_html)
        self.assertNotIn("<img onerror", rendered_html)
        self.assertIn("&lt;img onerror=alert(1)&gt;", rendered_html)


if __name__ == "__main__":
    unittest.main()
