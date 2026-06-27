"""
cookie_manager.py - Single Cookie Session Manager

Loads one canonical Zhihu cookie file configured by `local.cookies_file`.

================================================================================
cookie_manager.py — 单 Cookie 会话管理

只加载 `local.cookies_file` 配置指定的一份主 Cookie 文件。
================================================================================
"""

import json
from dataclasses import dataclass
from pathlib import Path
from typing import List, Dict, Optional

from .config_runtime import (
    get_config,
    get_logger,
    resolve_project_path,
)


PLACEHOLDER_COOKIE_VALUES = {
    "YOUR_COOKIE_HERE",
    "YOUR_Z_C0_HERE",
    "YOUR_D_C0_HERE",
}


@dataclass(frozen=True)
class RuntimePathResolution:
    """
    Resolved runtime path diagnostics.
    运行时路径解析结果。
    """

    configured_path: Path
    active_path: Path


def is_placeholder_cookie_value(value: Optional[str]) -> bool:
    """
    Check whether a cookie value is still a template placeholder
    检查 Cookie 值是否仍是模板占位符
    """
    if not value:
        return True

    value = value.strip()
    return value in PLACEHOLDER_COOKIE_VALUES or (value.startswith("YOUR_") and value.endswith("_HERE"))


def load_cookie_dict(path: Path) -> Dict[str, str]:
    """
    Parse a cookie file and return non-placeholder key/value pairs
    解析 Cookie 文件并返回过滤掉占位符后的键值对
    """
    cookies_dict: Dict[str, str] = {}
    if not path.exists():
        return cookies_dict

    with open(path, "r", encoding="utf-8") as f:
        cookies_list = json.load(f)
        if isinstance(cookies_list, list):
            for cookie in cookies_list:
                name = cookie.get("name")
                value = cookie.get("value")
                if name and not is_placeholder_cookie_value(value):
                    cookies_dict[name] = value.strip()
        elif isinstance(cookies_list, dict):
            for name, value in cookies_list.items():
                if name and not is_placeholder_cookie_value(value):
                    cookies_dict[name] = value.strip()

    return cookies_dict


def has_real_cookie_values(path: Path) -> bool:
    """
    Check whether a cookie file contains at least one real Zhihu session key
    检查 Cookie 文件是否至少包含一个真实的知乎会话键值
    """
    session = load_cookie_dict(path)
    return "z_c0" in session or "d_c0" in session


def count_available_cookie_sources(base_cookies_path: Optional[str] = None) -> int:
    """
    Count valid cookie sources.
    统计当前可用 Cookie 来源数量。

    """
    base_path = resolve_cookie_file_path(base_cookies_path)
    return 1 if has_real_cookie_values(base_path) else 0


def has_available_cookie_sources(base_cookies_path: Optional[str] = None) -> bool:
    """
    Check whether at least one valid cookie source is available.
    检查是否至少存在一个有效 Cookie 来源。
    """
    return count_available_cookie_sources(base_cookies_path) > 0


def describe_cookie_file_path(configured_path: Optional[str] = None) -> RuntimePathResolution:
    """
    Resolve the configured cookie file path.
    解析配置中的 Cookie 文件路径。
    """
    cfg = get_config()
    configured = resolve_project_path(configured_path or cfg.local.cookies_file)
    return RuntimePathResolution(configured_path=configured, active_path=configured)


def resolve_cookie_file_path(configured_path: Optional[str] = None) -> Path:
    """
    Resolve the active configured cookie file path.
    解析当前生效的配置 Cookie 文件路径。
    """
    return describe_cookie_file_path(configured_path).active_path


class CookieManager:
    """
    Chinese: 知乎单 Cookie 会话管理器
    English: Zhihu single-cookie session manager
    """

    def __init__(self, base_cookies_path: Optional[str] = None):
        self.log = get_logger()
        self.base_path = resolve_cookie_file_path(base_cookies_path)
        self.sessions: List[Dict[str, str]] = []
        self._current_index = -1

        self.reload_sessions()

    def reload_sessions(self) -> None:
        """
        Reload the canonical cookie file from filesystem.
        从文件系统重新加载主 Cookie 文件。
        """
        self.sessions.clear()

        base_session = self._parse_json_file(self.base_path)
        if base_session and self._is_valid_session(base_session):
            self.sessions.append(base_session)

        self.log.info(
            "cookie_manager_loaded",
            total_sessions=len(self.sessions),
            cookie_file=str(self.base_path),
            cookie_mode="single_file",
        )

        if self.sessions:
            self._current_index = 0

    def _parse_json_file(self, path: Path) -> Dict[str, str]:
        """
        Convert JSON array (Name/Value) to dict, filter out useless placeholders
        将 JSON 数组 (Name/Value) 转换为 dict，过滤无用占位符
        """
        try:
            return load_cookie_dict(path)
        except Exception as e:
            self.log.warning("cookie_parse_failed", file=path.name, error=str(e))
            return {}

    def _is_valid_session(self, session: Dict[str, str]) -> bool:
        """
        Verify if this session has minimum required Zhihu core key-values
        验证此 session 是否拥有最低限度的知乎核心键值
        """
        # z_c0 is Zhihu's required identity token
        # z_c0 是知乎必须的身份令牌基础
        return "z_c0" in session or "d_c0" in session

    def get_current_session(self) -> Optional[Dict[str, str]]:
        """
        Get currently active Cookie Session
        获取当前正在使用的 Cookie Session
        """
        if not self.sessions:
            return None
        return self.sessions[self._current_index]

    def has_sessions(self) -> bool:
        """
        Check whether the primary cookie file is usable.
        检查主 Cookie 文件是否可用。
        """
        return len(self.sessions) > 0


_cookie_manager: Optional[CookieManager] = None


def get_cookie_manager() -> CookieManager:
    """
    Lazily initialize the cookie manager.
    延迟初始化 Cookie 管理器。
    """
    global _cookie_manager
    if _cookie_manager is None:
        _cookie_manager = CookieManager()
    return _cookie_manager


class _LazyCookieManagerProxy:
    """
    Proxy access to the lazily initialized CookieManager.
    代理转发到延迟初始化的 CookieManager。
    """

    def __getattr__(self, item):
        return getattr(get_cookie_manager(), item)


# Global lazy proxy (used in scenarios not involving threaded concurrency isolation)
# 全局延迟代理实例 (通常用在不涉及多线程并发隔离的场景)
cookie_manager = _LazyCookieManagerProxy()
