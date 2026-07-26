"""Public archive workflow: route, fetch, normalize, enrich, and save."""

from __future__ import annotations

from collections.abc import Callable, Iterator, Mapping
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from types import TracebackType
from typing import Any, Protocol, Self

from .comments import CommentClient, fetch_comment_thread
from .domain import (
    Answer,
    ArchiveTarget,
    Article,
    ColumnArchive,
    ColumnRef,
    QuestionArchive,
)
from .http import TransportError, ZhihuHttpError
from .normalize import (
    normalize_answer,
    normalize_article,
    normalize_column,
    normalize_question,
    normalize_video,
)
from .settings import ArchiveSettings, BrowserFallback as BrowserFallbackMode
from .source import InvalidZhihuPayloadError, extract_entity_payload
from .urls import TargetKind, ZhihuTarget, route_zhihu_url


class ArchiveSink(Protocol):
    def archive(self, target: ArchiveTarget) -> object: ...


class PayloadSource(Protocol):
    def fetch_article_payload(self, target: ZhihuTarget) -> Mapping[str, object]: ...

    def fetch_answer_payload(self, target: ZhihuTarget) -> Mapping[str, object]: ...

    def fetch_question_payload(self, target: ZhihuTarget) -> Mapping[str, object]: ...

    def iter_question_answer_payloads(
        self,
        target: ZhihuTarget,
        *,
        page_size: int,
    ) -> Iterator[Mapping[str, object]]: ...

    def fetch_column_payload(self, target: ZhihuTarget) -> Mapping[str, object]: ...

    def iter_column_article_payloads(
        self,
        target: ZhihuTarget,
        *,
        page_size: int,
    ) -> Iterator[Mapping[str, object]]: ...

    def fetch_video_payload(self, target: ZhihuTarget) -> Mapping[str, object]: ...


class BrowserReader(Protocol):
    def set_cookie_dict(self, cookies: dict[str, str]) -> None: ...

    def fetch_html(self, url: str) -> str: ...

    def __enter__(self) -> Self: ...

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> object: ...


class BrowserFallbackUnavailable(RuntimeError):
    """HTTP failed and no configured browser fallback can continue."""


@dataclass(frozen=True, slots=True)
class ArchiveReport:
    target: ArchiveTarget
    receipt: object
    used_browser: bool


