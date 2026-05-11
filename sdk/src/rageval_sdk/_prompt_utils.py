"""
Prompt input truncation utilities.

Prevents oversized inputs from exceeding model context windows
or causing excessive token costs.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def truncate_text(text: str, max_chars: int, *, label: str = "text") -> str:
    """Truncate *text* to *max_chars*, appending a marker if cut."""
    if not text or len(text) <= max_chars:
        return text

    suffix = "\n...[truncated]"
    cut = text[: max_chars - len(suffix)] + suffix
    logger.warning(
        "Truncated %s from %d to %d chars (limit: %d)",
        label,
        len(text),
        len(cut),
        max_chars,
    )
    return cut


def truncate_contexts(
    contexts: list[str],
    *,
    max_total_chars: int,
    max_single_chars: int,
) -> list[str]:
    """Truncate a list of context strings within budget."""
    if not contexts:
        return contexts

    result: list[str] = []
    remaining = max_total_chars
    dropped = 0

    for i, ctx in enumerate(contexts):
        if remaining <= 0:
            dropped += 1
            continue

        truncated = truncate_text(
            ctx, min(max_single_chars, remaining), label=f"context[{i}]"
        )
        result.append(truncated)
        remaining -= len(truncated)

    if dropped:
        logger.warning(
            "Dropped %d context(s) — total context budget (%d chars) exhausted",
            dropped,
            max_total_chars,
        )

    return result
