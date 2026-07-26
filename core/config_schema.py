"""
config_schema.py - Configuration schema and parsing helpers.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Optional

LOCAL_RUNTIME_DIR = Path(".local")
DEFAULT_COOKIE_FILE = LOCAL_RUNTIME_DIR / "cookies.json"
DEFAULT_LOG_DIR = LOCAL_RUNTIME_DIR / "logs"
DEFAULT_LOG_FILE = DEFAULT_LOG_DIR / "scraper.log"


@dataclass
class BrowserConfig:
    headless: bool = True
    timeout: int = 30000
    viewport: Dict[str, int] = field(default_factory=lambda: {"width": 1920, "height": 1080})
    channel: str = "chrome"
    args: list = field(default_factory=list)
    user_data_dir: Optional[str] = None


@dataclass
class SignatureConfig:
    enabled: bool = False


@dataclass
class LocalConfig:
    cookies_file: str = str(DEFAULT_COOKIE_FILE)
    output_dir: str = "data"


@dataclass
class ZhihuConfig:
    cookies_required: bool = True
    browser: BrowserConfig = field(default_factory=BrowserConfig)
    signature: SignatureConfig = field(default_factory=SignatureConfig)


@dataclass
class RetryConfig:
    max_attempts: int = 3
    base_delay: float = 1.0
    max_delay: float = 30.0
    exponential_base: float = 2.0
    jitter: bool = True


@dataclass
class ScrollConfig:
    timeout: int = 60000
    pause: int = 1000
    viewport_height: int = 800


@dataclass
class HumanizeConfig:
    enabled: bool = True
    min_delay: float = 1.0
    max_delay: float = 3.0
    scroll_delay: float = 0.5
    page_load_delay: float = 2.0

    @classmethod
    def from_dict(cls, raw: Dict[str, Any]) -> "HumanizeConfig":
        return cls(
            enabled=raw.get("enabled", True),
            min_delay=raw.get("min_delay", 1.0),
            max_delay=raw.get("max_delay", 3.0),
            scroll_delay=raw.get("scroll_delay", 0.5),
            page_load_delay=raw.get("page_load_delay", 2.0),
        )


@dataclass
class ImagesConfig:
    concurrency: int = 4
    timeout: float = 30.0
    referer: str = "https://www.zhihu.com/"


@dataclass
class CrawlerConfig:
    retry: RetryConfig = field(default_factory=RetryConfig)
    scroll: ScrollConfig = field(default_factory=ScrollConfig)
    humanize: HumanizeConfig = field(default_factory=HumanizeConfig)
    images: ImagesConfig = field(default_factory=ImagesConfig)
    proxy: Optional[str] = None


@dataclass
class OutputConfig:
    format: str = "markdown"
    images_subdir: str = "images"
    folder_format: str = "[{date}] {title}"
    download_images: Optional[bool] = None


@dataclass
class LoggingConfig:
    level: str = "INFO"
    format: str = "console"
    file: Optional[str] = str(DEFAULT_LOG_FILE)
    log_exceptions: bool = True


@dataclass
class Config:
    local: LocalConfig
    zhihu: ZhihuConfig
    crawler: CrawlerConfig
    output: OutputConfig
    logging: LoggingConfig

    @classmethod
    def from_dict(cls, raw: Dict[str, Any]) -> "Config":
        return build_config_from_dict(raw)


def build_config_from_dict(raw: Dict[str, Any]) -> Config:
    local_raw = raw.get("local", {})
    zhihu_raw = raw.get("zhihu", {})
    cookies_raw = zhihu_raw.get("cookies", {})
    output_raw = raw.get("output", {})
    local = LocalConfig(
        cookies_file=local_raw.get("cookies_file", cookies_raw.get("file", str(DEFAULT_COOKIE_FILE))),
        output_dir=local_raw.get("output_dir", output_raw.get("directory", "data")),
    )
    zhihu = ZhihuConfig(
        cookies_required=cookies_raw.get("required", True),
        browser=BrowserConfig(**zhihu_raw.get("browser", {})),
        signature=SignatureConfig(**zhihu_raw.get("signature", {})),
    )

    crawler_raw = raw.get("crawler", {})
    crawler = CrawlerConfig(
        retry=RetryConfig(**crawler_raw.get("retry", {})),
        scroll=ScrollConfig(**crawler_raw.get("scroll", {})),
        humanize=HumanizeConfig.from_dict(crawler_raw.get("humanize", {})),
        images=ImagesConfig(**crawler_raw.get("images", {})),
        proxy=crawler_raw.get("proxy", None),
    )

    output = OutputConfig(**{k: v for k, v in output_raw.items() if k != "directory"})
    logging_cfg = LoggingConfig(**raw.get("logging", {}))

    return Config(
        local=local,
        zhihu=zhihu,
        crawler=crawler,
        output=output,
        logging=logging_cfg,
    )


def build_default_config() -> Config:
    return Config(
        local=LocalConfig(),
        zhihu=ZhihuConfig(),
        crawler=CrawlerConfig(),
        output=OutputConfig(),
        logging=LoggingConfig(),
    )
