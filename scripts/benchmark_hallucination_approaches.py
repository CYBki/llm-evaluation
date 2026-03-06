#!/usr/bin/env python3
"""
Hallucination Detection: Single-Call vs Two-Stage Benchmark

Compares two approaches on the same test cases:
  A) Single-Call  — one LLM call with structured output (JSON schema)
  B) Two-Stage    — Stage 1: free-text reasoning, Stage 2: JSON conversion

Measures:
  - Tutarlılık (consistency): same input N kez → skorlar ne kadar değişiyor
  - Süre (latency): ortalama çağrı süresi
  - Claim sayısı: kaç atomic claim çıkarılıyor
  - Skor dağılımı: hallucination_score, faithfulness

Usage:
  python scripts/benchmark_hallucination_approaches.py
  python scripts/benchmark_hallucination_approaches.py --repeats 5
  python scripts/benchmark_hallucination_approaches.py --cases 1,3,5
"""
from __future__ import annotations

import argparse
import asyncio
import json
import math
import os
import statistics
import sys
import time
from dataclasses import dataclass, field
from typing import Any

import httpx
from dotenv import load_dotenv

# Load .env file from project root
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

# ── Config ──────────────────────────────────────────────────────────────

API_KEY = os.environ.get("OPENAI_API_KEY", "")
BASE_URL = os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/")
MODEL = os.environ.get("RAG_METRICS_MODEL", "gpt-4o-mini")
TIMEOUT = 120.0

# ── Penalty constants (same as production) ──────────────────────────────

_HALLUCINATION_UNSUPPORTED_PENALTY = 0.15
_HALLUCINATION_CONTRADICTION_PENALTY = 0.30
_FAITHFULNESS_PER_CLAIM_PENALTY = 0.20


# ── Scoring (identical to production score_hallucination_claims) ────────

def score_hallucination_claims(claims: list[dict]) -> dict[str, float | None]:
    if not claims:
        return {"hallucination_score": None, "faithfulness": None}
    total_penalty = 0.0
    unfaithful_count = 0
    for item in claims:
        if not isinstance(item, dict):
            continue
        dt = str(item.get("disagreement_type", "")).lower()
        if dt == "unsupported claim":
            total_penalty += _HALLUCINATION_UNSUPPORTED_PENALTY
            unfaithful_count += 1
        elif dt == "confirmed contradiction":
            total_penalty += _HALLUCINATION_CONTRADICTION_PENALTY
            unfaithful_count += 1
    h = round(max(0.0, 1.0 - total_penalty), 4)
    f = round(max(0.0, 1.0 - unfaithful_count * _FAITHFULNESS_PER_CLAIM_PENALTY), 4)
    return {
        "hallucination_score": max(0.0, min(1.0, h)),
        "faithfulness": max(0.0, min(1.0, f)),
    }


# ── JSON Schema (shared) ───────────────────────────────────────────────

HALLUCINATION_JSON_SCHEMA = {
    "name": "hallucination_rubric_result",
    "strict": True,
    "schema": {
        "type": "object",
        "properties": {
            "disagreement_claims": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "context_quote": {"type": "string"},
                        "context_quote_type": {
                            "type": "string",
                            "enum": ["instruction", "factual claim"],
                        },
                        "answer_quote": {"type": "string"},
                        "reasoning": {"type": "string"},
                        "disagreement_type": {
                            "type": "string",
                            "enum": ["agreement", "unsupported claim", "confirmed contradiction"],
                        },
                    },
                    "required": [
                        "context_quote", "context_quote_type", "answer_quote",
                        "reasoning", "disagreement_type",
                    ],
                    "additionalProperties": False,
                },
            }
        },
        "required": ["disagreement_claims"],
        "additionalProperties": False,
    },
}

# ── Prompts ─────────────────────────────────────────────────────────────

_SHARED_SYSTEM_BASE = """You are a hallucination detection evaluator.

Task:
1. Extract atomic factual claims from the ANSWER.
2. For each claim, compare against CONTEXT PASSAGES.
3. Label each claim with one disagreement_type:
   - "agreement"                -> context supports the claim.
   - "unsupported claim"        -> context does not provide evidence either way.
   - "confirmed contradiction"  -> context explicitly conflicts with the claim.

Borderline / paraphrase guidance:
- If the answer paraphrases, summarises, or reasonably infers a fact FROM the context,
  label it "agreement". Exact wording is NOT required.
- Reserve "unsupported claim" for statements the context truly says NOTHING about.
- Reserve "confirmed contradiction" ONLY when the context explicitly states the opposite.

Rules:
- Use short direct quotes from both answer and context when possible.
- If no matching context evidence exists, set context_quote to "" and context_quote_type to "factual claim".
- context_quote_type must be either "instruction" or "factual claim".
- Keep reasoning concise (1-2 sentences per claim)."""

