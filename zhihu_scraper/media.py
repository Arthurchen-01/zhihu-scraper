"""Download and select media assets without third-party dependencies."""

from __future__ import annotations

import os
import re
import time
from collections.abc import Callable, Iterable, Mapping
from contextlib import AbstractContextManager
from dataclasses import dataclass
from http.client import IncompleteRead
from ipaddress import ip_address
from pathlib import Path
from socket import SOCK_STREAM, getaddrinfo
from typing import Any, Protocol, cast
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlsplit
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener


@dataclass(frozen=True, slots=True)
class MediaCandidate:
    """One downloadable rendition of the same media asset."""

    source_url: str
    width: int
    height: int


@dataclass(frozen=True, slots=True)
class MediaDownloadReceipt:
    """Observable result of a completed media download."""

    source_url: str
    destination: Path
    resumed_from: int
    bytes_total: int


class MediaDownloadError(RuntimeError):
    """Raised when a response cannot safely produce a complete media file."""


class _RetryableMediaError(MediaDownloadError):
    """Internal signal for a bounded retry."""


class _SafeMediaRedirectHandler(HTTPRedirectHandler):
    """Validate every redirect target immediately before urllib follows it."""

    def redirect_request(
        self,
        request: Request,
        file_pointer: Any,
        code: int,
        message: str,
        headers: Any,
        new_url: str,
    ) -> Request | None:
        redirect_url = urljoin(request.full_url, new_url)
        _validate_media_url(redirect_url)
        _resolve_media_host(redirect_url)
        return cast(
            Request | None,
            super().redirect_request(
                request,
                file_pointer,
                code,
                message,
                headers,
                redirect_url,
            ),
        )


class _HttpResponse(Protocol):
    status: int
    headers: Mapping[str, str]

    def __enter__(self) -> _HttpResponse: ...

    def __exit__(self, exc_type: object, exc_value: object, traceback: object) -> object: ...

    def read(self, size: int = -1) -> bytes: ...


HttpTransport = Callable[[Request], AbstractContextManager[_HttpResponse]]


def select_highest_resolution(candidates: Iterable[MediaCandidate]) -> MediaCandidate:
    """Return the largest rendition, keeping input order for exact ties."""

    available = tuple(candidates)
    if not available:
        raise ValueError("at least one media candidate is required")
    return max(available, key=lambda candidate: candidate.width * candidate.height)


def download_media(
    source_url: str,
    destination: Path,
    *,
    transport: HttpTransport | None = None,
    proxy: str | None = None,
    timeout: float = 30.0,
    max_retries: int = 2,
    sleep: Callable[[float], None] = time.sleep,
    chunk_size: int = 1024 * 1024,
) -> MediaDownloadReceipt:
    """Download one media URL, resuming a sibling ``.part`` file when possible."""

    if chunk_size <= 0:
        raise ValueError("chunk_size must be positive")
    if timeout <= 0:
        raise ValueError("timeout must be positive")
    if (
        not isinstance(max_retries, int)
        or isinstance(max_retries, bool)
        or not 0 <= max_retries <= 10
    ):
        raise ValueError("max_retries must be an integer from 0 to 10")
    _validate_media_url(source_url)

    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.is_file() and destination.stat().st_size > 0:
        return MediaDownloadReceipt(
            source_url=source_url,
            destination=destination,
            resumed_from=0,
            bytes_total=destination.stat().st_size,
        )

    partial_path = destination.with_name(f"{destination.name}.part")
    opener = None
    if transport is None:
        handlers: list[Any] = []
        if proxy is not None:
            handlers.append(ProxyHandler({"http": proxy, "https": proxy}))
        handlers.append(_SafeMediaRedirectHandler())
        opener = build_opener(*handlers)

    for retry_number in range(max_retries + 1):
        partial_size = partial_path.stat().st_size if partial_path.is_file() else 0
        headers = {
            "Referer": "https://www.zhihu.com/",
            "User-Agent": "zhihu-scraper/4",
        }
        if partial_size:
            headers["Range"] = f"bytes={partial_size}-"
        request = Request(source_url, headers=headers, method="GET")

        try:
            # Keep the DNS check adjacent to the actual open. urllib does not
            # expose a supported way to pin an HTTPS connection to this result,
            # so every retry and every redirect is resolved and checked again.
            _resolve_media_host(source_url)
            with _open_response(
                request,
                transport=transport,
                opener=opener,
                timeout=timeout,
            ) as response:
                status = _response_status(response)
                redirect_location = _header(response.headers, "Location")
                if 300 <= status <= 399 and redirect_location is not None:
                    redirect_url = urljoin(source_url, redirect_location)
                    _validate_media_url(redirect_url)
                    _resolve_media_host(redirect_url)
                    raise MediaDownloadError(
                        "the media transport returned an unhandled HTTP redirect"
                    )
                if status == 429 or 500 <= status <= 599:
                    raise _RetryableMediaError(f"temporary HTTP {status}")
                resumed_from, expected_total = _response_plan(
                    status=status,
                    headers=response.headers,
                    partial_size=partial_size,
                )
                mode = "ab" if resumed_from else "wb"
                with partial_path.open(mode) as output:
                    while True:
                        try:
                            chunk = response.read(chunk_size)
                        except IncompleteRead as error:
                            if error.partial:
                                output.write(error.partial)
                            raise _RetryableMediaError("media response interrupted") from None
                        except OSError:
                            raise _RetryableMediaError("media response interrupted") from None
                        if not chunk:
                            break
                        output.write(chunk)
                    output.flush()
                    os.fsync(output.fileno())

            bytes_total = partial_path.stat().st_size
            if expected_total is not None and bytes_total != expected_total:
                raise _RetryableMediaError("the response ended before the advertised length")

            os.replace(partial_path, destination)
            return MediaDownloadReceipt(
                source_url=source_url,
                destination=destination,
                resumed_from=resumed_from,
                bytes_total=bytes_total,
            )
        except HTTPError as error:
            if error.code != 429 and not 500 <= error.code <= 599:
                raise MediaDownloadError(f"unexpected HTTP status {error.code}") from None
            retry_error: BaseException = error
        except _RetryableMediaError as error:
            retry_error = error
        except (ConnectionError, TimeoutError, URLError) as error:
            retry_error = error

        if retry_number < max_retries:
            sleep(min(float(2**retry_number), 8.0))
            continue
        if isinstance(retry_error, _RetryableMediaError):
            raise MediaDownloadError(str(retry_error)) from None
        raise MediaDownloadError("media request failed after limited retries") from None

    raise AssertionError("media retry loop must return or raise")


