"""Authenticated Zhihu HTTP access with safe cookie diagnostics."""

from __future__ import annotations

import json
import time
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol, cast
from urllib.parse import urljoin, urlparse

from curl_cffi import requests


@dataclass(frozen=True, slots=True)
class CookieDiagnostic:
    missing: tuple[str, ...]

    @property
    def is_complete(self) -> bool:
        return not self.missing

    @property
    def message(self) -> str:
        if self.is_complete:
            return "Cookie fields z_c0 and d_c0 are available."
        return f"Cookie fields missing: {', '.join(self.missing)}."


@dataclass(frozen=True, slots=True)
class LoginStatus:
    authenticated: bool
    member_id: str | None = None
    name: str | None = None
    reason: str | None = None


class _HttpResponse(Protocol):
    status_code: int
    text: str
    headers: Mapping[str, str]

    def json(self) -> object: ...


class _HttpSession(Protocol):
    def get(self, url: str, **kwargs: Any) -> _HttpResponse: ...


class ZhihuHttpError(RuntimeError):
    """Base class for sanitized, user-facing Zhihu HTTP failures."""

    def __init__(self, status_code: int, message: str) -> None:
        super().__init__(message)
        self.status_code = status_code


class AuthenticationError(ZhihuHttpError):
    """The configured Zhihu login session is missing or expired."""


class AccessDeniedError(ZhihuHttpError):
    """Zhihu refused access for the current session."""


class RateLimitError(ZhihuHttpError):
    """Zhihu rate limiting persisted after the configured retries."""


class ServerError(ZhihuHttpError):
    """Zhihu returned a server-side failure after limited retries."""


class TransportError(RuntimeError):
    """The HTTP transport failed without exposing its potentially sensitive details."""


class InvalidResponseError(RuntimeError):
    """Zhihu returned a response that could not be decoded safely."""


class CookieFileError(ValueError):
    """A Cookie file could not be loaded safely."""


class UnsafeZhihuUrlError(ValueError):
    """A request target was outside the trusted Zhihu origins."""


