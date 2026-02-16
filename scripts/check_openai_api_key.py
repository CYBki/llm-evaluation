from __future__ import annotations

import argparse
import os
import sys

import httpx


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate OPENAI_API_KEY against OpenAI API")
    parser.add_argument(
        "--api-key",
        default=os.getenv("OPENAI_API_KEY"),
        help="OpenAI API key. If omitted, reads OPENAI_API_KEY env var.",
    )
    parser.add_argument("--base-url", default=os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1"))
    parser.add_argument("--timeout", type=float, default=20.0)
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    if not args.api_key:
        print("ERROR: OPENAI_API_KEY missing. Pass --api-key or set OPENAI_API_KEY.")
        return 2

    url = f"{args.base_url.rstrip('/')}/models"
    headers = {"Authorization": f"Bearer {args.api_key}"}

    try:
        with httpx.Client(timeout=args.timeout) as client:
            resp = client.get(url, headers=headers)
    except httpx.HTTPError as exc:
        print(f"ERROR: Request failed: {exc}")
        return 3

    print(f"status={resp.status_code}")

    if resp.status_code == 200:
        data = resp.json()
        count = len(data.get("data", [])) if isinstance(data, dict) else 0
        print(f"OK: OPENAI_API_KEY is valid. models_count={count}")
        return 0

    print("FAIL: OPENAI_API_KEY validation failed")
    try:
        print("Response:", resp.json())
    except Exception:
        print("Response:", resp.text)
    return 1


if __name__ == "__main__":
    sys.exit(main())
