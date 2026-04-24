#!/usr/bin/env python3
"""
Compare two evaluation stacks (e.g. Qwen via OpenRouter vs OpenAI) by sending
the same traces to both and printing a side-by-side report.

Usage:
    python scripts/compare_models.py \
        --traces traces.json \
        --qwen-url http://localhost:8000 --qwen-key <API_KEY> \
        --openai-url http://localhost:8001 --openai-key <API_KEY>

`traces.json` format: a JSON array of trace payloads, each matching the
`POST /api/v1/ingest` schema. Example:

    [
      {
        "question": "...",
        "answer": "...",
        "contexts": ["..."],
        "ground_truth": "...",
        "metadata": {"tag": "gil"}
      },
      ...
    ]

The script ingests each trace into both stacks in parallel, polls until both
evaluations complete, and prints a comparison table plus summary stats
(mean absolute diff per metric, Pearson correlation).
"""
from __future__ import annotations

import argparse
import asyncio
import json
import math
import statistics
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx


NUMERIC_METRICS = [
    "overall_score",
    "clarity",
    "coherence",
    "helpfulness",
    "completeness",
    "answer_relevancy",
    "faithfulness",
    "hallucination_score",
    "citation_check",
    "context_precision",
    "context_recall",
]


@dataclass
class Stack:
    name: str
    base_url: str
    api_key: str


@dataclass
class TraceResult:
    trace_id: str | None
    status: str
    scores: dict[str, float | None]
    duration_ms: int | None
    cost_usd: float | None
    total_tokens: int | None
    reasoning_summary: str | None
    raw: dict[str, Any]


async def submit_and_wait(
    client: httpx.AsyncClient,
    stack: Stack,
    payload: dict[str, Any],
    sem: asyncio.Semaphore,
    poll_interval: float = 2.0,
    timeout: float = 180.0,
) -> TraceResult:
    """Submit one trace and poll until evaluation completes (or timeout).

    ``sem`` throttles ingest concurrency per stack so we stay under the
    30/minute ingest rate limit; polling is unbounded (read-only).
    """
    headers = {"X-API-Key": stack.api_key}

    async with sem:
        try:
            resp = await client.post(
                f"{stack.base_url}/api/v1/ingest",
                headers=headers,
                json=payload,
                timeout=30.0,
            )
            resp.raise_for_status()
        except httpx.HTTPError as exc:
            return TraceResult(
                trace_id=None,
                status="ingest_failed",
                scores={},
                duration_ms=None,
                cost_usd=None,
                total_tokens=None,
                reasoning_summary=f"ingest error on {stack.name}: {exc}",
                raw={},
            )
        # Small gap inside the critical section so we never exceed 30/min
        await asyncio.sleep(0.3)

    data = resp.json()
    trace_id = data.get("id")
    if not trace_id:
        return TraceResult(
            trace_id=None,
            status="ingest_failed",
            scores={},
            duration_ms=None,
            cost_usd=None,
            total_tokens=None,
            reasoning_summary=f"no trace id in ingest response: {data}",
            raw=data,
        )

    deadline = time.monotonic() + timeout
    last_raw: dict[str, Any] = {}
    while time.monotonic() < deadline:
        try:
            detail_resp = await client.get(
                f"{stack.base_url}/api/v1/traces/{trace_id}",
                headers=headers,
                timeout=30.0,
            )
            detail_resp.raise_for_status()
            last_raw = detail_resp.json()
        except httpx.HTTPError as exc:
            await asyncio.sleep(poll_interval)
            continue

        status = last_raw.get("status") or (last_raw.get("evaluation") or {}).get(
            "status"
        )
        if status in ("completed", "failed"):
            break
        await asyncio.sleep(poll_interval)

    evaluation = last_raw.get("evaluation") or {}
    scores = evaluation.get("scores") or {}
    overall = evaluation.get("overall_score")
    if overall is not None:
        scores = {**scores, "overall_score": overall}
    return TraceResult(
        trace_id=trace_id,
        status=last_raw.get("status", "unknown"),
        scores={k: scores.get(k) for k in NUMERIC_METRICS},
        duration_ms=evaluation.get("evaluation_duration_ms"),
        cost_usd=evaluation.get("cost_usd"),
        total_tokens=evaluation.get("total_tokens"),
        reasoning_summary=evaluation.get("reasoning_summary"),
        raw=last_raw,
    )


