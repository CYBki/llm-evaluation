"""
Prompt input truncation utilities.

Prevents oversized inputs from exceeding model context windows
or causing excessive token costs. Truncation is applied transparently
before prompt construction — the LLM sees a [truncated] marker so it
knows data was cut.

Limits are configured via Settings (app/config.py) and can be
overridden with environment variables.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def truncate_text(text: str, max_chars: int, *, label: str = "text") -> str:
    """Truncate *text* to *max_chars*, appending a marker if cut.

    Args:
        text: The input string.
        max_chars: Maximum allowed character length.
        label: Human-readable name for log messages (e.g. "answer", "question").

    Returns:
        Original text if within limit, otherwise truncated with suffix.
    """
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
    """Truncate a list of context strings within budget.

    Each individual context is capped at *max_single_chars*.
    The cumulative total is capped at *max_total_chars* — once the
    budget is exhausted, remaining contexts are dropped entirely.

    Returns:
        A new list (never mutates the input).
    """
    if not contexts:
        return contexts

    result: list[str] = []
    remaining = max_total_chars
    dropped = 0

    for i, ctx in enumerate(contexts):
        if remaining <= 0:
            dropped += 1
            continue

        truncated = truncate_text(ctx, min(max_single_chars, remaining), label=f"context[{i}]")
        result.append(truncated)
        remaining -= len(truncated)

    if dropped:
        logger.warning(
            "Dropped %d context(s) — total context budget (%d chars) exhausted",
            dropped,
            max_total_chars,
        )

    return result