class ArchiveWorkflow:
    """One testable use case behind the project's public archive behavior."""

    def __init__(
        self,
        *,
        source: PayloadSource,
        sink: ArchiveSink,
        settings: ArchiveSettings,
        comment_client: CommentClient | None = None,
        browser_factory: Callable[[], BrowserReader] | None = None,
        browser_cookies: Mapping[str, str] | None = None,
        clock: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
    ) -> None:
        self._source = source
        self._sink = sink
        self._settings = settings
        self._comment_client = comment_client
        self._browser_factory = browser_factory
        self._browser_cookies = dict(browser_cookies or {})
        self._clock = clock
        self._used_browser = False

    def run(self, raw_url: str) -> ArchiveReport:
        self._used_browser = False
        routed = route_zhihu_url(raw_url)
        target = self._collect(routed)
        receipt = self._sink.archive(target)
        return ArchiveReport(
            target=target,
            receipt=receipt,
            used_browser=self._used_browser,
        )

    def _collect(self, target: ZhihuTarget) -> ArchiveTarget:
        if target.kind is TargetKind.ARTICLE:
            payload = self._single_payload(
                target,
                direct=lambda: self._source.fetch_article_payload(target),
                collection="articles",
            )
            article = normalize_article(payload, source_url=target.canonical_url)
            return self._with_article_comments(article)

        if target.kind is TargetKind.ANSWER:
            payload = self._single_payload(
                target,
                direct=lambda: self._source.fetch_answer_payload(target),
                collection="answers",
            )
            answer = normalize_answer(payload, source_url=target.canonical_url)
            return self._with_answer_comments(answer)

        if target.kind is TargetKind.QUESTION:
            question_payload = self._single_payload(
                target,
                direct=lambda: self._source.fetch_question_payload(target),
                collection="questions",
            )
            question = normalize_question(
                question_payload,
                source_url=target.canonical_url,
            )
            answers = tuple(
                self._with_answer_comments(normalize_answer(payload))
                for payload in self._source.iter_question_answer_payloads(
                    target,
                    page_size=self._settings.page_size,
                )
            )
            return QuestionArchive(
                question=question,
                answers=answers,
                archived_at=self._clock(),
            )

        if target.kind is TargetKind.COLUMN:
            column_payload = self._single_payload(
                target,
                direct=lambda: self._source.fetch_column_payload(target),
                collection="columns",
            )
            column = normalize_column(
                column_payload,
                source_url=target.canonical_url,
            )
            origin = ColumnRef(
                token=column.token,
                title=column.title,
                url=column.source_url,
            )
            articles: list[Article] = []
            for payload in self._source.iter_column_article_payloads(
                target,
                page_size=self._settings.page_size,
            ):
                article = normalize_article(payload)
                if all(item.token != origin.token for item in article.columns):
                    article = replace(
                        article,
                        columns=(*article.columns, origin),
                    )
                articles.append(self._with_article_comments(article))
            if column.item_count == 0 and articles:
                column = replace(column, item_count=len(articles))
            return ColumnArchive(
                column=column,
                articles=tuple(articles),
                archived_at=self._clock(),
            )

        if target.kind is TargetKind.VIDEO:
            payload = self._single_payload(
                target,
                direct=lambda: self._source.fetch_video_payload(target),
                collection="zvideos",
            )
            video = normalize_video(payload, source_url=target.canonical_url)
            if not self._settings.comments:
                return video
            thread = self._comments("zvideo", video.id)
            return replace(video, comments=thread)

        raise AssertionError(f"unhandled target kind: {target.kind}")

    def _single_payload(
        self,
        target: ZhihuTarget,
        *,
        direct: Callable[[], Mapping[str, object]],
        collection: str,
    ) -> Mapping[str, object]:
        mode = self._settings.browser_fallback
        if mode is BrowserFallbackMode.ALWAYS:
            return self._browser_payload(target, collection=collection)
        try:
            return direct()
        except (InvalidZhihuPayloadError, ZhihuHttpError, TransportError):
            if mode is BrowserFallbackMode.NEVER:
                raise
            return self._browser_payload(target, collection=collection)

    def _browser_payload(
        self,
        target: ZhihuTarget,
        *,
        collection: str,
    ) -> Mapping[str, object]:
        if self._browser_factory is None:
            raise BrowserFallbackUnavailable(
                "HTTP 抓取失败，但当前没有配置浏览器回退。"
            )
        with self._browser_factory() as browser:
            if self._browser_cookies:
                browser.set_cookie_dict(self._browser_cookies)
            document = browser.fetch_html(target.canonical_url)
        self._used_browser = True
        return extract_entity_payload(
            document,
            collection=collection,
            entity_id=target.content_id,
        )

    def _with_article_comments(self, article: Article) -> Article:
        if not self._settings.comments:
            return article
        return replace(
            article,
            comments=self._comments("article", article.id),
        )

    def _with_answer_comments(self, answer: Answer) -> Answer:
        if not self._settings.comments:
            return answer
        return replace(
            answer,
            comments=self._comments("answer", answer.id),
        )

    def _comments(self, target_kind: str, target_id: str):
        if self._comment_client is None:
            raise RuntimeError("评论已启用，但没有可用的知乎请求客户端。")
        return fetch_comment_thread(
            self._comment_client,
            target_kind=target_kind,
            target_id=target_id,
            root_limit=self._settings.comment_roots,
            reply_limit=self._settings.comment_replies,
        )