# Single-call: one prompt, JSON output required
SINGLE_CALL_SYSTEM = _SHARED_SYSTEM_BASE + "\n- Output ONLY JSON matching the required schema."

# Two-stage Stage 1: free-text reasoning only
TWO_STAGE_S1_SYSTEM = _SHARED_SYSTEM_BASE + "\n- Output plain text reasoning only; do not output JSON."

# Two-stage Stage 2: convert reasoning → JSON
TWO_STAGE_S2_SYSTEM = """You convert evaluator reasoning into strict JSON.
Return ONLY a single JSON object with one key: disagreement_claims.
Use this structure for each item:
- context_quote: string
- context_quote_type: "instruction" | "factual claim"
- answer_quote: string
- reasoning: string
- disagreement_type: "agreement" | "unsupported claim" | "confirmed contradiction"

If no claims are found, return {"disagreement_claims": []}."""


def build_user_prompt(answer: str, contexts: list[str]) -> str:
    ctx_block = "\n".join(f"[{i}] {c}" for i, c in enumerate(contexts)) if contexts else "(empty)"
    return (
        f"ANSWER:\n{answer}\n\n"
        f"CONTEXT PASSAGES:\n{ctx_block}\n\n"
        "Extract atomic factual claims. For each claim, provide context_quote, "
        "answer_quote, reasoning, and disagreement_type as JSON."
    )


def build_stage_2_user_prompt(reasoning: str) -> str:
    return (
        "Convert the following hallucination-evaluation reasoning into strict JSON.\n"
        "Output ONLY JSON.\n\n"
        f"REASONING:\n{reasoning}"
    )


# ── Test Scenarios ──────────────────────────────────────────────────────

TEST_CASES: list[dict[str, Any]] = [
    {
        "name": "1. Tamamen desteklenen cevap (all agreement)",
        "answer": "Redis, açık kaynaklı bir in-memory veri yapısı deposudur. "
                  "Genellikle veritabanı, cache ve mesaj broker olarak kullanılır.",
        "contexts": [
            "Redis, açık kaynaklı (BSD lisanslı), bir in-memory veri yapısı deposudur. "
            "Veritabanı, cache, mesaj broker ve streaming motoru olarak kullanılır.",
        ],
        "expected_range": (0.85, 1.0),  # all supported → high score
    },
    {
        "name": "2. Kısmi uydurma (1 unsupported claim)",
        "answer": "Python 1991 yılında Guido van Rossum tarafından oluşturulmuştur. "
                  "Python dünyanın en hızlı programlama dilidir.",
        "contexts": [
            "Python, Guido van Rossum tarafından oluşturulmuş, ilk olarak 1991'de "
            "yayınlanmış genel amaçlı bir programlama dilidir.",
        ],
        "expected_range": (0.55, 0.90),  # 1 unsupported → ~0.85
    },
    {
        "name": "3. Doğrudan çelişki (1 contradiction)",
        "answer": "Dünya güneş sisteminin en büyük gezegenidir.",
        "contexts": [
            "Jüpiter, güneş sistemindeki en büyük gezegendir. Dünya, güneş sisteminin "
            "beşinci en büyük gezegenidir.",
        ],
        "expected_range": (0.0, 0.75),  # contradiction → ~0.70
    },
    {
        "name": "4. Karışık (1 agreement + 1 unsupported + 1 contradiction)",
        "answer": "Docker, konteyner teknolojisidir. Docker 2010 yılında kurulmuştur. "
                  "Docker, Java ile yazılmıştır.",
        "contexts": [
            "Docker, 2013 yılında kurulan bir konteyner platformudur. Go programlama "
            "dili ile yazılmıştır.",
        ],
        "expected_range": (0.0, 0.60),  # unsupported + contradiction → ~0.55
    },
    {
        "name": "5. Paraphrase / inference testi",
        "answer": "Redis genellikle cache olarak kullanılır.",
        "contexts": [
            "Redis'in tipik kullanım alanları arasında oturum önbellekleme (session caching), "
            "pub/sub mesajlaşma ve sıralama tabloları (leaderboards) yer alır.",
        ],
        "expected_range": (0.85, 1.0),  # paraphrase → agreement
    },
    {
        "name": "6. Tamamen uydurma (no context support)",
        "answer": "Kubernetes 2005 yılında Microsoft tarafından geliştirilmiştir. "
                  "Kubernetes C++ ile yazılmıştır ve sadece Windows'ta çalışır.",
        "contexts": [
            "Kubernetes, Google tarafından tasarlanmış, 2014 yılında açık kaynak olarak "
            "yayınlanmış bir konteyner orkestrasyon sistemidir. Go ile yazılmıştır.",
        ],
        "expected_range": (0.0, 0.40),  # multiple problems
    },
]


