from __future__ import annotations

import json
from typing import Any, Callable


def safe_parse_json_object(
    content: str,
    *,
    transform: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
    fallback: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Best-effort extraction of a JSON object from model output.

    Order:
    1. Raw content
    2. Markdown-fence-stripped content
    3. Outermost JSON object slice
    """
    raw = (content or "").strip()
    candidates: list[str] = [raw]

    if raw.startswith("```"):
        lines = raw.splitlines()
        if len(lines) >= 3 and lines[-1].strip().startswith("```"):
            body = "\n".join(lines[1:-1]).strip()
            if body:
                candidates.insert(0, body)

    start = raw.find("{")
    end = raw.rfind("}")
    if start != -1 and end != -1 and end > start:
        candidates.insert(0, raw[start : end + 1])

    for candidate in candidates:
        try:
            parsed = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            return transform(parsed) if transform else parsed

    return dict(fallback or {})
