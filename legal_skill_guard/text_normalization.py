"""Shared deterministic normalization for natural-language surface forms."""

from __future__ import annotations

import re


def normalize_question(value: str) -> str:
    """Canonicalize a question for exact-repeat checks across execution stages."""

    return re.sub(r"[\W_]+", "", value).lower()