# ── LLM Client ──────────────────────────────────────────────────────────

async def chat_completion(
    http: httpx.AsyncClient,
    system: str,
    user: str,
    max_tokens: int = 4096,
    json_schema: dict | None = None,
) -> tuple[str, int, int, float]:
    """Returns (content, prompt_tokens, completion_tokens, elapsed_seconds)."""
    payload: dict[str, Any] = {
        "model": MODEL,
        "max_completion_tokens": max_tokens,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    }
    if json_schema:
        payload["response_format"] = {"type": "json_schema", "json_schema": json_schema}

    t0 = time.perf_counter()
    resp = await http.post(
        f"{BASE_URL}/chat/completions",
        headers={"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"},
        json=payload,
    )
    elapsed = time.perf_counter() - t0
    resp.raise_for_status()
    data = resp.json()

    content = data["choices"][0]["message"].get("content", "")
    usage = data.get("usage", {})
    return content, usage.get("prompt_tokens", 0), usage.get("completion_tokens", 0), elapsed


def safe_parse(raw: str) -> dict:
    """Parse JSON from LLM output, handling markdown fences."""
    if not raw:
        return {}
    text = raw.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        lines = [l for l in lines if not l.strip().startswith("```")]
        text = "\n".join(lines).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        import re
        m = re.search(r"\{.*\}", text, re.DOTALL)
        if m:
            try:
                return json.loads(m.group())
            except json.JSONDecodeError:
                pass
    return {}


# ── Single-Call Approach ────────────────────────────────────────────────

async def run_single_call(
    http: httpx.AsyncClient, answer: str, contexts: list[str]
) -> dict[str, Any]:
    content, pt, ct, elapsed = await chat_completion(
        http,
        system=SINGLE_CALL_SYSTEM,
        user=build_user_prompt(answer, contexts),
        max_tokens=4096,
        json_schema=HALLUCINATION_JSON_SCHEMA,
    )
    parsed = safe_parse(content)
    claims = parsed.get("disagreement_claims", [])
    scores = score_hallucination_claims(claims)
    return {
        "approach": "single-call",
        "hallucination_score": scores["hallucination_score"],
        "faithfulness": scores["faithfulness"],
        "num_claims": len(claims),
        "claims": claims,
        "elapsed": elapsed,
        "prompt_tokens": pt,
        "completion_tokens": ct,
    }


# ── Two-Stage Approach ─────────────────────────────────────────────────

async def run_two_stage(
    http: httpx.AsyncClient, answer: str, contexts: list[str]
) -> dict[str, Any]:
    # Stage 1: free-text reasoning
    s1_content, s1_pt, s1_ct, s1_elapsed = await chat_completion(
        http,
        system=TWO_STAGE_S1_SYSTEM,
        user=build_user_prompt(answer, contexts),
        max_tokens=4096,
    )

    # Stage 2: convert to JSON
    s2_content, s2_pt, s2_ct, s2_elapsed = await chat_completion(
        http,
        system=TWO_STAGE_S2_SYSTEM,
        user=build_stage_2_user_prompt(s1_content),
        max_tokens=2048,
        json_schema=HALLUCINATION_JSON_SCHEMA,
    )

    parsed = safe_parse(s2_content)
    claims = parsed.get("disagreement_claims", [])
    scores = score_hallucination_claims(claims)
    return {
        "approach": "two-stage",
        "hallucination_score": scores["hallucination_score"],
        "faithfulness": scores["faithfulness"],
        "num_claims": len(claims),
        "claims": claims,
        "elapsed": s1_elapsed + s2_elapsed,
        "stage1_elapsed": s1_elapsed,
        "stage2_elapsed": s2_elapsed,
        "prompt_tokens": s1_pt + s2_pt,
        "completion_tokens": s1_ct + s2_ct,
        "stage1_reasoning_preview": s1_content[:300] if s1_content else "",
    }


