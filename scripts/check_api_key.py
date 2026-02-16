from __future__ import annotations

import argparse
import os
import sys

import httpx


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Check if X-API-Key works against /api/v1/traces endpoint")
    parser.add_argument("--base-url", default=os.getenv("BASE_URL", "http://localhost:8000"), help="API base URL")
    parser.add_argument(
        "--api-key",
        default=os.getenv("RAGEVAL_API_KEY"),
        help="API key value. If omitted, reads RAGEVAL_API_KEY env var.",
    )
    parser.add_argument("--timeout", type=float, default=20.0, help="HTTP timeout in seconds")
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    if not args.api_key:
        print("ERROR: API key missing. Pass --api-key or set RAGEVAL_API_KEY.")
        return 2

    traces_url = f"{args.base_url.rstrip('/')}/api/v1/traces?page=1&per_page=1"

    try:
        with httpx.Client(timeout=args.timeout) as client:
            no_key_resp = client.get(traces_url)
            with_key_resp = client.get(traces_url, headers={"X-API-Key": args.api_key})
    except httpx.HTTPError as exc:
        print(f"ERROR: Request failed: {exc}")
        return 3

    print(f"[No Key]   status={no_key_resp.status_code}")
    print(f"[With Key] status={with_key_resp.status_code}")

    if no_key_resp.status_code != 401:
        print("WARN: No-key request did not return 401. Check middleware/auth config.")

    if with_key_resp.status_code == 200:
        print("OK: API key is valid and working.")
        return 0

    print("FAIL: API key check failed.")
    try:
        print("Response body:", with_key_resp.json())
    except Exception:
        print("Response body:", with_key_resp.text)
    return 1


if __name__ == "__main__":
    sys.exit(main())
