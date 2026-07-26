"""Deterministic filenames that are safe on Windows, macOS, and Linux."""

from __future__ import annotations

import hashlib
import re
import unicodedata
from pathlib import PurePath


_INVALID = re.compile(r'[\x00-\x1f<>:"/\\|?*]+')
_RESERVED = {
    "CON",
    "PRN",
    "AUX",
    "NUL",
    *(f"COM{index}" for index in range(1, 10)),
    *(f"LPT{index}" for index in range(1, 10)),
}


def safe_filename(value: str, *, max_length: int = 120) -> str:
    """Return one readable component accepted by all supported platforms."""

    if max_length < 16:
        raise ValueError("max_length must be at least 16")
    original = unicodedata.normalize("NFC", value)
    normalized = _INVALID.sub("_", original)
    normalized = re.sub(r"\s+", " ", normalized).strip(" .")
    normalized = re.sub(r"_+", "_", normalized)
    if not normalized:
        normalized = "未命名"

    suffix = PurePath(normalized).suffix
    stem = normalized[: -len(suffix)] if suffix else normalized
    if stem.casefold().upper() in _RESERVED:
        normalized = f"_{normalized}"
        suffix = PurePath(normalized).suffix
        stem = normalized[: -len(suffix)] if suffix else normalized

    if len(normalized) <= max_length:
        return normalized

    digest = hashlib.sha256(original.encode("utf-8")).hexdigest()[:8]
    suffix = suffix if len(suffix) <= 12 else ""
    available = max_length - len(suffix) - len(digest) - 1
    truncated_stem = stem[:available].rstrip(" .")
    return f"{truncated_stem}-{digest}{suffix}"
