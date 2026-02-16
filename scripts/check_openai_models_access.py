from __future__ import annotations

import argparse
import os
import sys
from typing import Any

import httpx


DEFAULT_MODELS = ["gpt-5.2", "gpt-5-mini"]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Live check model access with OPENAI_API_KEY")
    parser.add_argument(
        "--api-key",
        default=os.getenv("OPENAI_API_KEY"),
        help="OpenAI API key. Defaults to OPENAI_API_KEY env var.",
    )
    parser.add_argument("--base-url", default=os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1"))
    parser.add_argument("--timeout", type=float, default=30.0)
    parser.add_argument("--models", nargs="*", default=DEFAULT_MODELS)
    return parser.parse_args()


def call_model(client: httpx.Client, base_url: str, model: str) -> tuple[bool, int, str]:
    url = f"{base_url.rstrip('/')}/chat/completions"
    payload: dict[str, Any] = {
        "model": model,
        "messages": [
            {"role": "system", "content": "You are a health check assistant."},
            {"role": "user", "content": "Reply with exactly: OK"},
        ],
        "max_completion_tokens": 20,
    }

    resp = client.post(url, json=payload)
    if resp.status_code != 200:
        try:
            detail = str(resp.json())
        except Exception:
            detail = resp.text
        return False, resp.status_code, detail

    try:
        content = resp.json()["choices"][0]["message"]["content"]
    except Exception:
        return False, resp.status_code, "Invalid success response format"

    return True, resp.status_code, content.strip()


def main() -> int:
    args = parse_args()
    if not args.api_key:
        print("ERROR: OPENAI_API_KEY missing. Set env var or pass --api-key.")
        return 2

    headers = {
        "Authorization": f"Bearer {args.api_key}",
        "Content-Type": "application/json",
    }

    failed = False
    with httpx.Client(timeout=args.timeout, headers=headers) as client:
        for model in args.models:
            ok, status, detail = call_model(client, args.base_url, model)
            if ok:
                print(f"[OK] {model} status={status} reply={detail}")
            else:
                failed = True
                print(f"[FAIL] {model} status={status} detail={detail}")

    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