def _fmt(v: Any) -> str:
    if v is None:
        return "  —  "
    if isinstance(v, float):
        return f"{v:.3f}"
    return str(v)


def print_per_trace_table(
    payloads: list[dict[str, Any]],
    qwen: list[TraceResult],
    openai: list[TraceResult],
) -> None:
    print("\n" + "=" * 100)
    print("Per-trace comparison")
    print("=" * 100)
    header = f"{'metric':<22} " + " | ".join(f"#{i+1:<8} Q  vs  O" for i in range(len(payloads)))
    print(header)
    print("-" * len(header))
    for metric in NUMERIC_METRICS:
        row = f"{metric:<22} "
        cells = []
        for q, o in zip(qwen, openai):
            cells.append(f"{_fmt(q.scores.get(metric)):>6}  {_fmt(o.scores.get(metric)):>6}")
        row += " | ".join(cells)
        print(row)

    print("\n" + "-" * 100)
    print(f"{'duration_ms':<22} " + " | ".join(
        f"{_fmt(q.duration_ms):>6}  {_fmt(o.duration_ms):>6}"
        for q, o in zip(qwen, openai)
    ))
    print(f"{'cost_usd':<22} " + " | ".join(
        f"{_fmt(q.cost_usd):>6}  {_fmt(o.cost_usd):>6}"
        for q, o in zip(qwen, openai)
    ))
    print(f"{'total_tokens':<22} " + " | ".join(
        f"{_fmt(q.total_tokens):>6}  {_fmt(o.total_tokens):>6}"
        for q, o in zip(qwen, openai)
    ))
    print(f"{'status':<22} " + " | ".join(
        f"{q.status:>6}  {o.status:>6}"
        for q, o in zip(qwen, openai)
    ))


def _pearson(xs: list[float], ys: list[float]) -> float | None:
    if len(xs) < 2:
        return None
    mx = statistics.fmean(xs)
    my = statistics.fmean(ys)
    num = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    dx = math.sqrt(sum((x - mx) ** 2 for x in xs))
    dy = math.sqrt(sum((y - my) ** 2 for y in ys))
    if dx == 0 or dy == 0:
        return None
    return num / (dx * dy)


def print_summary(qwen: list[TraceResult], openai: list[TraceResult]) -> None:
    print("\n" + "=" * 100)
    print("Aggregate stats per metric")
    print("=" * 100)
    print(f"{'metric':<22} {'n':>4} {'Qwen_mean':>11} {'OAI_mean':>11} {'mean_diff':>11} {'MAD':>8} {'pearson':>8}")
    print("-" * 100)

    for metric in NUMERIC_METRICS:
        pairs = [
            (q.scores.get(metric), o.scores.get(metric))
            for q, o in zip(qwen, openai)
            if isinstance(q.scores.get(metric), (int, float))
            and isinstance(o.scores.get(metric), (int, float))
        ]
        if not pairs:
            print(f"{metric:<22} {0:>4}     —           —           —         —       —")
            continue
        qs = [float(p[0]) for p in pairs]
        os_ = [float(p[1]) for p in pairs]
        q_mean = statistics.fmean(qs)
        o_mean = statistics.fmean(os_)
        mean_diff = statistics.fmean([q - o for q, o in zip(qs, os_)])
        mad = statistics.fmean([abs(q - o) for q, o in zip(qs, os_)])
        r = _pearson(qs, os_)
        r_str = f"{r:>.3f}" if r is not None else "  —  "
        print(
            f"{metric:<22} {len(pairs):>4} "
            f"{q_mean:>11.3f} {o_mean:>11.3f} "
            f"{mean_diff:>+11.3f} {mad:>8.3f} {r_str:>8}"
        )

    # Cost / speed totals
    def _sum_field(results: list[TraceResult], field: str) -> float:
        vals = [getattr(r, field) for r in results if getattr(r, field) is not None]
        return float(sum(vals))

    print("\n" + "-" * 100)
    print("Totals")
    print(f"  Qwen   total cost  = ${_sum_field(qwen, 'cost_usd'):.4f}")
    print(f"  OpenAI total cost  = ${_sum_field(openai, 'cost_usd'):.4f}")
    print(f"  Qwen   total tokens= {int(_sum_field(qwen, 'total_tokens')):,}")
    print(f"  OpenAI total tokens= {int(_sum_field(openai, 'total_tokens')):,}")
    q_dur = [r.duration_ms for r in qwen if r.duration_ms is not None]
    o_dur = [r.duration_ms for r in openai if r.duration_ms is not None]
    if q_dur:
        print(f"  Qwen   mean dur    = {statistics.fmean(q_dur):.0f} ms")
    if o_dur:
        print(f"  OpenAI mean dur    = {statistics.fmean(o_dur):.0f} ms")


