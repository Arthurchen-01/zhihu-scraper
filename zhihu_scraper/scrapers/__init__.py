"""Zhihu Scrapers Collection."""

from .author import AuthorScraper
from .column import ColumnScraper
from .article import ArticleScraper
from .answer import AnswerScraper
from .pin import PinScraper
from .comment import CommentScraper

__all__ = [
    "AuthorScraper",
    "ColumnScraper",
    "ArticleScraper",
    "AnswerScraper",
    "PinScraper",
    "CommentScraper"
]
