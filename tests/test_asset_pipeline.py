import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from zhihu_scraper.assets import archive_assets
from zhihu_scraper.domain import (
    Answer,
    Article,
    Author,
    Column,
    ColumnArchive,
    Comment,
    CommentThread,
    ListBlock,
    MediaAsset,
    MediaBlock,
    MediaKind,
    MediaRendition,
    Paragraph,
    Question,
    QuestionArchive,
    QuestionRef,
    Quote,
    Text,
    Video,
)
from zhihu_scraper.media import MediaDownloadReceipt


NOW = datetime(2026, 7, 27, tzinfo=timezone.utc)
AUTHOR = Author(id="writer", name="作者")


class RecordingDownloader:
    def __init__(self) -> None:
        self.calls: list[tuple[str, Path]] = []

    def __call__(self, source_url: str, destination: Path) -> MediaDownloadReceipt:
        self.calls.append((source_url, destination))
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(source_url.encode())
        return MediaDownloadReceipt(
            source_url=source_url,
            destination=destination,
            resumed_from=0,
            bytes_total=destination.stat().st_size,
        )


def image(
    asset_id: str,
    source_url: str,
    *,
    alternate_url: str | None = None,
    kind: MediaKind = MediaKind.IMAGE,
) -> MediaAsset:
    renditions = [
        MediaRendition(source_url, mime_type="image/gif" if kind is MediaKind.ANIMATION else None)
    ]
    if alternate_url is not None:
        renditions.append(MediaRendition(alternate_url, width=2000, height=1200))
    return MediaAsset(id=asset_id, kind=kind, renditions=tuple(renditions))