async def run(
    qwen: Stack,
    openai: Stack,
    payloads: list[dict[str, Any]],
    out_path: Path | None,
    concurrency: int,
) -> None:
    # Per-stack ingest semaphore — each limits concurrent POSTs to /ingest so
    # we stay under the 30/minute rate limit. 4 concurrent × ~0.3s gap is
    # comfortably under the limit while keeping wall-clock low.
    qwen_sem = asyncio.Semaphore(concurrency)
    openai_sem = asyncio.Semaphore(concurrency)

    async with httpx.AsyncClient() as client:
        print(
            f"Submitting {len(payloads)} trace(s) to both stacks "
            f"(concurrency={concurrency} per stack)..."
        )
        tasks = []
        for p in payloads:
            tasks.append(submit_and_wait(client, qwen, p, qwen_sem))
            tasks.append(submit_and_wait(client, openai, p, openai_sem))
        results = await asyncio.gather(*tasks)

    qwen_results = results[0::2]
    openai_results = results[1::2]

    for i, (q, o) in enumerate(zip(qwen_results, openai_results), 1):
        print(f"[{i}] qwen: {q.status} ({q.trace_id}) | openai: {o.status} ({o.trace_id})")
        if q.status != "completed":
            print(f"    qwen reason: {q.reasoning_summary}")
        if o.status != "completed":
            print(f"    openai reason: {o.reasoning_summary}")

    print_per_trace_table(payloads, qwen_results, openai_results)
    print_summary(qwen_results, openai_results)

    if out_path:
        dump = {
            "qwen": [r.raw for r in qwen_results],
            "openai": [r.raw for r in openai_results],
        }
        out_path.write_text(json.dumps(dump, indent=2, ensure_ascii=False))
        print(f"\nRaw results written to {out_path}")


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--traces", required=True, type=Path, help="JSON file with a list of trace payloads")
    ap.add_argument("--qwen-url", default="http://localhost:8000")
    ap.add_argument("--qwen-key", required=True, help="X-API-Key for the Qwen stack")
    ap.add_argument("--openai-url", default="http://localhost:8001")
    ap.add_argument("--openai-key", required=True, help="X-API-Key for the OpenAI stack")
    ap.add_argument("--out", type=Path, default=None, help="Optional: dump raw results to this path")
    ap.add_argument(
        "--concurrency",
        type=int,
        default=4,
        help="Max concurrent ingests per stack (default 4; keeps us below the 30/min rate limit)",
    )
    return ap.parse_args()


def main() -> int:
    args = parse_args()
    if not args.traces.exists():
        print(f"ERROR: traces file not found: {args.traces}", file=sys.stderr)
        return 2

    payloads = json.loads(args.traces.read_text())
    if isinstance(payloads, dict):
        payloads = [payloads]
    if not isinstance(payloads, list) or not payloads:
        print("ERROR: traces file must be a non-empty JSON list", file=sys.stderr)
        return 2

    qwen = Stack(name="qwen", base_url=args.qwen_url.rstrip("/"), api_key=args.qwen_key)
    openai = Stack(name="openai", base_url=args.openai_url.rstrip("/"), api_key=args.openai_key)

    asyncio.run(run(qwen, openai, payloads, args.out, args.concurrency))
    return 0


if __name__ == "__main__":
    sys.exit(main())
    sys.exit(main())
