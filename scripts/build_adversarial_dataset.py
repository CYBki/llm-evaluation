#!/usr/bin/env python3
"""Build a mixed adversarial benchmark dataset from multiple RAG evaluation sources.

Scenarios included:
  A. correct        – Good answer, matching context (should score high)
  B. hallucinated   – Answer contains fabricated facts not in context
  C. partial        – Answer is incomplete / misses key info
  D. contradictory  – Answer directly contradicts context
  E. deflection     – Answer refuses/deflects instead of answering
  F. irrelevant_ctx – Context is unrelated to the question
  G. unanswerable   – Context doesn't contain info to answer

Sources:
  - explodinggradients/amnesty_qa (english_v3)
  - neural-bridge/rag-hallucination-dataset-1000
  - rungalileo/ragbench (hotpotqa)
  - Hand-crafted adversarial examples
"""
from __future__ import annotations

import json
import random
from pathlib import Path

from datasets import load_dataset


def build_adversarial_dataset(output_path: str, target_count: int = 30) -> None:
    samples: list[dict] = []

    # ── A. Correct answers (from Amnesty QA – LLM-generated long answers) ──
    print("Loading Amnesty QA …")
    amnesty = load_dataset("explodinggradients/amnesty_qa", "english_v3", split="eval")
    for row in amnesty.select(range(min(5, len(amnesty)))):
        samples.append({
            "question": row["user_input"],
            "answer": row["response"],
            "contexts": row["retrieved_contexts"],
            "metadata": {
                "source": "amnesty_qa",
                "scenario": "correct",
                "expected_score_range": "0.7-1.0",
                "reference_answer": row["reference"],
            },
        })

    # ── B. Hallucinated / unanswerable (from Neural Bridge Hallucination) ──
    print("Loading Neural Bridge Hallucination …")
    halluc = load_dataset("neural-bridge/rag-hallucination-dataset-1000", split="train")
    # Pick samples where answer says "cannot be answered" or is fabricated
    unanswerable = [r for r in halluc if "cannot be answered" in r["answer"].lower()]
    answerable = [r for r in halluc if "cannot be answered" not in r["answer"].lower()]

    # G. Unanswerable – context doesn't have info
    for row in unanswerable[:3]:
        samples.append({
            "question": row["question"],
            "answer": row["answer"],
            "contexts": [row["context"]],
            "metadata": {
                "source": "neural_bridge_hallucination",
                "scenario": "unanswerable",
                "expected_score_range": "0.0-0.4",
            },
        })

    # A2. Correct from neural bridge (answerable)
    for row in answerable[:3]:
        samples.append({
            "question": row["question"],
            "answer": row["answer"],
            "contexts": [row["context"]],
            "metadata": {
                "source": "neural_bridge_hallucination",
                "scenario": "correct",
                "expected_score_range": "0.6-1.0",
            },
        })

    # ── C/B. RAGBench with adherence scores (has ground truth labels!) ──
    print("Loading RAGBench (hotpotqa) …")
    ragbench = load_dataset("rungalileo/ragbench", "hotpotqa", split="test")

    # Low adherence = hallucinated/unsupported
    sorted_by_adherence = sorted(ragbench, key=lambda x: x.get("adherence_score", 1.0))
    for row in sorted_by_adherence[:4]:
        docs = row.get("documents", [])
        contexts = docs if isinstance(docs, list) else [docs]
        # Flatten if nested
        flat_ctx = []
        for d in contexts:
            if isinstance(d, str):
                flat_ctx.append(d)
            elif isinstance(d, list):
                flat_ctx.extend([str(s) for s in d])
        samples.append({
            "question": row["question"],
            "answer": row["response"],
            "contexts": flat_ctx[:3],
            "metadata": {
                "source": "ragbench_hotpotqa",
                "scenario": "hallucinated",
                "expected_score_range": "0.0-0.4",
                "adherence_score": row.get("adherence_score"),
                "ragas_faithfulness": row.get("ragas_faithfulness"),
            },
        })

    # High adherence = correct
    sorted_desc = sorted(ragbench, key=lambda x: x.get("adherence_score", 0.0), reverse=True)
    for row in sorted_desc[:3]:
        docs = row.get("documents", [])
        contexts = docs if isinstance(docs, list) else [docs]
        flat_ctx = []
        for d in contexts:
            if isinstance(d, str):
                flat_ctx.append(d)
            elif isinstance(d, list):
                flat_ctx.extend([str(s) for s in d])
        samples.append({
            "question": row["question"],
            "answer": row["response"],
            "contexts": flat_ctx[:3],
            "metadata": {
                "source": "ragbench_hotpotqa",
                "scenario": "correct",
                "expected_score_range": "0.7-1.0",
                "adherence_score": row.get("adherence_score"),
                "ragas_faithfulness": row.get("ragas_faithfulness"),
            },
        })

    # ── D. Hand-crafted: Contradictory answers ──
    samples.append({
        "question": "What is the capital of France?",
        "answer": "The capital of France is Berlin. It has been the capital since the 18th century and is known for its beautiful architecture along the Seine river.",
        "contexts": ["Paris is the capital and most populous city of France. It is situated on the River Seine, in northern France. Paris has been one of the major centres of finance, diplomacy and politics since the 17th century."],
        "metadata": {"source": "handcrafted", "scenario": "contradictory", "expected_score_range": "0.0-0.3"},
    })
    samples.append({
        "question": "When did World War II end?",
        "answer": "World War II ended in 1939 when Germany surrendered to the Allied forces after the bombing of Hiroshima.",
        "contexts": ["World War II ended in 1945 with the surrender of Germany in May (V-E Day) and Japan in September (V-J Day) following the atomic bombings of Hiroshima and Nagasaki."],
        "metadata": {"source": "handcrafted", "scenario": "contradictory", "expected_score_range": "0.0-0.3"},
    })

    # ── E. Hand-crafted: Deflection ──
    samples.append({
        "question": "What are the side effects of ibuprofen?",
        "answer": "I'm sorry, but I cannot provide medical advice. Please consult a healthcare professional for information about medication side effects.",
        "contexts": ["Common side effects of ibuprofen include stomach pain, nausea, vomiting, headache, diarrhea, constipation, dizziness, and drowsiness. Serious side effects may include heart attack, stroke, and gastrointestinal bleeding."],
        "metadata": {"source": "handcrafted", "scenario": "deflection", "expected_score_range": "0.0-0.3"},
    })
    samples.append({
        "question": "How does photosynthesis work?",
        "answer": "That's an interesting question! There are many resources available online where you can learn about this topic. I'd recommend checking out a biology textbook.",
        "contexts": ["Photosynthesis is the process by which green plants and other organisms convert light energy into chemical energy. During photosynthesis, chlorophyll absorbs sunlight and uses it to convert carbon dioxide and water into glucose and oxygen. The equation is: 6CO2 + 6H2O + light → C6H12O6 + 6O2."],
        "metadata": {"source": "handcrafted", "scenario": "deflection", "expected_score_range": "0.0-0.3"},
    })

    # ── C. Hand-crafted: Partial answer ──
    samples.append({
        "question": "What are the three branches of the United States government and what does each branch do?",
        "answer": "The United States government has three branches. The legislative branch makes laws.",
        "contexts": ["The United States federal government has three branches: the legislative branch (Congress - makes laws), the executive branch (President - enforces laws), and the judicial branch (Supreme Court - interprets laws). This system of separation of powers was designed by the Founding Fathers to prevent any one branch from gaining too much power."],
        "metadata": {"source": "handcrafted", "scenario": "partial", "expected_score_range": "0.3-0.6"},
    })
    samples.append({
        "question": "Name the planets in our solar system in order from the Sun.",
        "answer": "The planets in order from the Sun are Mercury, Venus, Earth, and Mars.",
        "contexts": ["The eight planets in our solar system in order from the Sun are: Mercury, Venus, Earth, Mars, Jupiter, Saturn, Uranus, and Neptune. Pluto was reclassified as a dwarf planet in 2006 by the International Astronomical Union."],
        "metadata": {"source": "handcrafted", "scenario": "partial", "expected_score_range": "0.3-0.6"},
    })

    # ── F. Hand-crafted: Irrelevant context ──
    samples.append({
        "question": "What programming language was Python inspired by?",
        "answer": "Python was inspired by the ABC programming language. Guido van Rossum created Python while working at Centrum Wiskunde & Informatica.",
        "contexts": ["The Amazon rainforest, also known as Amazonia, covers most of the Amazon basin of South America. This region includes territory belonging to nine nations, with the majority in Brazil. The forest represents over half of the planet's remaining rainforests."],
        "metadata": {"source": "handcrafted", "scenario": "irrelevant_context", "expected_score_range": "0.2-0.5"},
    })

    # ── B. Hand-crafted: Hallucinated facts ──
    samples.append({
        "question": "Who invented the telephone?",
        "answer": "The telephone was invented by Alexander Graham Bell in 1876. He also invented the internet in 1890 and developed the first smartphone prototype in 1895. Bell won three Nobel Prizes for his work in telecommunications.",
        "contexts": ["Alexander Graham Bell was a Scottish-born inventor, scientist, and engineer who is credited with patenting the first practical telephone in 1876. He co-founded the American Telephone and Telegraph Company (AT&T) in 1885."],
        "metadata": {"source": "handcrafted", "scenario": "hallucinated", "expected_score_range": "0.1-0.4"},
    })

    # Shuffle
    random.seed(42)
    random.shuffle(samples)

    # Write JSONL
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8") as f:
        for s in samples:
            f.write(json.dumps(s, ensure_ascii=False) + "\n")

    # Summary
    scenarios = {}
    for s in samples:
        sc = s["metadata"]["scenario"]
        scenarios[sc] = scenarios.get(sc, 0) + 1

    print(f"\nDataset written: {out}")
    print(f"Total samples: {len(samples)}")
    print("Scenarios:")
    for sc, cnt in sorted(scenarios.items()):
        print(f"  {sc}: {cnt}")


if __name__ == "__main__":
    build_adversarial_dataset("data/adversarial_benchmark.jsonl")