class AssetPipelineTests(unittest.TestCase):
    def test_recursively_archives_article_assets_and_deduplicates_asset_ids(self):
        original = "https://pic.example/original.png?source=zhihu"
        alternate = "https://pic.example/large.jpg"
        animation_url = "https://pic.example/demo?format=gif"
        duplicate = image("hero", "https://pic.example/duplicate.jpg")
        article = Article(
            id="1",
            title="文章",
            source_url="https://zhuanlan.zhihu.com/p/1",
            author=AUTHOR,
            published_at=NOW,
            blocks=(
                MediaBlock(image("hero", original, alternate_url=alternate)),
                Quote(
                    (
                        ListBlock(
                            ordered=False,
                            items=(
                                (
                                    MediaBlock(
                                        image(
                                            "animation",
                                            animation_url,
                                            kind=MediaKind.ANIMATION,
                                        )
                                    ),
                                ),
                            ),
                        ),
                    )
                ),
                MediaBlock(duplicate),
            ),
            comments=CommentThread(
                comments=(
                    Comment(
                        id="c1",
                        author=None,
                        blocks=(MediaBlock(image("comment-image", "https://pic.example/c.webp")),),
                        created_at=None,
                        like_count=0,
                    ),
                ),
                order="api",
            ),
        )
        downloader = RecordingDownloader()

        with tempfile.TemporaryDirectory() as temporary_directory:
            media_directory = Path(temporary_directory) / "entry" / "media"
            result = archive_assets(
                article,
                media_directory,
                downloader=downloader,
            )

            self.assertEqual(
                [original, animation_url, "https://pic.example/c.webp"],
                [source for source, _ in downloader.calls],
            )
            self.assertEqual(3, len(result.downloads))
            self.assertTrue(all(path.is_file() for _, path in downloader.calls))
            self.assertTrue(downloader.calls[0][1].name.endswith(".png"))
            self.assertTrue(downloader.calls[1][1].name.endswith(".gif"))
            self.assertTrue(downloader.calls[2][1].name.endswith(".webp"))
            self.assertEqual(result.source_paths[original], result.source_paths[alternate])
            self.assertNotIn("https://pic.example/duplicate.jpg", result.source_paths)
            self.assertTrue(
                all(
                    relative.startswith("media/")
                    and "\\" not in relative
                    and ".." not in relative
                    for relative in result.source_paths.values()
                )
            )

    def test_video_uses_largest_known_resolution_and_archives_cover_and_description(self):
        low = MediaRendition("https://video.example/low.mp4", width=640, height=360)
        unknown = MediaRendition(
            "https://video.example/unknown.mp4",
            bitrate=99_000_000,
        )
        high = MediaRendition(
            "https://video.example/high",
            mime_type="video/mp4",
            width=1920,
            height=1080,
        )
        video = Video(
            id="1666569497233207296",
            title="训练方案",
            source_url="https://www.zhihu.com/zvideo/1666569497233207296",
            author=AUTHOR,
            published_at=NOW,
            description=(
                MediaBlock(image("description", "https://pic.example/description.jpg")),
            ),
            asset=MediaAsset(
                id="zvideo-1666569497233207296",
                kind=MediaKind.VIDEO,
                renditions=(low, unknown, high),
            ),
            cover_url="https://pic.example/cover.avif",
        )
        downloader = RecordingDownloader()

        with tempfile.TemporaryDirectory() as temporary_directory:
            result = archive_assets(
                video,
                Path(temporary_directory) / "media",
                downloader=downloader,
            )

        self.assertEqual(
            [
                "https://video.example/high",
                "https://pic.example/description.jpg",
                "https://pic.example/cover.avif",
            ],
            [source for source, _ in downloader.calls],
        )
        self.assertTrue(downloader.calls[0][1].name.endswith(".mp4"))
        self.assertEqual(
            result.source_paths["https://video.example/low.mp4"],
            result.source_paths["https://video.example/high"],
        )

    def test_question_and_column_archives_recurse_into_children(self):
        answer = Answer(
            id="answer",
            question=QuestionRef("q", "问题", "https://www.zhihu.com/question/q"),
            source_url="https://www.zhihu.com/question/q/answer/answer",
            author=AUTHOR,
            published_at=NOW,
            blocks=(MediaBlock(image("answer-image", "https://pic.example/a.jpg")),),
        )
        question = QuestionArchive(
            question=Question(
                id="q",
                title="问题",
                source_url="https://www.zhihu.com/question/q",
                detail=(MediaBlock(image("detail-image", "https://pic.example/q.png")),),
            ),
            answers=(answer,),
            archived_at=NOW,
        )
        article = Article(
            id="article",
            title="文章",
            source_url="https://zhuanlan.zhihu.com/p/article",
            author=AUTHOR,
            published_at=NOW,
            blocks=(MediaBlock(image("article-image", "https://pic.example/article.webp")),),
        )
        column = ColumnArchive(
            column=Column(
                token="column",
                title="专栏",
                source_url="https://www.zhihu.com/column/column",
                description="",
                author=AUTHOR,
                item_count=1,
            ),
            articles=(article,),
            archived_at=NOW,
        )

        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            question_downloader = RecordingDownloader()
            column_downloader = RecordingDownloader()
            archive_assets(
                question,
                root / "question" / "media",
                downloader=question_downloader,
            )
            archive_assets(
                column,
                root / "column" / "media",
                downloader=column_downloader,
            )

        self.assertEqual(
            ["https://pic.example/q.png", "https://pic.example/a.jpg"],
            [source for source, _ in question_downloader.calls],
        )
        self.assertEqual(
            ["https://pic.example/article.webp"],
            [source for source, _ in column_downloader.calls],
        )

    def test_empty_target_does_not_create_media_directory(self):
        article = Article(
            id="empty",
            title="空文章",
            source_url="https://zhuanlan.zhihu.com/p/empty",
            author=AUTHOR,
            published_at=None,
            blocks=(Paragraph((Text("只有正文"),)),),
        )

        with tempfile.TemporaryDirectory() as temporary_directory:
            media_directory = Path(temporary_directory) / "media"
            result = archive_assets(article, media_directory, downloader=RecordingDownloader())

            self.assertFalse(media_directory.exists())
            self.assertEqual({}, dict(result.source_paths))
            self.assertEqual((), result.downloads)


if __name__ == "__main__":
    unittest.main()
