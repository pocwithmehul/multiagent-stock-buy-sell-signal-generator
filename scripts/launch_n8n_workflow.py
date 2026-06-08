#!/usr/bin/env python3
"""Launch and manage n8n workflows through the n8n REST API."""

import argparse
import json
import os
import sys
from typing import Any

import requests


class N8NClient:
    """Small client for n8n workflow actions with endpoint fallbacks."""

    def __init__(self, base_url: str, api_key: str, timeout: int = 30):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.headers = {
            "X-N8N-API-KEY": api_key,
            "Content-Type": "application/json",
        }

    def _request_with_fallbacks(self, method: str, paths: list[str], json_body: dict | None = None) -> dict[str, Any]:
        last_error = None
        for path in paths:
            url = f"{self.base_url}{path}"
            try:
                response = requests.request(
                    method=method,
                    url=url,
                    headers=self.headers,
                    json=json_body,
                    timeout=self.timeout,
                )
                if response.status_code in (404, 405):
                    last_error = f"{response.status_code} at {url}"
                    continue
                response.raise_for_status()
                if not response.text:
                    return {}
                return response.json()
            except requests.RequestException as exc:
                last_error = f"{url}: {exc}"
                continue
        raise RuntimeError(f"All endpoint attempts failed. Last error: {last_error}")

    def run_workflow(self, workflow_id: str) -> dict[str, Any]:
        return self._request_with_fallbacks(
            "POST",
            [
                f"/api/v1/workflows/{workflow_id}/run",
                f"/rest/workflows/{workflow_id}/run",
            ],
            json_body={},
        )

    def activate_workflow(self, workflow_id: str) -> dict[str, Any]:
        return self._request_with_fallbacks(
            "POST",
            [
                f"/api/v1/workflows/{workflow_id}/activate",
                f"/rest/workflows/{workflow_id}/activate",
            ],
            json_body={},
        )

    def deactivate_workflow(self, workflow_id: str) -> dict[str, Any]:
        return self._request_with_fallbacks(
            "POST",
            [
                f"/api/v1/workflows/{workflow_id}/deactivate",
                f"/rest/workflows/{workflow_id}/deactivate",
            ],
            json_body={},
        )

    def get_workflow(self, workflow_id: str) -> dict[str, Any]:
        return self._request_with_fallbacks(
            "GET",
            [
                f"/api/v1/workflows/{workflow_id}",
                f"/rest/workflows/{workflow_id}",
            ],
        )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Launch/manage an n8n workflow from CLI.")
    parser.add_argument("--workflow-id", required=True, help="n8n workflow ID")
    parser.add_argument(
        "--action",
        required=True,
        choices=["run", "activate", "deactivate", "status"],
        help="Action to perform",
    )
    parser.add_argument("--base-url", default=os.getenv("N8N_BASE_URL", "http://localhost:5678"))
    parser.add_argument("--api-key", default=os.getenv("N8N_API_KEY"))
    parser.add_argument("--timeout", type=int, default=30)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not args.api_key:
        print("Missing n8n API key. Set N8N_API_KEY or pass --api-key.", file=sys.stderr)
        return 2

    client = N8NClient(
        base_url=args.base_url,
        api_key=args.api_key,
        timeout=args.timeout,
    )

    try:
        if args.action == "run":
            result = client.run_workflow(args.workflow_id)
        elif args.action == "activate":
            result = client.activate_workflow(args.workflow_id)
        elif args.action == "deactivate":
            result = client.deactivate_workflow(args.workflow_id)
        else:
            result = client.get_workflow(args.workflow_id)

        print(json.dumps(result, indent=2, default=str))
        return 0
    except Exception as exc:
        print(f"n8n action failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
