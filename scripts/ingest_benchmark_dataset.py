#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import httpx


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Ingest benchmark JSONL and collect evaluation statuses.")
    parser.add_argument("--input", default="data/benchmark_ingest.jsonl", help="Input JSONL file path.")
    parser.add_argument("--base-url", default="http://localhost:8000", help="API base URL.")
    parser.add_argument("--api-key", required=True, help="RAG Eval API key (X-API-Key).")
    parser.add_argument("--limit", type=int, default=100, help="Max rows to ingest.")
    parser.add_argument("--poll-seconds", type=int, default=120, help="Polling timeout per trace.")
    parser.add_argument(
        "--results-output",
        default="",
        help="Optional JSON output path for detailed per-trace results and summary.",
    )
    return parser.parse_args()


def iter_jsonl(path: Path):
    with path.open("r", encoding="utf-8") as file:
        for line in file:
            line = line.strip()
            if not line:
                continue
            yield json.loads(line)


def poll_until_terminal(client: httpx.Client, base_url: str, api_key: str, trace_id: str, timeout_seconds: int) -> str:
    deadline = time.time() + timeout_seconds
    headers = {"X-API-Key": api_key}
    while time.time() < deadline:
        response = client.get(f"{base_url}/api/v1/traces/{trace_id}", headers=headers, timeout=30)
        response.raise_for_status()
        status = response.json().get("status", "unknown")
        if status in {"completed", "failed"}:
            return status
        time.sleep(2)
    return "timeout"


def fetch_trace_detail(client: httpx.Client, base_url: str, api_key: str, trace_id: str) -> dict:
    response = client.get(
        f"{base_url}/api/v1/traces/{trace_id}",
        headers={"X-API-Key": api_key},
        timeout=30,
    )
    response.raise_for_status()
    return response.json()


def main() -> None:
    args = parse_args()
    path = Path(args.input)
    if not path.exists():
        raise SystemExit(f"Input not found: {path}")

    completed = 0
    failed = 0
    timeout = 0
    sent = 0
    results: list[dict] = []

    headers = {"Content-Type": "application/json", "X-API-Key": args.api_key}

    with httpx.Client() as client:
        for payload in iter_jsonl(path):
            response = client.post(
                f"{args.base_url}/api/v1/ingest",
                headers=headers,
                json=payload,
                timeout=300,
            )
            response.raise_for_status()
            data = response.json()
            trace_id = str(data["id"])
            status = str(data.get("status", "pending"))

            if status not in {"completed", "failed"}:
                status = poll_until_terminal(client, args.base_url, args.api_key, trace_id, args.poll_seconds)

            if status == "completed":
                completed += 1
            elif status == "failed":
                failed += 1
            else:
                timeout += 1

            sent += 1

            detail: dict | None = None
            if status in {"completed", "failed"}:
                detail = fetch_trace_detail(client, args.base_url, args.api_key, trace_id)

            results.append(
                {
                    "trace_id": trace_id,
                    "status": status,
                    "question": payload.get("question"),
                    "metadata": payload.get("metadata"),
                    "evaluation": (detail or {}).get("evaluation"),
                }
            )

            if sent >= args.limit:
                break

    if args.results_output:
        output_path = Path(args.results_output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_payload = {
            "summary": {
                "sent": sent,
                "completed": completed,
                "failed": failed,
                "timeout": timeout,
            },
            "results": results,
        }
        output_path.write_text(json.dumps(output_payload, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"results_output={output_path}")

    print("Benchmark ingest summary")
    print(f"sent={sent}")
    print(f"completed={completed}")
    print(f"failed={failed}")
    print(f"timeout={timeout}")


if __name__ == "__main__":
    main()
