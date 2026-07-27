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


def safe_filename(
    value: str,
    *,
    max_length: int = 80,
    max_bytes: int = 240,
) -> str:
    """Return one readable component accepted by all supported platforms."""

    if max_length < 16:
        raise ValueError("max_length must be at least 16")
    if max_bytes < 32:
        raise ValueError("max_bytes must be at least 32")
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

    if len(normalized) <= max_length and len(normalized.encode("utf-8")) <= max_bytes:
        return normalized

    digest = hashlib.sha256(original.encode("utf-8")).hexdigest()[:8]
    suffix = suffix if len(suffix) <= 12 and len(suffix.encode("utf-8")) <= 32 else ""
    fixed = f"-{digest}{suffix}"
    available_characters = max_length - len(fixed)
    available_bytes = max_bytes - len(fixed.encode("utf-8"))
    truncated_stem = _truncate_component(
        stem,
        max_characters=available_characters,
        max_bytes=available_bytes,
    ).rstrip(" .")
    if not truncated_stem:
        truncated_stem = "file"
    return f"{truncated_stem}-{digest}{suffix}"


def _truncate_component(
    value: str,
    *,
    max_characters: int,
    max_bytes: int,
) -> str:
    characters: list[str] = []
    byte_count = 0
    for character in value:
        encoded_size = len(character.encode("utf-8"))
        if len(characters) >= max_characters or byte_count + encoded_size > max_bytes:
            break
        characters.append(character)
        byte_count += encoded_size
    return "".join(characters)
