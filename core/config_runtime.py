"""
config_runtime.py - Runtime config loading and singleton access.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional, Union

import yaml

from .config_schema import (
    Config,
    build_config_from_dict,
    build_default_config,
)
from .logging_setup import setup_logging
from .structlog_compat import structlog, BoundLoggerBase


def get_project_root() -> Path:
    """Get project root path / 获取项目根目录"""
    return Path(__file__).parent.parent


def resolve_project_path(path: Union[str, Path]) -> Path:
    """Resolve relative paths against project root / 将相对路径解析为项目根目录下的绝对路径"""
    path = Path(path)
    if path.is_absolute():
        return path
    return get_project_root() / path


def get_logger(name: str = "zhihu-scraper") -> BoundLoggerBase:
    """Get structured logger. / 获取结构化日志记录器。"""
    return structlog.get_logger(name)


class ConfigLoader:
    """Configuration loader supporting defaults and singleton caching."""

    _instance: Optional["ConfigLoader"] = None
    _config: Optional[Config] = None

    def __new__(cls) -> "ConfigLoader":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if hasattr(self, "_initialized"):
            return
        self._initialized = True

    def load(
        self,
        config_path: Optional[Union[str, Path]] = None,
        *,
        override_level: Optional[str] = None,
    ) -> Config:
        if self._config is not None:
            return self._config

        resolved_path = Path(config_path) if config_path is not None else get_project_root() / "config.yaml"

        if not resolved_path.exists():
            self._log_missing_config(resolved_path)
            self._config = self._finalize_config(build_default_config(), override_level=override_level)
            return self._config

        try:
            with open(resolved_path, "r", encoding="utf-8") as f:
                raw = yaml.safe_load(f) or {}

            raw = _filter_config_dict(raw)

            self._config = self._finalize_config(
                build_config_from_dict(raw),
                override_level=override_level,
            )
            return self._config
        except Exception as e:
            print(f"⚠️ Configuration file load failed: {e}")
            print("  Using default configuration / 使用默认配置")
            self._config = self._finalize_config(build_default_config(), override_level=override_level)
            return self._config

    def get(self) -> Config:
        if self._config is None:
            return self.load()
        return self._config

    def reload(self, config_path: Optional[Union[str, Path]] = None) -> Config:
        self._config = None
        return self.load(config_path)

    def _log_missing_config(self, path: Path) -> None:
        log = structlog.get_logger()
        log.warning("config_file_not_found", path=str(path), using_defaults=True)

    @staticmethod
    def _finalize_config(config: Config, *, override_level: Optional[str] = None) -> Config:
        if override_level:
            config.logging.level = override_level
        setup_logging(config)
        return config


def get_config(config_path: Optional[Union[str, Path]] = None) -> Config:
    """Convenience singleton getter / 便捷配置入口"""
    return ConfigLoader().load(config_path)


def update_config(patch: dict) -> None:
    """Merge *patch* into config.yaml and persist to disk.

    Only the keys present in *patch* are updated; the rest of the file
    is left untouched.  The in-memory singleton is then reloaded so that
    subsequent ``get_config()`` calls reflect the change.

    Example::

        update_config({"global": {"language": "en"}})
    """
    config_path = get_project_root() / "config.yaml"
    raw: dict = {}
    if config_path.exists():
        with open(config_path, "r", encoding="utf-8") as fh:
            raw = yaml.safe_load(fh) or {}

    _deep_merge(raw, patch)
    cleaned = _filter_config_dict(raw)

    with open(config_path, "w", encoding="utf-8") as fh:
        yaml.dump(cleaned, fh, default_flow_style=False, allow_unicode=True, sort_keys=False)

    # Reload singleton so in-memory state stays consistent
    ConfigLoader().reload()


def _deep_merge(base: dict, override: dict) -> None:
    """Recursively merge *override* into *base* in-place."""
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(base.get(key), dict):
            _deep_merge(base[key], value)
        else:
            base[key] = value


def _filter_config_dict(data: dict) -> dict:
    """Filter out keys from data dict that do not conform to Config schema."""
    valid_schema = {
        "zhihu": {
            "cookies": {"file", "required"},
            "browser": {"headless", "timeout", "viewport", "channel", "args", "user_data_dir"},
            "signature": {"enabled"},
        },
        "local": {"cookies_file", "output_dir"},
        "crawler": {
            "retry": {"max_attempts", "base_delay", "max_delay", "exponential_base", "jitter"},
            "scroll": {"timeout", "pause", "viewport_height"},
            "humanize": {"enabled", "min_delay", "max_delay", "scroll_delay", "page_load_delay"},
            "images": {"concurrency", "timeout", "referer"},
            "proxy": None,
        },
        "output": {"directory", "format", "images_subdir", "folder_format", "download_images"},
        "logging": {"level", "format", "file", "log_exceptions"},
    }

    def filter_node(current_data: Any, schema_node: Any) -> Any:
        if schema_node is None:
            return current_data
        if not isinstance(current_data, dict):
            return current_data

        filtered = {}
        for k, v in current_data.items():
            if k in schema_node:
                node_schema = schema_node[k]
                if isinstance(node_schema, dict):
                    filtered[k] = filter_node(v, node_schema)
                elif isinstance(node_schema, set):
                    if isinstance(v, dict):
                        filtered[k] = {sub_k: sub_v for sub_k, sub_v in v.items() if sub_k in node_schema}
                    else:
                        filtered[k] = v
                else:
                    filtered[k] = v
        return filtered

    return filter_node(data, valid_schema)