class ZhihuHttpClient:
    """Small authenticated interface over one reusable curl_cffi session."""

    def __init__(
        self,
        *,
        cookies: Mapping[str, str] | None = None,
        proxy: str | None = None,
        session: _HttpSession | None = None,
        max_retries: int = 2,
        timeout: float = 20.0,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self._cookies = dict(cookies or {})
        self._proxy = proxy
        self._session = session or cast(
            _HttpSession,
            requests.Session(impersonate="chrome"),
        )
        self._max_retries = max_retries
        self._timeout = timeout
        self._sleep = sleep

    def get_json(self, url_or_path: str) -> object:
        response = self._get(url_or_path, accept="application/json, text/plain, */*")
        try:
            return response.json()
        except Exception:
            raise InvalidResponseError(
                "Zhihu returned a response that was not valid JSON."
            ) from None

    def get_html(self, url_or_path: str) -> str:
        response = self._get(
            url_or_path,
            accept="text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        )
        return response.text

    def check_login(self) -> LoginStatus:
        try:
            payload = self.get_json("/api/v4/me")
        except (AuthenticationError, AccessDeniedError):
            return LoginStatus(
                authenticated=False,
                reason="authentication_rejected",
            )
        if not isinstance(payload, Mapping):
            return LoginStatus(authenticated=False, reason="invalid_response")

        raw_member_id = payload.get("id")
        raw_url_token = payload.get("url_token")
        member_id = raw_member_id if isinstance(raw_member_id, str) else None
        url_token = raw_url_token if isinstance(raw_url_token, str) else None
        authenticated = bool(member_id or url_token)
        raw_name = payload.get("name")
        name = raw_name if isinstance(raw_name, str) else None
        return LoginStatus(
            authenticated=authenticated,
            member_id=member_id,
            name=name,
            reason=None if authenticated else "identity_missing",
        )

    def _get(self, url_or_path: str, *, accept: str) -> _HttpResponse:
        url = _absolute_zhihu_url(url_or_path)
        request_options: dict[str, object] = {
            "headers": {
                "Accept": accept,
                "Referer": "https://www.zhihu.com/",
            },
            "cookies": self._cookies,
            "timeout": self._timeout,
        }
        if self._proxy:
            request_options["proxy"] = self._proxy

        for retry_number in range(self._max_retries + 1):
            try:
                response = self._session.get(url, **request_options)
            except Exception:
                if retry_number < self._max_retries:
                    self._sleep(_retry_delay({}, retry_number))
                    continue
                raise TransportError(
                    "Zhihu request failed after limited retries; check the network or proxy."
                ) from None
            should_retry = response.status_code == 429 or 500 <= response.status_code <= 599
            if should_retry and retry_number < self._max_retries:
                self._sleep(_retry_delay(response.headers, retry_number))
                continue
            if response.status_code == 401:
                raise AuthenticationError(
                    401,
                    "Zhihu returned HTTP 401; authentication is missing or expired. "
                    "Check the z_c0 and d_c0 Cookie fields.",
                )
            if response.status_code == 403:
                raise AccessDeniedError(
                    403,
                    "Zhihu returned HTTP 403; access was denied. "
                    "Refresh the z_c0 and d_c0 Cookie fields or use browser fallback.",
                )
            if response.status_code == 429:
                raise RateLimitError(
                    429,
                    "Zhihu returned HTTP 429 after limited retries; "
                    "reduce request frequency and try again later.",
                )
            if 500 <= response.status_code <= 599:
                raise ServerError(
                    response.status_code,
                    f"Zhihu returned HTTP {response.status_code} after limited retries; "
                    "the server is temporarily unavailable.",
                )
            return response

        raise AssertionError("retry loop must return or raise")


def load_cookies(path: Path) -> dict[str, str]:
    """Load non-empty name/value pairs from a browser cookie export."""

    cookie_path = Path(path)
    try:
        payload = json.loads(cookie_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        raise CookieFileError(f"Could not safely load Cookie file {cookie_path.name}.") from None

    cookies: dict[str, str] = {}
    pairs: Iterable[tuple[object, object]]
    if isinstance(payload, dict):
        pairs = payload.items()
    elif isinstance(payload, list):
        pairs = (
            (item.get("name"), item.get("value")) for item in payload if isinstance(item, dict)
        )
    else:
        raise CookieFileError(
            f"Cookie file {cookie_path.name} must contain a name/value list or object."
        )

    for name, value in pairs:
        if not isinstance(name, str) or not isinstance(value, str):
            continue
        normalized_name = name.strip()
        normalized_value = value.strip()
        if not normalized_name or not normalized_value:
            continue
        if normalized_value.startswith("YOUR_") and normalized_value.endswith("_HERE"):
            continue
        cookies[normalized_name] = normalized_value
    return cookies


def diagnose_cookies(cookies: dict[str, str]) -> CookieDiagnostic:
    """Report missing core Cookie names without exposing any values."""

    missing = tuple(name for name in ("z_c0", "d_c0") if not cookies.get(name))
    return CookieDiagnostic(missing=missing)


def _absolute_zhihu_url(url_or_path: str) -> str:
    url = urljoin("https://www.zhihu.com/", url_or_path)
    parsed = urlparse(url)
    hostname = (parsed.hostname or "").casefold()
    trusted_host = hostname == "zhihu.com" or hostname.endswith(".zhihu.com")
    if parsed.scheme != "https" or not trusted_host or parsed.username or parsed.password:
        raise UnsafeZhihuUrlError(
            "Refusing to send authenticated Zhihu request outside trusted HTTPS origins."
        )
    return url


def _retry_delay(headers: Mapping[str, str], retry_number: int) -> float:
    retry_after = headers.get("Retry-After")
    if retry_after is not None:
        try:
            return max(0.0, float(retry_after))
        except (TypeError, ValueError):
            pass
    return min(float(2**retry_number), 8.0)
