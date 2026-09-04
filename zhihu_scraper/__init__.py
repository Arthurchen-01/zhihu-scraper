"""Zhihu Scraper & Archival Toolkit.
Modular, robust, and extensible scraper for articles, columns, answers, pins, comments, and visual screenshots.
"""

__version__ = "1.0.0"
__all__ = [
    "ZhihuClient",
    "AuthorScraper",
    "ColumnScraper",
    "ArticleScraper",
    "AnswerScraper",
    "PinScraper",
    "CommentScraper",
    "VisualArchiver"
]

from .client import ZhihuClient
from .scrapers.author import AuthorScraper
from .scrapers.column import ColumnScraper
from .scrapers.article import ArticleScraper
from .scrapers.answer import AnswerScraper
from .scrapers.pin import PinScraper
from .scrapers.comment import CommentScraper
from .visual.screenshot import VisualArchiver
