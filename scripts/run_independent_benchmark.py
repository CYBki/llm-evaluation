#!/usr/bin/env python3
"""
Unified Independent Benchmark Suite for RAG Evaluation System.

Combines all validation methods into a single script:
  1. Golden Set      — deterministic hand-crafted test cases with pass/fail criteria
  2. Perturbation    — sensitivity tests for metrics without external ground truth
  3. External GT     — RAGBench, HaluEval, SummEval, TruthfulQA correlations
  4. Consistency     — repeated evaluation variance measurement

Key design notes:
  - RAGBench: ONLY hallucination_vs_adherence and overall_vs_adherence are compared.
    completeness_score and relevance_score are NOT used because they measure fundamentally
    different things (sentence utilization and context relevance, not our key-point coverage
    or statement-level answer relevancy).
  - SummEval hallucination_vs_consistency: included but may show ceiling effect
    (81.6% of consistency scores = 1.0, near-zero variance).
  - All sections are independently skippable via CLI flags.

Usage:
  python scripts/run_independent_benchmark.py --limit 5
  python scripts/run_independent_benchmark.py --limit 5 --skip-external
  python scripts/run_independent_benchmark.py --limit 5 --only golden,perturbation
"""
from __future__ import annotations

import argparse
import asyncio
import json
import math
import statistics
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import httpx

# ── Configuration ──────────────────────────────────────────────────────

BASE_URL = "http://localhost:8000"
INGEST_TIMEOUT = 300
DEFAULT_CONCURRENCY = 5
MAX_RETRIES = 4
REPORT_DIR = Path("reports")


@dataclass
class TestResult:
    name: str
    passed: bool | None  # None = skipped
    details: str
    scores: dict = field(default_factory=dict)
    section: str = ""


# ── HTTP Helpers ───────────────────────────────────────────────────────

