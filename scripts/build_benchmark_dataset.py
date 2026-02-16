#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Iterable


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build benchmark JSONL in ingest format from public QA datasets."
    )
    parser.add_argument(
        "--source",
        choices=["squad_v2", "hotpot_qa", "both"],
        default="both",
        help="Dataset source to download and transform.",
    )
    parser.add_argument(
        "--split",
        default="validation",
        help="Dataset split name. Use validation/dev style split.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=300,
        help="Maximum number of examples per dataset.",
    )
    parser.add_argument(
        "--output",
        default="data/benchmark_ingest.jsonl",
        help="Output JSONL path.",
    )
    return parser.parse_args()


def ensure_datasets_import():
    try:
        from datasets import load_dataset  # type: ignore
    except Exception as exc:
        raise SystemExit(
            "Missing dependency: datasets. Install with `pip install -r requirements.txt`."
        ) from exc
    return load_dataset


def normalize_squad_v2(records: Iterable[dict], limit: int) -> list[dict]:
    rows: list[dict] = []
    for record in records:
        question = str(record.get("question", "")).strip()
        context = str(record.get("context", "")).strip()
        answers = record.get("answers") or {}
        answer_items = answers.get("text") or []
        answer = str(answer_items[0]).strip() if answer_items else ""

        if not question or not context or not answer:
            continue

        rows.append(
            {
                "question": question,
                "answer": answer,
                "contexts": [context],
                "metadata": {
                    "benchmark_source": "squad_v2",
                    "example_id": record.get("id"),
                },
            }
        )
        if len(rows) >= limit:
            break
    return rows


def normalize_hotpot_qa(records: Iterable[dict], limit: int) -> list[dict]:
    rows: list[dict] = []
    for record in records:
        question = str(record.get("question", "")).strip()
        answer = str(record.get("answer", "")).strip()
        contexts_raw = record.get("context") or []

        contexts: list[str] = []
        if isinstance(contexts_raw, dict):
            titles = contexts_raw.get("title") or []
            sentences_groups = contexts_raw.get("sentences") or []
            for title, sentences in list(zip(titles, sentences_groups))[:3]:
                if not isinstance(sentences, list):
                    continue
                context_text = " ".join(str(sentence).strip() for sentence in sentences if str(sentence).strip())
                if not context_text:
                    continue
                contexts.append(f"{title}: {context_text}")
        else:
            for item in list(contexts_raw)[:3]:
                if not isinstance(item, list) or len(item) != 2:
                    continue
                title, sentences = item
                if not isinstance(sentences, list):
                    continue
                context_text = " ".join(str(sentence).strip() for sentence in sentences if str(sentence).strip())
                if not context_text:
                    continue
                contexts.append(f"{title}: {context_text}")

        if not question or not answer or not contexts:
            continue

        rows.append(
            {
                "question": question,
                "answer": answer,
                "contexts": contexts,
                "metadata": {
                    "benchmark_source": "hotpot_qa",
                    "example_id": record.get("id"),
                    "level": record.get("level"),
                    "type": record.get("type"),
                },
            }
        )
        if len(rows) >= limit:
            break
    return rows


def write_jsonl(rows: list[dict], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as file:
        for row in rows:
            file.write(json.dumps(row, ensure_ascii=False) + "\n")


def main() -> None:
    args = parse_args()
    load_dataset = ensure_datasets_import()

    all_rows: list[dict] = []

    if args.source in {"squad_v2", "both"}:
        squad = load_dataset("squad_v2", split=args.split)
        all_rows.extend(normalize_squad_v2(squad, args.limit))

    if args.source in {"hotpot_qa", "both"}:
        hotpot_split = args.split
        if hotpot_split == "validation":
            hotpot_split = "validation"
        hotpot = load_dataset("hotpot_qa", "distractor", split=hotpot_split)
        all_rows.extend(normalize_hotpot_qa(hotpot, args.limit))

    output_path = Path(args.output)
    write_jsonl(all_rows, output_path)

    print(f"Wrote {len(all_rows)} benchmark rows to {output_path}")


if __name__ == "__main__":
    main()
