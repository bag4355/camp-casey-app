from __future__ import annotations

import re
import unicodedata
from typing import Iterable


_whitespace_re = re.compile(r"\s+")
_non_word_re = re.compile(r"[^a-z0-9가-힣]+")


def compact_whitespace(value: str) -> str:
    return _whitespace_re.sub(" ", value or "").strip()


def normalize_text(value: str | None) -> str:
    if not value:
        return ""
    normalized = unicodedata.normalize("NFKC", value)
    normalized = normalized.lower()
    normalized = normalized.replace("&", " and ")
    normalized = normalized.replace("’", "'").replace("`", "'")
    normalized = compact_whitespace(normalized)
    return normalized


def slugify(value: str) -> str:
    normalized = normalize_text(value)
    normalized = _non_word_re.sub("-", normalized)
    normalized = normalized.strip("-")
    return normalized or "item"


def tokenize_for_search(value: str | None) -> list[str]:
    normalized = normalize_text(value)
    tokens = [token for token in _non_word_re.split(normalized) if token]
    return tokens


def dedupe_keep_order(values: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if not value:
            continue
        key = normalize_text(value)
        if key in seen:
            continue
        seen.add(key)
        result.append(value)
    return result