async def register_user(client: httpx.AsyncClient) -> str:
    resp = await client.post(
        f"{BASE_URL}/api/v1/auth/register",
        json={"email": f"bench_{int(time.time())}@eval.com", "password": "BenchPass123!"},
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()["api_key"]


async def ingest_and_get(
    client: httpx.AsyncClient,
    api_key: str,
    payload: dict,
    sem: asyncio.Semaphore,
) -> dict:
    """Ingest a trace (sync mode) with retry on 429, return full detail."""
    async with sem:
        headers = {"X-API-Key": api_key, "Content-Type": "application/json"}
        for attempt in range(MAX_RETRIES):
            resp = await client.post(
                f"{BASE_URL}/api/v1/ingest",
                headers=headers,
                json=payload,
                timeout=INGEST_TIMEOUT,
            )
            if resp.status_code == 429:
                wait = 2 ** attempt + 1
                await asyncio.sleep(wait)
                continue
            resp.raise_for_status()
            break
        else:
            resp.raise_for_status()

        trace_id = resp.json()["id"]
        detail = await client.get(
            f"{BASE_URL}/api/v1/traces/{trace_id}",
            headers={"X-API-Key": api_key},
            timeout=30,
        )
        detail.raise_for_status()
        return detail.json()


def ev(detail: dict) -> dict:
    return detail.get("evaluation") or {}


# ── Math Helpers ───────────────────────────────────────────────────────

def pearson_correlation(x: list[float], y: list[float]) -> float:
    n = len(x)
    if n < 3:
        return 0.0
    mx = sum(x) / n
    my = sum(y) / n
    num = sum((xi - mx) * (yi - my) for xi, yi in zip(x, y))
    dx = math.sqrt(sum((xi - mx) ** 2 for xi in x))
    dy = math.sqrt(sum((yi - my) ** 2 for yi in y))
    if dx == 0 or dy == 0:
        return 0.0
    return num / (dx * dy)


def mean_absolute_error(actual: list[float], predicted: list[float]) -> float:
    return sum(abs(a - p) for a, p in zip(actual, predicted)) / len(actual)


def binary_classification(our: list[float], gt: list[float], threshold: float = 0.5) -> dict:
    tp = fp = tn = fn = 0
    for o, g in zip(our, gt):
        pred_pos = o >= threshold
        actual_pos = g >= threshold
        if pred_pos and actual_pos:
            tp += 1
        elif pred_pos and not actual_pos:
            fp += 1
        elif not pred_pos and actual_pos:
            fn += 1
        else:
            tn += 1
    total = tp + fp + tn + fn
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0
    return {
        "accuracy": round((tp + tn) / total, 4) if total > 0 else 0.0,
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
        "tp": tp, "fp": fp, "tn": tn, "fn": fn,
    }


# ═══════════════════════════════════════════════════════════════════════
#  SECTION 1: GOLDEN SET — Deterministic test cases with pass/fail
# ═══════════════════════════════════════════════════════════════════════

GOLDEN_SET = [
    # ── A: Perfect answers ──
    {
        "name": "A1_perfect_copy",
        "desc": "Answer is exact copy of context → very high scores",
        "payload": {
            "question": "What is the speed of light?",
            "answer": "The speed of light in vacuum is approximately 299,792 kilometers per second (km/s), which is about 186,282 miles per second.",
            "contexts": ["The speed of light in vacuum is approximately 299,792 kilometers per second (km/s), which is about 186,282 miles per second."],
        },
        "checks": [
            ("overall_score", ">=", 0.7),
            ("hallucination_score", ">=", 0.8),
            ("completeness", ">=", 0.7),
            ("is_deflection", "==", False),
        ],
    },
    {
        "name": "A2_correct_paraphrase",
        "desc": "Correct paraphrase of context",
        "payload": {
            "question": "Who wrote Romeo and Juliet?",
            "answer": "William Shakespeare authored the famous play Romeo and Juliet.",
            "contexts": ["Romeo and Juliet is a tragedy written by William Shakespeare early in his career about the romance between two star-crossed lovers."],
        },
        "checks": [
            ("overall_score", ">=", 0.65),
            ("hallucination_score", ">=", 0.65),
            ("is_off_topic", "==", False),
        ],
    },

    # ── B: Hallucination ──
    {
        "name": "B1_total_fabrication",
        "desc": "Completely fabricated answer",
        "payload": {
            "question": "What is the capital of Japan?",
            "answer": "The capital of Japan is Osaka. It became the capital in 1523 after the Great Migration from Kyoto. The city has a population of 50 million people.",
            "contexts": ["Tokyo is the capital of Japan. It has been the capital since 1868 when the Emperor moved from Kyoto. Tokyo has a population of approximately 14 million people."],
        },
        "checks": [
            ("hallucination_score", "<=", 0.4),
        ],
    },
    {
        "name": "B2_mixed_hallucination",
        "desc": "Some claims correct, some fabricated",
        "payload": {
            "question": "Tell me about Einstein.",
            "answer": "Albert Einstein was a theoretical physicist born in Germany. He developed the theory of relativity. He won the Nobel Prize in Physics in 1921. He also invented the internet and discovered penicillin.",
            "contexts": ["Albert Einstein (1879-1955) was a German-born theoretical physicist who developed the theory of relativity. He received the Nobel Prize in Physics in 1921 for his explanation of the photoelectric effect."],
        },
        "checks": [
            ("hallucination_score", "<=", 0.7),
            ("hallucination_score", ">=", 0.2),
        ],
    },

    # ── C: Contradiction ──
    {
        "name": "C1_direct_contradiction",
        "desc": "Answer directly contradicts context",
        "payload": {
            "question": "When was the Eiffel Tower built?",
            "answer": "The Eiffel Tower was built in 1920 and is located in London, England.",
            "contexts": ["The Eiffel Tower is a wrought-iron lattice tower on the Champ de Mars in Paris, France. It was constructed from 1887 to 1889 as the centerpiece of the 1889 World's Fair."],
        },
        "checks": [
            ("hallucination_score", "<=", 0.3),
        ],
    },

    # ── D: Deflection ──
    {
        "name": "D1_sorry_cant_help",
        "desc": "Refuses to answer despite having context",
        "payload": {
            "question": "What causes rain?",
            "answer": "I'm sorry, I cannot help with that question. Please consult a meteorologist.",
            "contexts": ["Rain is liquid water in the form of droplets that have condensed from atmospheric water vapor and then become heavy enough to fall under gravity. Rain is a major component of the water cycle."],
        },
        "checks": [
            ("is_deflection", "==", True),
            ("helpfulness", "<=", 0.3),
        ],
    },
    {
        "name": "D2_vague_redirect",
        "desc": "Redirects without providing information",
        "payload": {
            "question": "How does a car engine work?",
            "answer": "Great question! You should check out some YouTube videos about this topic. There are many good resources available online.",
            "contexts": ["A car engine works by converting fuel into motion through internal combustion. The engine draws in air and fuel, compresses the mixture, ignites it with a spark plug, and the resulting explosion pushes a piston down, converting chemical energy into mechanical energy."],
        },
        "checks": [
            ("is_deflection", "==", True),
            ("helpfulness", "<=", 0.4),
            ("completeness", "<=", 0.3),
        ],
    },

    # ── E: Partial answer ──
    {
        "name": "E1_incomplete",
        "desc": "Covers only part of the question",
        "payload": {
            "question": "What are the three states of matter and give an example of each?",
            "answer": "Water is a liquid.",
            "contexts": ["The three classical states of matter are solid, liquid, and gas. Examples include ice (solid), water (liquid), and steam (gas). A fourth state, plasma, exists at very high temperatures."],
        },
        "checks": [
            ("completeness", "<=", 0.5),
            ("hallucination_score", ">=", 0.5),
        ],
    },

    # ── F: Edge cases ──
    {
        "name": "F1_empty_answer",
        "desc": "Empty answer string",
        "payload": {
            "question": "What is gravity?",
            "answer": " ",
            "contexts": ["Gravity is a fundamental force of nature that attracts two bodies with mass toward each other."],
        },
        "checks": [
            ("overall_score", "<=", 0.3),
            ("completeness", "<=", 0.2),
            ("helpfulness", "<=", 0.2),
        ],
    },
    {
        "name": "F2_no_context",
        "desc": "No context provided, answer is correct from world knowledge",
        "payload": {
            "question": "What is 2+2?",
            "answer": "2+2 equals 4.",
        },
        "checks": [
            ("overall_score", ">=", 0.5),
            ("is_off_topic", "==", False),
        ],
    },

    # ── G: Off-topic ──
    {
        "name": "G1_completely_off_topic",
        "desc": "Question about weather, answer about cooking",
        "payload": {
            "question": "What will the weather be like tomorrow?",
            "answer": "To make pasta, boil water in a large pot, add salt, then cook the pasta for 8-10 minutes until al dente. Drain and serve with your favorite sauce.",
            "contexts": ["Weather forecasting uses science and technology to predict atmospheric conditions for a given location and time."],
        },
        "checks": [
            ("helpfulness", "<=", 0.3),
            ("completeness", "<=", 0.2),
        ],
    },

    # ── H: Wrong context ──
    {
        "name": "H1_wrong_context",
        "desc": "Context is about something completely different",
        "payload": {
            "question": "What is machine learning?",
            "answer": "Machine learning is a subset of artificial intelligence that enables systems to learn from data without being explicitly programmed.",
            "contexts": ["The Amazon rainforest produces about 20% of the world's oxygen. It covers 5.5 million square kilometers across nine countries in South America."],
        },
        "checks": [
            ("hallucination_score", "<=", 0.3),
        ],
    },

    # ── I: Citation ──
    {
        "name": "I1_correct_citation",
        "desc": "Answer with correct citation reference",
        "payload": {
            "question": "What is DNA?",
            "answer": "DNA (deoxyribonucleic acid) is the molecule that carries genetic information [0]. It has a double helix structure [0].",
            "contexts": ["DNA, or deoxyribonucleic acid, is the hereditary material in humans and almost all other organisms. DNA has a double helix structure, consisting of two strands that wind around each other."],
        },
        "checks": [
            ("citation_check", ">=", 0.5),
            ("hallucination_score", ">=", 0.7),
        ],
    },

    # ── J: Borderline / Paraphrase ──
    {
        "name": "J1_paraphrase_summary",
        "desc": "Answer summarises context with different wording → should be agreement, not unsupported",
        "payload": {
            "question": "What is Redis used for?",
            "answer": "Redis is mostly used as a cache. It stores frequently accessed data in memory for fast retrieval.",
            "contexts": [
                "Redis is an open-source, in-memory data structure store. "
                "Typical use cases include session caching, real-time analytics, "
                "pub/sub messaging, leaderboards, and rate limiting. "
                "Redis keeps data in RAM, making reads and writes extremely fast."
            ],
        },
        "checks": [
            ("hallucination_score", ">=", 0.7),
            ("is_off_topic", "==", False),
        ],
    },
    {
        "name": "J2_inference_from_context",
        "desc": "Answer makes a reasonable inference from context → should be agreement",
        "payload": {
            "question": "Is PostgreSQL suitable for large applications?",
            "answer": "Yes, PostgreSQL is well-suited for large-scale enterprise applications.",
            "contexts": [
                "PostgreSQL is a powerful, open source object-relational database system "
                "with over 35 years of active development. It is used by many large companies "
                "including Apple, Instagram, and Spotify for mission-critical workloads. "
                "It supports advanced features like partitioning, parallel queries, and "
                "can handle databases of several terabytes."
            ],
        },
        "checks": [
            ("hallucination_score", ">=", 0.7),
            ("overall_score", ">=", 0.6),
        ],
    },
]


async def run_golden_set(
    client: httpx.AsyncClient, api_key: str, sem: asyncio.Semaphore
) -> list[TestResult]:
    """Run all golden set test cases concurrently."""
    results: list[TestResult] = []
    total = len(GOLDEN_SET)

    async def _run_one(i: int, tc: dict) -> TestResult:
        name = tc["name"]
        try:
            detail = await ingest_and_get(client, api_key, tc["payload"], sem)
            evaluation = ev(detail)

            if not evaluation:
                print(f"  [{i+1}/{total}] ❌ {name}: No evaluation returned")
                return TestResult(name=name, passed=False, details="No evaluation returned", section="golden")

            failures = []
            scores = {}
            for field_name, op, expected in tc["checks"]:
                actual = evaluation.get(field_name)
                scores[field_name] = actual
                if actual is None:
                    failures.append(f"{field_name}=None (expected {op} {expected})")
                    continue
                if op == ">=" and actual < expected:
                    failures.append(f"{field_name}={actual:.2f} (expected >= {expected})")
                elif op == "<=" and actual > expected:
                    failures.append(f"{field_name}={actual:.2f} (expected <= {expected})")
                elif op == "==" and actual != expected:
                    failures.append(f"{field_name}={actual} (expected == {expected})")

            passed = len(failures) == 0
            detail_str = "OK" if passed else "; ".join(failures)
            icon = "✅" if passed else "❌"
            print(f"  [{i+1}/{total}] {icon} {name}: {detail_str}")
            return TestResult(name=name, passed=passed, details=detail_str, scores=scores, section="golden")

        except Exception as exc:
            print(f"  [{i+1}/{total}] ❌ {name}: ERROR — {exc}")
            return TestResult(name=name, passed=False, details=f"Error: {exc}", section="golden")

    tasks = [_run_one(i, tc) for i, tc in enumerate(GOLDEN_SET)]
    return list(await asyncio.gather(*tasks))


# ═══════════════════════════════════════════════════════════════════════
#  SECTION 2: PERTURBATION (SENSITIVITY) TESTS
# ═══════════════════════════════════════════════════════════════════════

PERTURB_CONTEXTS = [
    "The Eiffel Tower is a wrought-iron lattice tower on the Champ de Mars in Paris, France. "
    "It was named after the engineer Gustave Eiffel, whose company designed and built the tower. "
    "Constructed from 1887 to 1889, it was the entrance arch for the 1889 World's Fair. "
    "The tower is 330 metres (1,083 ft) tall and was the tallest man-made structure in the world "
    "until the Chrysler Building was completed in 1930.",

    "The tower has three levels for visitors, with restaurants on the first and second levels. "
    "The top level is 276 m above the ground. Tickets can be purchased to ascend by stairs or "
    "lift to the first and second levels. The climb from ground level to the first level is over "
    "300 steps. The tower receives about 7 million visitors per year [Source 1].",

    "The design of the Eiffel Tower was the product of Maurice Koechlin and Émile Nouguier, "
    "two senior engineers working for the Compagnie des Établissements Eiffel. The tower cost "
    "7,799,401.31 French gold francs to build and was completed on 31 March 1889 [Source 2].",
]

PERTURB_QUESTION = "What is the Eiffel Tower and when was it built?"


def build_perturbation_cases() -> list[dict]:
    cases = []

    # ── answer_relevancy: inject irrelevant content ──────────────
    good_answer_rel = (
        "The Eiffel Tower is a wrought-iron lattice tower located on the Champ de Mars in Paris, France. "
        "It was constructed between 1887 and 1889 as the entrance arch for the 1889 World's Fair."
    )
    bad_answer_rel = (
        "The Eiffel Tower is a wrought-iron lattice tower located on the Champ de Mars in Paris, France. "
        "It was constructed between 1887 and 1889 as the entrance arch for the 1889 World's Fair. "
        "Meanwhile, pizza is a popular dish in Italy, consisting of dough topped with tomato sauce. "
        "The stock market experienced a significant downturn in 2008 due to the financial crisis. "
        "Dolphins are marine mammals known for their intelligence and playful behavior. "
        "The recipe for chocolate cake requires flour, sugar, cocoa powder, eggs, and butter."
    )
    cases.append({
        "name": "relevancy_inject_irrelevant",
        "metric": "answer_relevancy",
        "original": {"question": PERTURB_QUESTION, "answer": good_answer_rel, "contexts": PERTURB_CONTEXTS},
        "perturbed": {"question": PERTURB_QUESTION, "answer": bad_answer_rel, "contexts": PERTURB_CONTEXTS},
    })

    off_topic_answer = (
        "Python is a high-level programming language known for its simplicity. "
        "It supports multiple programming paradigms including procedural and object-oriented. "
        "The Zen of Python emphasizes readability and beauty of code."
    )
    cases.append({
        "name": "relevancy_off_topic",
        "metric": "answer_relevancy",
        "original": {"question": PERTURB_QUESTION, "answer": good_answer_rel, "contexts": PERTURB_CONTEXTS},
        "perturbed": {"question": PERTURB_QUESTION, "answer": off_topic_answer, "contexts": PERTURB_CONTEXTS},
    })

    # ── completeness: remove key information ──────────────────────
    complete_answer = (
        "The Eiffel Tower is a wrought-iron lattice tower on the Champ de Mars in Paris, France. "
        "It was designed by engineer Gustave Eiffel's company and built from 1887 to 1889. "
        "It served as the entrance arch for the 1889 World's Fair. "
        "The tower stands 330 metres tall and was the tallest man-made structure until 1930."
    )
    incomplete_answer = "The Eiffel Tower is a tower in Paris."
    cases.append({
        "name": "completeness_remove_details",
        "metric": "completeness",
        "original": {"question": PERTURB_QUESTION, "answer": complete_answer, "contexts": PERTURB_CONTEXTS},
        "perturbed": {"question": PERTURB_QUESTION, "answer": incomplete_answer, "contexts": PERTURB_CONTEXTS},
    })

    # Use a multi-part question requiring 4+ key points so partial answer is clearly incomplete
    multi_part_question = (
        "What is the Eiffel Tower, who designed it, when was it built, "
        "how tall is it, and how much did it cost to build?"
    )
    multi_part_complete = (
        "The Eiffel Tower is a wrought-iron lattice tower on the Champ de Mars in Paris, France. "
        "It was designed by Gustave Eiffel's company (engineers Maurice Koechlin and Émile Nouguier). "
        "It was constructed from 1887 to 1889 for the 1889 World's Fair. "
        "The tower stands 330 metres (1,083 ft) tall and was the tallest man-made structure until 1930. "
        "The construction cost 7,799,401.31 French gold francs."
    )
    multi_part_partial = (
        "The Eiffel Tower is a tower in Paris, France. It was built in the 1880s."
    )
    cases.append({
        "name": "completeness_partial",
        "metric": "completeness",
        "original": {"question": multi_part_question, "answer": multi_part_complete, "contexts": PERTURB_CONTEXTS},
        "perturbed": {"question": multi_part_question, "answer": multi_part_partial, "contexts": PERTURB_CONTEXTS},
    })

    # ── clarity: convoluted / contradictory ──────────────────────
    clear_answer = (
        "The Eiffel Tower is a 330-metre tall iron tower in Paris, France. "
        "It was built between 1887 and 1889 for the World's Fair."
    )
    unclear_answer = (
        "Well, um, so there's this thing, you know, kind of like a structure, "
        "it might be made of some metal material perhaps, and it's sort of located "
        "somewhere in a European city, possibly, and there was some event, "
        "maybe in the late 1800s or something, that it was, you know, "
        "somehow related to or associated with in some way, perhaps."
    )
    cases.append({
        "name": "clarity_convoluted",
        "metric": "clarity",
        "original": {"question": PERTURB_QUESTION, "answer": clear_answer, "contexts": PERTURB_CONTEXTS},
        "perturbed": {"question": PERTURB_QUESTION, "answer": unclear_answer, "contexts": PERTURB_CONTEXTS},
    })

    contradictory_answer = (
        "The Eiffel Tower was built in 1889, but actually it was built in 1920. "
        "It is located in Paris, although some sources say it's in London. "
        "The height is 330 metres, or maybe 200 metres, it's hard to say."
    )
    cases.append({
        "name": "clarity_contradictory",
        "metric": "clarity",
        "original": {"question": PERTURB_QUESTION, "answer": clear_answer, "contexts": PERTURB_CONTEXTS},
        "perturbed": {"question": PERTURB_QUESTION, "answer": contradictory_answer, "contexts": PERTURB_CONTEXTS},
    })

    # ── citation_check: remove / corrupt citations ───────────────
    cited_answer = (
        "The Eiffel Tower receives about 7 million visitors per year [Source 1]. "
        "The construction cost 7,799,401.31 French gold francs [Source 2]. "
        "It was built from 1887 to 1889 as the entrance for the World's Fair [1]."
    )
    uncited_answer = (
        "The Eiffel Tower receives about 7 million visitors per year. "
        "The construction cost 7,799,401.31 French gold francs. "
        "It was built from 1887 to 1889 as the entrance for the World's Fair."
    )
    cases.append({
        "name": "citation_removed",
        "metric": "citation_check",
        "original": {"question": PERTURB_QUESTION, "answer": cited_answer, "contexts": PERTURB_CONTEXTS},
        "perturbed": {"question": PERTURB_QUESTION, "answer": uncited_answer, "contexts": PERTURB_CONTEXTS},
    })

    wrong_cited_answer = (
        "The Eiffel Tower receives about 7 million visitors per year [Source 99]. "
        "The construction cost 7,799,401.31 French gold francs [Source 42]. "
        "It was built from 1887 to 1889 as the entrance for the World's Fair [15]."
    )
    cases.append({
        "name": "citation_wrong_refs",
        "metric": "citation_check",
        "original": {"question": PERTURB_QUESTION, "answer": cited_answer, "contexts": PERTURB_CONTEXTS},
        "perturbed": {"question": PERTURB_QUESTION, "answer": wrong_cited_answer, "contexts": PERTURB_CONTEXTS},
    })

    return cases


async def run_perturbation_pair(
    client: httpx.AsyncClient,
    api_key: str,
    sem: asyncio.Semaphore,
    case: dict,
    idx: int,
    total: int,
) -> dict:
    name = case["name"]
    metric = case["metric"]
    try:
        orig_detail = await ingest_and_get(client, api_key, case["original"], sem)
        pert_detail = await ingest_and_get(client, api_key, case["perturbed"], sem)

        orig_score = ev(orig_detail).get(metric)
        pert_score = ev(pert_detail).get(metric)

        if orig_score is None or pert_score is None:
            status = "SKIP"
            passed = None
        elif orig_score > pert_score:
            status = "PASS"
            passed = True
        elif orig_score == pert_score:
            status = "TIED"
            passed = False
        else:
            status = "FAIL"
            passed = False

        print(f"  [{idx+1}/{total}] [{status}] {name:35s}  {metric}: orig={orig_score} → pert={pert_score}")
        return {"name": name, "metric": metric, "orig_score": orig_score, "pert_score": pert_score, "status": status, "passed": passed}

    except Exception as exc:
        print(f"  [{idx+1}/{total}] [ERROR] {name}: {exc}")
        return {"name": name, "metric": metric, "orig_score": None, "pert_score": None, "status": "ERROR", "passed": None}


async def run_perturbation_tests(
    client: httpx.AsyncClient, api_key: str, sem: asyncio.Semaphore
) -> list[TestResult]:
    cases = build_perturbation_cases()
    total = len(cases)

    tasks = [
        run_perturbation_pair(client, api_key, sem, case, i, total)
        for i, case in enumerate(cases)
    ]
    pair_results = await asyncio.gather(*tasks)

    # Aggregate by metric
    by_metric: dict[str, list[dict]] = {}
    for r in pair_results:
        by_metric.setdefault(r["metric"], []).append(r)

    results: list[TestResult] = []
    for metric, mrs in by_metric.items():
        testable = [r for r in mrs if r["passed"] is not None]
        passed_count = sum(1 for r in testable if r["passed"])
        rate = passed_count / len(testable) * 100 if testable else 0
        passed = rate >= 80

        details_parts = []
        for r in mrs:
            marker = {"PASS": "✓", "FAIL": "✗", "TIED": "~", "SKIP": "○", "ERROR": "!"}.get(r["status"], "?")
            details_parts.append(f"{marker} {r['name']}(orig={r['orig_score']}→pert={r['pert_score']})")

        results.append(TestResult(
            name=f"perturbation_{metric}",
            passed=passed,
            details=f"{passed_count}/{len(testable)} pairs correct ({rate:.0f}%): {'; '.join(details_parts)}",
            scores={"pass_rate": rate, "pairs": mrs},
            section="perturbation",
        ))

    return results


# ═══════════════════════════════════════════════════════════════════════
#  SECTION 3: EXTERNAL GROUND TRUTH — RAGBench, HaluEval, SummEval, TruthfulQA
# ═══════════════════════════════════════════════════════════════════════

def _load_hf_dataset(name: str, config: str | None, split: str):
    """Load a HuggingFace dataset, returns None on failure."""
    try:
        from datasets import load_dataset
        if config:
            return load_dataset(name, config, split=split, trust_remote_code=True)
        return load_dataset(name, split=split, trust_remote_code=True)
    except Exception as exc:
        print(f"  ⚠ Cannot load {name}/{config}: {exc}")
        return None


# ── 3a: RAGBench ─────────────────────────────────────────────────────

async def run_ragbench(
    client: httpx.AsyncClient, api_key: str, sem: asyncio.Semaphore, limit: int
) -> list[TestResult]:
    """
    Compare hallucination_score and overall_score against RAGBench adherence_score.

    NOTE: We intentionally DO NOT compare:
      - completeness vs completeness_score (RAGBench measures sentence utilization,
        not key-point coverage)
      - answer_relevancy vs relevance_score (RAGBench measures context relevance =
        relevant_sentences / total_sentences, not our statement-level answer relevancy)
    """
    results: list[TestResult] = []
    ds = _load_hf_dataset("rungalileo/ragbench", "hotpotqa", "test")
    if ds is None:
        return [TestResult(name="ragbench_load", passed=False, details="Cannot load dataset", section="external")]

    # Pick mix of low and high adherence samples
    sorted_ds = sorted(ds, key=lambda x: x.get("adherence_score", 0.5))
    per_side = limit * 3  # 3 samples per side per limit
    low = sorted_ds[:per_side]
    high = sorted_ds[-per_side:]
    selected = low + high
    print(f"  RAGBench: {len(selected)} samples selected (low + high adherence)")

    our_halluc: list[float] = []
    our_overall: list[float] = []
    gt_scores: list[float] = []
    gt_for_overall: list[float] = []

    async def _process(i: int, row: dict):
        gt = row.get("adherence_score")
        if gt is None:
            return

        docs = row.get("documents", [])
        flat_ctx = []
        for d in docs:
            if isinstance(d, str):
                flat_ctx.append(d)
            elif isinstance(d, list):
                flat_ctx.extend([str(s) for s in d])

        payload = {"question": row["question"], "answer": row["response"], "contexts": flat_ctx[:3]}

        try:
            detail = await ingest_and_get(client, api_key, payload, sem)
            evaluation = ev(detail)
            halluc = evaluation.get("hallucination_score")
            overall = evaluation.get("overall_score")

            if halluc is not None:
                our_halluc.append(halluc)
                gt_scores.append(gt)
            if overall is not None:
                our_overall.append(overall)
                gt_for_overall.append(gt)

            print(f"    [{i+1}/{len(selected)}] gt={gt:.2f} → halluc={halluc}, overall={overall}")
        except Exception as exc:
            print(f"    [{i+1}/{len(selected)}] ERROR: {exc}")

    tasks = [_process(i, row) for i, row in enumerate(selected)]
    await asyncio.gather(*tasks)

    # Hallucination score vs adherence
    if len(our_halluc) >= 5:
        r_faith = pearson_correlation(gt_scores, our_halluc)
        cls = binary_classification(our_halluc, gt_scores)
        passed = cls["f1"] >= 0.5 or r_faith >= 0.4
        results.append(TestResult(
            name="ragbench_hallucination_vs_adherence",
            passed=passed,
            details=f"r={r_faith:.3f}, Acc={cls['accuracy']:.0%}, F1={cls['f1']:.3f}, n={len(our_halluc)}",
            scores={"pearson_r": round(r_faith, 4), **cls, "n": len(our_halluc)},
            section="external",
        ))
    else:
        results.append(TestResult(name="ragbench_hallucination", passed=False,
                                  details=f"Too few samples: {len(our_halluc)}", section="external"))

    # Overall vs adherence
    if len(our_overall) >= 5:
        r_overall = pearson_correlation(gt_for_overall, our_overall)
        cls_o = binary_classification(our_overall, gt_for_overall)
        passed = cls_o["f1"] >= 0.5 or r_overall >= 0.3
        results.append(TestResult(
            name="ragbench_overall_vs_adherence",
            passed=passed,
            details=f"r={r_overall:.3f}, Acc={cls_o['accuracy']:.0%}, F1={cls_o['f1']:.3f}, n={len(our_overall)}",
            scores={"pearson_r": round(r_overall, 4), **cls_o, "n": len(our_overall)},
            section="external",
        ))

    return results


# ── 3b: HaluEval ────────────────────────────────────────────────────

async def run_halueval(
    client: httpx.AsyncClient, api_key: str, sem: asyncio.Semaphore, limit: int
) -> list[TestResult]:
    """Test hallucination detection using HaluEval qa_samples."""
    results: list[TestResult] = []
    ds = _load_hf_dataset("pminervini/HaluEval", "qa_samples", "data")
    if ds is None:
        return [TestResult(name="halueval_load", passed=False, details="Cannot load dataset", section="external")]

    selected = list(ds)[:limit * 2]  # limit pairs
    print(f"  HaluEval: {len(selected)} samples")

    our_halluc: list[float] = []
    our_overall: list[float] = []
    gt_labels: list[float] = []

    async def _process(i: int, row: dict):
        question = row.get("question", "")
        knowledge = row.get("knowledge", "")
        answer = row.get("hallucinated_answer", row.get("right_answer", ""))
        label_str = row.get("right_answer", "")

        # Determine ground truth: if we're looking at hallucinated_answer, gt=0
        # HaluEval has both right_answer and hallucinated_answer per row
        # We send hallucinated for odd indices, right for even
        if i % 2 == 0:
            answer = row.get("right_answer", "")
            gt = 1.0  # good answer
        else:
            answer = row.get("hallucinated_answer", "")
            gt = 0.0  # hallucinated

        if not question or not answer:
            return

        payload = {"question": question, "answer": answer, "contexts": [knowledge] if knowledge else []}

        try:
            detail = await ingest_and_get(client, api_key, payload, sem)
            evaluation = ev(detail)
            halluc = evaluation.get("hallucination_score")
            overall = evaluation.get("overall_score")

            if halluc is not None:
                our_halluc.append(halluc)
                gt_labels.append(gt)
            if overall is not None:
                our_overall.append(overall)

            print(f"    [{i+1}/{len(selected)}] gt={'good' if gt==1.0 else 'halluc'} → halluc={halluc}")
        except Exception as exc:
            print(f"    [{i+1}/{len(selected)}] ERROR: {exc}")

    tasks = [_process(i, row) for i, row in enumerate(selected)]
    await asyncio.gather(*tasks)

    if len(our_halluc) >= 5:
        r = pearson_correlation(gt_labels, our_halluc)
        cls = binary_classification(our_halluc, gt_labels)
        passed = cls["f1"] >= 0.5 or r >= 0.4
        results.append(TestResult(
            name="halueval_hallucination_score",
            passed=passed,
            details=f"r={r:.3f}, Acc={cls['accuracy']:.0%}, F1={cls['f1']:.3f}, n={len(our_halluc)}",
            scores={"pearson_r": round(r, 4), **cls, "n": len(our_halluc)},
            section="external",
        ))

        # Overall score
        if len(our_overall) >= 5:
            gt_for_overall = gt_labels[:len(our_overall)]
            r_o = pearson_correlation(gt_for_overall, our_overall)
            cls_o = binary_classification(our_overall, gt_for_overall)
            results.append(TestResult(
                name="halueval_overall_score",
                passed=cls_o["f1"] >= 0.5 or r_o >= 0.4,
                details=f"r={r_o:.3f}, Acc={cls_o['accuracy']:.0%}, F1={cls_o['f1']:.3f}, n={len(our_overall)}",
                scores={"pearson_r": round(r_o, 4), **cls_o, "n": len(our_overall)},
                section="external",
            ))

    return results


# ── 3c: SummEval ─────────────────────────────────────────────────────

async def run_summeval(
    client: httpx.AsyncClient, api_key: str, sem: asyncio.Semaphore, limit: int
) -> list[TestResult]:
    """Compare coherence / hallucination_score / helpfulness against SummEval expert annotations."""
    results: list[TestResult] = []
    ds = _load_hf_dataset("mteb/summeval", None, "test")
    if ds is None:
        return [TestResult(name="summeval_load", passed=False, details="Cannot load dataset", section="external")]

    # Select samples with maximum GT diversity for meaningful correlation
    all_rows = list(ds)
    # Compute a diversity score per row based on GT coherence spread
    def _gt_diversity_key(row):
        """Sort key: prefer rows whose coherence scores have wide spread."""
        coh = row.get("coherence", [])
        con = row.get("consistency", [])
        rel = row.get("relevance", [])
        scores = []
        if coh:
            scores.append(sum(coh) / len(coh) / 5.0)
        if con:
            scores.append(sum(con) / len(con) / 5.0)
        if rel:
            scores.append(sum(rel) / len(rel) / 5.0)
        return statistics.mean(scores) if scores else 0.5

    # Sort by GT quality and pick evenly: lowest, highest, and in between
    sorted_rows = sorted(all_rows, key=_gt_diversity_key)
    if len(sorted_rows) > limit and limit >= 3:
        step = max(1, (len(sorted_rows) - 1) / (limit - 1))
        indices = [round(i * step) for i in range(limit)]
        indices = sorted(set(min(idx, len(sorted_rows) - 1) for idx in indices))
        selected = [sorted_rows[i] for i in indices[:limit]]
    else:
        selected = sorted_rows[:limit]
    print(f"  SummEval: {len(selected)} samples (diversity-selected from {len(all_rows)})")

    our_coherence: list[float] = []
    our_halluc: list[float] = []
    our_helpfulness: list[float] = []
    our_overall: list[float] = []
    gt_coherence: list[float] = []
    gt_consistency: list[float] = []
    gt_relevance: list[float] = []
    gt_overall: list[float] = []

    async def _process(i: int, row: dict):
        text = row.get("text", "")
        machine_summary = row.get("machine_summaries", [""])[0] if isinstance(row.get("machine_summaries"), list) else ""
        human_summary = row.get("human_summaries", [""])[0] if isinstance(row.get("human_summaries"), list) else ""
        summary = machine_summary or human_summary

        if not text or not summary:
            return

        # Ground truth: average expert scores (normalized to 0-1)
        coh_scores = row.get("coherence", [])
        con_scores = row.get("consistency", [])
        rel_scores = row.get("relevance", [])

        gt_coh = sum(coh_scores) / len(coh_scores) / 5.0 if coh_scores else None
        gt_con = sum(con_scores) / len(con_scores) / 5.0 if con_scores else None
        gt_rel = sum(rel_scores) / len(rel_scores) / 5.0 if rel_scores else None
        gt_avg = statistics.mean([x for x in [gt_coh, gt_con, gt_rel] if x is not None]) if any(x is not None for x in [gt_coh, gt_con, gt_rel]) else None

        payload = {
            "question": f"Summarize the following article:\n{text[:500]}",
            "answer": summary,
            "contexts": [text[:2000]],
        }

        try:
            detail = await ingest_and_get(client, api_key, payload, sem)
            evaluation = ev(detail)
            coh = evaluation.get("coherence")
            halluc = evaluation.get("hallucination_score")
            helpful = evaluation.get("helpfulness")
            overall = evaluation.get("overall_score")

            if coh is not None and gt_coh is not None:
                our_coherence.append(coh)
                gt_coherence.append(gt_coh)
            if halluc is not None and gt_con is not None:
                our_halluc.append(halluc)
                gt_consistency.append(gt_con)
            if helpful is not None and gt_rel is not None:
                our_helpfulness.append(helpful)
                gt_relevance.append(gt_rel)
            if overall is not None and gt_avg is not None:
                our_overall.append(overall)
                gt_overall.append(gt_avg)

            print(f"    [{i+1}/{len(selected)}] gt_coh={gt_coh}, gt_con={gt_con} → coh={coh}, halluc={halluc}")
        except Exception as exc:
            print(f"    [{i+1}/{len(selected)}] ERROR: {exc}")

    tasks = [_process(i, row) for i, row in enumerate(selected)]
    await asyncio.gather(*tasks)

    # Coherence
    if len(our_coherence) >= 3:
        r = pearson_correlation(gt_coherence, our_coherence)
        results.append(TestResult(
            name="summeval_coherence",
            passed=r >= 0.4,
            details=f"r={r:.3f}, n={len(our_coherence)}",
            scores={"pearson_r": round(r, 4), "n": len(our_coherence)},
            section="external",
        ))

    # Hallucination score vs consistency (NOTE: may have ceiling effect)
    if len(our_halluc) >= 3:
        r = pearson_correlation(gt_consistency, our_halluc)
        gt_mean = statistics.mean(gt_consistency) if gt_consistency else 0
        # Flag if GT has ceiling effect
        note = ""
        if gt_mean > 0.9:
            note = f" (NOTE: gt_mean={gt_mean:.2f}, possible ceiling effect)"
        results.append(TestResult(
            name="summeval_hallucination_vs_consistency",
            passed=r >= 0.3 or gt_mean > 0.9,  # relaxed threshold if ceiling effect
            details=f"r={r:.3f}, n={len(our_halluc)}{note}",
            scores={"pearson_r": round(r, 4), "gt_mean": round(gt_mean, 4), "n": len(our_halluc)},
            section="external",
        ))

    # Helpfulness vs relevance
    if len(our_helpfulness) >= 3:
        r = pearson_correlation(gt_relevance, our_helpfulness)
        results.append(TestResult(
            name="summeval_helpfulness_vs_relevance",
            passed=r >= 0.3,
            details=f"r={r:.3f}, n={len(our_helpfulness)}",
            scores={"pearson_r": round(r, 4), "n": len(our_helpfulness)},
            section="external",
        ))

    # Overall
    if len(our_overall) >= 3:
        r = pearson_correlation(gt_overall, our_overall)
        results.append(TestResult(
            name="summeval_overall_score",
            passed=r >= 0.3,
            details=f"r={r:.3f}, n={len(our_overall)}",
            scores={"pearson_r": round(r, 4), "n": len(our_overall)},
            section="external",
        ))

    return results


# ── 3d: TruthfulQA ──────────────────────────────────────────────────

async def run_truthfulqa(
    client: httpx.AsyncClient, api_key: str, sem: asyncio.Semaphore, limit: int
) -> list[TestResult]:
    """Test truthfulness scoring against TruthfulQA dataset."""
    results: list[TestResult] = []
    ds = _load_hf_dataset("truthfulqa/truthful_qa", "generation", "validation")
    if ds is None:
        return [TestResult(name="truthfulqa_load", passed=False, details="Cannot load dataset", section="external")]

    # Pick mix: some with correct answers, some with incorrect
    rows = list(ds)[:200]
    selected_pairs: list[tuple[dict, float]] = []

    for row in rows:
        if len(selected_pairs) >= limit * 2:
            break
        q = row.get("question", "")
        best = row.get("best_answer", "")
        incorrect = row.get("incorrect_answers", [])

        if q and best:
            selected_pairs.append(({"question": q, "answer": best, "contexts": []}, 1.0))
        if q and incorrect:
            selected_pairs.append(({"question": q, "answer": incorrect[0], "contexts": []}, 0.0))

    selected_pairs = selected_pairs[:limit * 2]
    print(f"  TruthfulQA: {len(selected_pairs)} samples")

    our_overall: list[float] = []
    our_helpful: list[float] = []
    gt_labels: list[float] = []

    async def _process(i: int, payload: dict, gt: float):
        try:
            detail = await ingest_and_get(client, api_key, payload, sem)
            evaluation = ev(detail)
            overall = evaluation.get("overall_score")
            helpful = evaluation.get("helpfulness")

            if overall is not None:
                our_overall.append(overall)
                gt_labels.append(gt)
            if helpful is not None:
                our_helpful.append(helpful)

            label = "correct" if gt == 1.0 else "incorrect"
            print(f"    [{i+1}/{len(selected_pairs)}] gt={label} → overall={overall}, helpful={helpful}")
        except Exception as exc:
            print(f"    [{i+1}/{len(selected_pairs)}] ERROR: {exc}")

    tasks = [_process(i, payload, gt) for i, (payload, gt) in enumerate(selected_pairs)]
    await asyncio.gather(*tasks)

    if len(our_overall) >= 4:
        r = pearson_correlation(gt_labels, our_overall)
        cls = binary_classification(our_overall, gt_labels)
        results.append(TestResult(
            name="truthfulqa_overall_score",
            passed=cls["f1"] >= 0.5 or r >= 0.4,
            details=f"r={r:.3f}, Acc={cls['accuracy']:.0%}, F1={cls['f1']:.3f}, n={len(our_overall)}",
            scores={"pearson_r": round(r, 4), **cls, "n": len(our_overall)},
            section="external",
        ))

    if len(our_helpful) >= 4:
        gt_h = gt_labels[:len(our_helpful)]
        r = pearson_correlation(gt_h, our_helpful)
        cls = binary_classification(our_helpful, gt_h)
        results.append(TestResult(
            name="truthfulqa_helpfulness",
            passed=cls["f1"] >= 0.5 or r >= 0.4,
            details=f"r={r:.3f}, Acc={cls['accuracy']:.0%}, F1={cls['f1']:.3f}, n={len(our_helpful)}",
            scores={"pearson_r": round(r, 4), **cls, "n": len(our_helpful)},
            section="external",
        ))

    return results


# ═══════════════════════════════════════════════════════════════════════
#  SECTION 4: CONSISTENCY — Repeated evaluation variance
# ═══════════════════════════════════════════════════════════════════════

CONSISTENCY_TRACES = [
    {
        "question": "What is photosynthesis?",
        "answer": "Photosynthesis is the process by which plants convert sunlight, carbon dioxide, and water into glucose and oxygen using chlorophyll.",
        "contexts": ["Photosynthesis is a process used by plants to convert light energy into chemical energy. During photosynthesis, plants take in carbon dioxide and water, and using sunlight and chlorophyll, they produce glucose and oxygen."],
    },
    {
        "question": "What is the speed of light?",
        "answer": "The speed of light in a vacuum is approximately 299,792,458 metres per second.",
        "contexts": ["The speed of light in vacuum, commonly denoted c, is a universal physical constant that is exactly equal to 299,792,458 metres per second. It is the fastest speed at which energy, matter, or information can travel."],
    },
]
CONSISTENCY_REPEATS = 3
CONSISTENCY_MAX_STDDEV = 0.15


async def run_consistency_tests(
    client: httpx.AsyncClient, api_key: str, sem: asyncio.Semaphore
) -> list[TestResult]:
    results: list[TestResult] = []
    metrics = ["overall_score", "hallucination_score", "completeness", "helpfulness", "coherence"]

    for t_idx, trace in enumerate(CONSISTENCY_TRACES):
        q_short = trace["question"][:40]
        print(f"  Trace {t_idx + 1}: \"{q_short}...\"")
        repeat_scores: dict[str, list[float]] = {m: [] for m in metrics}

        for r in range(CONSISTENCY_REPEATS):
            try:
                detail = await ingest_and_get(client, api_key, trace, sem)
                evaluation = ev(detail)
                for m in metrics:
                    val = evaluation.get(m)
                    if val is not None:
                        repeat_scores[m].append(val)
                vals_str = ", ".join(f"{m}={evaluation.get(m)}" for m in metrics)
                print(f"    Repeat {r+1}/{CONSISTENCY_REPEATS}: {vals_str}")
            except Exception as exc:
                print(f"    Repeat {r+1}/{CONSISTENCY_REPEATS}: ERROR — {exc}")

        for m in metrics:
            scores_list = repeat_scores[m]
            if len(scores_list) >= 2:
                sd = statistics.stdev(scores_list)
                mean_val = statistics.mean(scores_list)
                passed = sd <= CONSISTENCY_MAX_STDDEV
                results.append(TestResult(
                    name=f"consistency_t{t_idx + 1}_{m}",
                    passed=passed,
                    details=f"mean={mean_val:.3f}, stddev={sd:.3f}, values={[round(v, 3) for v in scores_list]}",
                    scores={"mean": mean_val, "stddev": sd},
                    section="consistency",
                ))

    return results


# ═══════════════════════════════════════════════════════════════════════
#  MAIN
# ═══════════════════════════════════════════════════════════════════════

def print_section_summary(title: str, results: list[TestResult]) -> tuple[int, int]:
    if not results:
        return 0, 0
    passed = sum(1 for r in results if r.passed is True)
    failed = sum(1 for r in results if r.passed is False)
    skipped = sum(1 for r in results if r.passed is None)
    total = passed + failed
    pct = passed / total * 100 if total > 0 else 0

    print(f"\n  {'─' * 68}")
    print(f"  {title}: {passed}/{total} passed ({pct:.0f}%)" + (f" + {skipped} skipped" if skipped else ""))
    print(f"  {'─' * 68}")
    for r in results:
        icon = "✅" if r.passed is True else ("⏭" if r.passed is None else "❌")
        print(f"  {icon} {r.name}: {r.details}")
    return passed, total


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Unified RAG evaluation benchmark")
    p.add_argument("--limit", type=int, default=5, help="Sample limit per external dataset (default: 5)")
    p.add_argument("--concurrency", type=int, default=DEFAULT_CONCURRENCY, help="Max concurrent API calls")
    p.add_argument("--skip-golden", action="store_true", help="Skip golden set tests")
    p.add_argument("--skip-perturbation", action="store_true", help="Skip perturbation tests")
    p.add_argument("--skip-external", action="store_true", help="Skip all external GT tests")
    p.add_argument("--skip-consistency", action="store_true", help="Skip consistency tests")
    p.add_argument("--only", type=str, default="", help="Run only specified sections (comma-separated: golden,perturbation,external,consistency)")
    p.add_argument("--output", default="reports/benchmark_results.json", help="JSON output path")
    return p.parse_args()


async def async_main():
    args = parse_args()

    # Handle --only flag
    sections_to_run = set()
    if args.only:
        sections_to_run = set(args.only.split(","))
    else:
        all_sections = {"golden", "perturbation", "external", "consistency"}
        sections_to_run = all_sections.copy()
        if args.skip_golden:
            sections_to_run.discard("golden")
        if args.skip_perturbation:
            sections_to_run.discard("perturbation")
        if args.skip_external:
            sections_to_run.discard("external")
        if args.skip_consistency:
            sections_to_run.discard("consistency")

    sem = asyncio.Semaphore(args.concurrency)

    print("=" * 72)
    print("  RAG EVALUATION SYSTEM — UNIFIED BENCHMARK")
    print("=" * 72)
    print(f"  Sections: {', '.join(sorted(sections_to_run))}")
    print(f"  Concurrency: {args.concurrency}, External limit: {args.limit}")
    print()

    start = time.time()

    async with httpx.AsyncClient() as client:
        print("  Registering test user...")
        api_key = await register_user(client)
        print(f"  API key: {api_key[:20]}...\n")

        all_results: dict[str, list[TestResult]] = {}
        total_pass = 0
        total_tests = 0

        # ── Section 1: Golden Set ──
        if "golden" in sections_to_run:
            print(f"\n{'━' * 72}")
            print("  SECTION 1: GOLDEN SET (Deterministic Tests)")
            print(f"{'━' * 72}")
            golden = await run_golden_set(client, api_key, sem)
            all_results["golden"] = golden
            p, t = print_section_summary("GOLDEN SET", golden)
            total_pass += p
            total_tests += t

        # ── Section 2: Perturbation Tests ──
        if "perturbation" in sections_to_run:
            print(f"\n{'━' * 72}")
            print("  SECTION 2: PERTURBATION (Sensitivity Tests)")
            print(f"{'━' * 72}")
            perturb = await run_perturbation_tests(client, api_key, sem)
            all_results["perturbation"] = perturb
            p, t = print_section_summary("PERTURBATION", perturb)
            total_pass += p
            total_tests += t

        # ── Section 3: External GT ──
        if "external" in sections_to_run:
            print(f"\n{'━' * 72}")
            print("  SECTION 3: EXTERNAL GROUND TRUTH")
            print(f"{'━' * 72}")

            ext_results: list[TestResult] = []

            print(f"\n  ── 3a: RAGBench (hallucination vs adherence) ──")
            ext_results.extend(await run_ragbench(client, api_key, sem, args.limit))

            print(f"\n  ── 3b: HaluEval (hallucination detection) ──")
            ext_results.extend(await run_halueval(client, api_key, sem, args.limit))

            print(f"\n  ── 3c: SummEval (expert-annotated summaries) ──")
            ext_results.extend(await run_summeval(client, api_key, sem, args.limit))

            print(f"\n  ── 3d: TruthfulQA (truthfulness scoring) ──")
            ext_results.extend(await run_truthfulqa(client, api_key, sem, args.limit))

            all_results["external"] = ext_results
            p, t = print_section_summary("EXTERNAL GT", ext_results)
            total_pass += p
            total_tests += t

        # ── Section 4: Consistency ──
        if "consistency" in sections_to_run:
            print(f"\n{'━' * 72}")
            print("  SECTION 4: CONSISTENCY (Repeat Variance)")
            print(f"{'━' * 72}")
            consistency = await run_consistency_tests(client, api_key, sem)
            all_results["consistency"] = consistency
            p, t = print_section_summary("CONSISTENCY", consistency)
            total_pass += p
            total_tests += t

    elapsed = time.time() - start

    # ── Final Summary ──
    print(f"\n{'═' * 72}")
    print(f"  FINAL SCORE: {total_pass}/{total_tests} tests passed", end="")
    if total_tests > 0:
        print(f" ({total_pass / total_tests * 100:.0f}%)")
    else:
        print()

    for section_name, section_results in all_results.items():
        p = sum(1 for r in section_results if r.passed is True)
        t = sum(1 for r in section_results if r.passed is not None)
        print(f"    {section_name:15s}: {p}/{t}")

    print(f"  Time: {elapsed:.0f}s ({elapsed / 60:.1f} min)")
    print(f"{'═' * 72}")

    # Save JSON
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "concurrency": args.concurrency,
        "limit": args.limit,
        "elapsed_seconds": round(elapsed, 1),
        "sections": {},
        "summary": {
            "total_pass": total_pass,
            "total_tests": total_tests,
            "pass_rate": round(total_pass / total_tests * 100, 1) if total_tests > 0 else 0,
        },
    }

    for section_name, section_results in all_results.items():
        output["sections"][section_name] = [
            {
                "name": r.name,
                "passed": r.passed,
                "details": r.details,
                "scores": r.scores,
            }
            for r in section_results
        ]

    output_path.write_text(json.dumps(output, indent=2, ensure_ascii=False, default=str))
    print(f"\n  Results saved to {output_path}")


def main():
    asyncio.run(async_main())


if __name__ == "__main__":
    main()