def _open_response(
    request: Request,
    *,
    transport: HttpTransport | None,
    opener: Any | None,
    timeout: float,
) -> AbstractContextManager[_HttpResponse]:
    if transport is not None:
        return transport(request)
    if opener is not None:
        return cast(
            AbstractContextManager[_HttpResponse],
            opener.open(request, timeout=timeout),
        )
    raise AssertionError("a default urllib opener must be configured")


def _response_status(response: _HttpResponse) -> int:
    status = getattr(response, "status", None)
    if status is None:
        getcode = getattr(response, "getcode", None)
        status = getcode() if getcode is not None else None
    if status is None:
        raise MediaDownloadError("HTTP response did not expose a status code")
    return int(status)


def _response_plan(
    *,
    status: int,
    headers: Mapping[str, str],
    partial_size: int,
) -> tuple[int, int | None]:
    if status == 200:
        content_length = _header(headers, "Content-Length")
        return 0, int(content_length) if content_length is not None else None

    if status != 206:
        raise MediaDownloadError(f"unexpected HTTP status {status}")

    content_range = _header(headers, "Content-Range")
    match = re.fullmatch(r"bytes (\d+)-(\d+)/(\d+|\*)", content_range or "")
    if match is None:
        raise MediaDownloadError("partial response did not include a valid Content-Range")

    start, _end, total = match.groups()
    start_offset = int(start)
    if start_offset != partial_size:
        raise MediaDownloadError(
            f"partial response started at byte {start_offset}, expected {partial_size}"
        )
    return partial_size, None if total == "*" else int(total)


def _header(headers: Mapping[str, str], name: str) -> str | None:
    direct = headers.get(name)
    if direct is not None:
        return direct
    lowered_name = name.casefold()
    return next(
        (value for key, value in headers.items() if key.casefold() == lowered_name),
        None,
    )


def _validate_media_url(source_url: str) -> None:
    if any(character.isspace() or ord(character) < 32 for character in source_url):
        raise MediaDownloadError("media source must be a trusted HTTP or HTTPS URL")
    try:
        parsed = urlsplit(source_url)
        hostname = (parsed.hostname or "").casefold().rstrip(".")
        parsed.port
    except ValueError:
        raise MediaDownloadError("media source must be a trusted HTTP or HTTPS URL") from None
    if (
        parsed.scheme not in {"http", "https"}
        or not hostname
        or parsed.username is not None
        or parsed.password is not None
        or parsed.fragment
        or hostname == "localhost"
        or hostname.endswith(".localhost")
    ):
        raise MediaDownloadError("media source must be a trusted HTTP or HTTPS URL")
    try:
        address = ip_address(hostname)
    except ValueError:
        return
    if not address.is_global:
        raise MediaDownloadError("media source must be a trusted HTTP or HTTPS URL")


def _resolve_media_host(source_url: str) -> None:
    """Reject a hostname unless every address currently resolved for it is global."""

    parsed = urlsplit(source_url)
    hostname = (parsed.hostname or "").casefold().rstrip(".")
    if _is_official_media_host(parsed.scheme, hostname):
        return
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    try:
        resolved = getaddrinfo(hostname, port, type=SOCK_STREAM)
    except OSError:
        raise _RetryableMediaError("media host resolution failed") from None
    if not resolved:
        raise _RetryableMediaError("media host resolution returned no addresses")

    for _family, _socket_type, _protocol, _canonical_name, socket_address in resolved:
        try:
            address = ip_address(str(socket_address[0]).split("%", maxsplit=1)[0])
        except (IndexError, TypeError, ValueError):
            raise MediaDownloadError("media source must be a trusted HTTP or HTTPS URL") from None
        if not address.is_global:
            raise MediaDownloadError("media source must be a trusted HTTP or HTTPS URL")


def _is_official_media_host(scheme: str, hostname: str) -> bool:
    """Trust Zhihu's HTTPS CDNs even behind proxy fake-IP DNS."""

    if scheme != "https":
        return False
    return any(
        hostname == domain or hostname.endswith(f".{domain}")
        for domain in ("zhimg.com", "vzuu.com")
    )
