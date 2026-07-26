"""Download and select media assets without third-party dependencies."""

from __future__ import annotations

import os
import re
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import ContextManager, Protocol
from urllib.request import Request, urlopen


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


class _HttpResponse(Protocol):
    status: int
    headers: Mapping[str, str]

    def __enter__(self) -> _HttpResponse: ...

    def __exit__(self, exc_type: object, exc_value: object, traceback: object) -> object: ...

    def read(self, size: int = -1) -> bytes: ...


HttpTransport = Callable[[Request], ContextManager[_HttpResponse]]


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
    chunk_size: int = 1024 * 1024,
) -> MediaDownloadReceipt:
    """Download one media URL, resuming a sibling ``.part`` file when possible."""

    if chunk_size <= 0:
        raise ValueError("chunk_size must be positive")

    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.is_file():
        return MediaDownloadReceipt(
            source_url=source_url,
            destination=destination,
            resumed_from=0,
            bytes_total=destination.stat().st_size,
        )

    partial_path = destination.with_name(f"{destination.name}.part")
    partial_size = partial_path.stat().st_size if partial_path.is_file() else 0
    headers = {
        "Referer": "https://www.zhihu.com/",
        "User-Agent": "zhihu-scraper/3",
    }
    if partial_size:
        headers["Range"] = f"bytes={partial_size}-"

    request = Request(source_url, headers=headers, method="GET")
    open_request = transport or urlopen

    with open_request(request) as response:
        status = _response_status(response)
        resumed_from, expected_total = _response_plan(
            status=status,
            headers=response.headers,
            partial_size=partial_size,
        )
        mode = "ab" if resumed_from else "wb"
        with partial_path.open(mode) as output:
            while chunk := response.read(chunk_size):
                output.write(chunk)
            output.flush()
            os.fsync(output.fileno())

    bytes_total = partial_path.stat().st_size
    if expected_total is not None and bytes_total != expected_total:
        raise MediaDownloadError(
            f"incomplete download: expected {expected_total} bytes, received {bytes_total}"
        )

    os.replace(partial_path, destination)
    return MediaDownloadReceipt(
        source_url=source_url,
        destination=destination,
        resumed_from=resumed_from,
        bytes_total=bytes_total,
    )


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