# ── Claim Comparison ───────────────────────────────────────────────────

def claim_type_distribution(claims: list[dict]) -> dict[str, int]:
    dist: dict[str, int] = {"agreement": 0, "unsupported claim": 0, "confirmed contradiction": 0}
    for c in claims:
        dt = str(c.get("disagreement_type", "")).lower()
        if dt in dist:
            dist[dt] += 1
    return dist


def format_claims_summary(claims: list[dict]) -> str:
    lines = []
    for i, c in enumerate(claims, 1):
        dt = c.get("disagreement_type", "?")
        aq = c.get("answer_quote", "")[:60]
        lines.append(f"    [{i}] {dt}: \"{aq}...\"")
    return "\n".join(lines) if lines else "    (no claims)"


# ── Main Runner ─────────────────────────────────────────────────────────

@dataclass
class CaseResult:
    case_name: str
    single_call: dict[str, Any]
    two_stage: dict[str, Any]


async def run_benchmark(repeats: int, case_indices: list[int] | None) -> None:
    if not API_KEY:
        print("ERROR: OPENAI_API_KEY ortam değişkeni ayarlanmamış.")
        sys.exit(1)

    cases = TEST_CASES
    if case_indices:
        cases = [TEST_CASES[i - 1] for i in case_indices if 0 < i <= len(TEST_CASES)]

    print("=" * 80)
    print("  Hallucination Benchmark: Single-Call vs Two-Stage")
    print(f"  Model: {MODEL}")
    print(f"  Test cases: {len(cases)}, Repeats per case: {repeats}")
    print("=" * 80)

    all_single_scores: list[float] = []
    all_two_stage_scores: list[float] = []
    all_single_times: list[float] = []
    all_two_stage_times: list[float] = []
    total_single_tokens = 0
    total_two_stage_tokens = 0

    async with httpx.AsyncClient(timeout=TIMEOUT) as http:
        for case in cases:
            print(f"\n{'─' * 70}")
            print(f"  Case: {case['name']}")
            print(f"  Expected score range: {case['expected_range']}")
            print(f"{'─' * 70}")

            sc_results: list[dict] = []
            ts_results: list[dict] = []

            for r in range(1, repeats + 1):
                print(f"  Run {r}/{repeats}...", end=" ", flush=True)

                sc = await run_single_call(http, case["answer"], case["contexts"])
                ts = await run_two_stage(http, case["answer"], case["contexts"])

                sc_results.append(sc)
                ts_results.append(ts)

                print(
                    f"SC: {sc['hallucination_score']:.2f} ({sc['elapsed']:.1f}s, "
                    f"{sc['num_claims']} claims) | "
                    f"TS: {ts['hallucination_score']:.2f} ({ts['elapsed']:.1f}s, "
                    f"{ts['num_claims']} claims)"
                )

            # Aggregate per case
            sc_h_scores = [r["hallucination_score"] for r in sc_results if r["hallucination_score"] is not None]
            ts_h_scores = [r["hallucination_score"] for r in ts_results if r["hallucination_score"] is not None]
            sc_times = [r["elapsed"] for r in sc_results]
            ts_times = [r["elapsed"] for r in ts_results]
            sc_claims = [r["num_claims"] for r in sc_results]
            ts_claims = [r["num_claims"] for r in ts_results]

            all_single_scores.extend(sc_h_scores)
            all_two_stage_scores.extend(ts_h_scores)
            all_single_times.extend(sc_times)
            all_two_stage_times.extend(ts_times)
            for r in sc_results:
                total_single_tokens += r["prompt_tokens"] + r["completion_tokens"]
            for r in ts_results:
                total_two_stage_tokens += r["prompt_tokens"] + r["completion_tokens"]

            # Print case summary
            lo, hi = case["expected_range"]
            print(f"\n  {'Metric':<25} {'Single-Call':>15} {'Two-Stage':>15}")
            print(f"  {'─' * 55}")

            sc_mean = statistics.mean(sc_h_scores) if sc_h_scores else 0
            ts_mean = statistics.mean(ts_h_scores) if ts_h_scores else 0
            sc_in = lo <= sc_mean <= hi
            ts_in = lo <= ts_mean <= hi
            print(f"  {'Ort. h_score':<25} {sc_mean:>14.3f}{'✓' if sc_in else '✗'} {ts_mean:>14.3f}{'✓' if ts_in else '✗'}")

            if len(sc_h_scores) > 1:
                sc_std = statistics.stdev(sc_h_scores)
                ts_std = statistics.stdev(ts_h_scores) if len(ts_h_scores) > 1 else 0
                print(f"  {'Std dev (tutarlılık)':<25} {sc_std:>15.4f} {ts_std:>15.4f}")
                sc_range = max(sc_h_scores) - min(sc_h_scores)
                ts_range = max(ts_h_scores) - min(ts_h_scores)
                print(f"  {'Score range':<25} {sc_range:>15.4f} {ts_range:>15.4f}")

            print(f"  {'Ort. süre (s)':<25} {statistics.mean(sc_times):>15.1f} {statistics.mean(ts_times):>15.1f}")
            print(f"  {'Ort. claim sayısı':<25} {statistics.mean(sc_claims):>15.1f} {statistics.mean(ts_claims):>15.1f}")

            # Show claim type distributions from last run
            sc_dist = claim_type_distribution(sc_results[-1]["claims"])
            ts_dist = claim_type_distribution(ts_results[-1]["claims"])
            print(f"\n  Son run claim dağılımı:")
            print(f"    {'Type':<25} {'SC':>5} {'TS':>5}")
            for key in ["agreement", "unsupported claim", "confirmed contradiction"]:
                print(f"    {key:<25} {sc_dist.get(key, 0):>5} {ts_dist.get(key, 0):>5}")

            # Show individual claims from last run of each
            print(f"\n  Single-Call claims (son run):")
            print(format_claims_summary(sc_results[-1]["claims"]))
            print(f"\n  Two-Stage claims (son run):")
            print(format_claims_summary(ts_results[-1]["claims"]))

            if ts_results[-1].get("stage1_reasoning_preview"):
                print(f"\n  Two-Stage S1 reasoning preview:")
                print(f"    {ts_results[-1]['stage1_reasoning_preview'][:200]}...")

    # ── Global Summary ──────────────────────────────────────────────────
    print(f"\n{'=' * 80}")
    print("  GENEL ÖZET")
    print(f"{'=' * 80}")
    print(f"\n  {'Metric':<30} {'Single-Call':>15} {'Two-Stage':>15}")
    print(f"  {'─' * 60}")

    if all_single_scores and all_two_stage_scores:
        print(f"  {'Ortalama h_score':<30} {statistics.mean(all_single_scores):>15.3f} {statistics.mean(all_two_stage_scores):>15.3f}")
        if len(all_single_scores) > 1 and len(all_two_stage_scores) > 1:
            print(f"  {'Std dev (tüm caseler)':<30} {statistics.stdev(all_single_scores):>15.4f} {statistics.stdev(all_two_stage_scores):>15.4f}")
    if all_single_times and all_two_stage_times:
        print(f"  {'Ortalama süre (s)':<30} {statistics.mean(all_single_times):>15.1f} {statistics.mean(all_two_stage_times):>15.1f}")
        print(f"  {'Toplam süre (s)':<30} {sum(all_single_times):>15.1f} {sum(all_two_stage_times):>15.1f}")
    print(f"  {'Toplam token':<30} {total_single_tokens:>15,} {total_two_stage_tokens:>15,}")

    if all_single_times and all_two_stage_times:
        speedup = statistics.mean(all_two_stage_times) / statistics.mean(all_single_times)
        print(f"\n  Two-Stage / Single-Call süre oranı: {speedup:.2f}x")

    if len(all_single_scores) > 1 and len(all_two_stage_scores) > 1:
        sc_std = statistics.stdev(all_single_scores)
        ts_std = statistics.stdev(all_two_stage_scores)
        winner = "Two-Stage" if ts_std <= sc_std else "Single-Call"
        print(f"  Daha tutarlı yaklaşım: {winner} (std: SC={sc_std:.4f}, TS={ts_std:.4f})")

    print()


def main() -> None:
    parser = argparse.ArgumentParser(description="Hallucination: Single-Call vs Two-Stage Benchmark")
    parser.add_argument("--repeats", type=int, default=3, help="Her case kaç kez tekrarlanacak (default: 3)")
    parser.add_argument(
        "--cases", type=str, default=None,
        help="Çalıştırılacak case numaraları, virgülle ayrılmış (default: hepsi). Örn: 1,3,5"
    )
    args = parser.parse_args()

    case_indices = None
    if args.cases:
        case_indices = [int(x.strip()) for x in args.cases.split(",")]

    asyncio.run(run_benchmark(repeats=args.repeats, case_indices=case_indices))


if __name__ == "__main__":
    main()
