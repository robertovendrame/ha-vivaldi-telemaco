#!/usr/bin/env python3
"""Safely probe read-only Telemaco REST endpoints and save sanitized responses."""

import json
import re
import urllib.error
import urllib.request
from argparse import ArgumentParser
from pathlib import Path

ENDPOINTS = (
    "/openapi.json",
    "/swagger.json",
    "/v3/api-docs",
    "/api/device/status",
    "/api/metadata/get",
    "/api/presets/get",
    "/api/input/get",
    "/api/matrix/get",
    "/api/output/get",
    "/api/hostnames/get",
    "/api/status/get",
    "/api/api/status",
)
SENSITIVE_KEYS = re.compile(
    r"(token|password|passwd|authorization|secret|mac|email)", re.IGNORECASE
)


def redact(value):
    if isinstance(value, dict):
        return {
            key: ("**REDACTED**" if SENSITIVE_KEYS.search(str(key)) else redact(item))
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [redact(item) for item in value]
    return value


def main() -> None:
    parser = ArgumentParser()
    parser.add_argument("host", help="Telemaco IP address or hostname")
    parser.add_argument("--port", type=int, default=80)
    parser.add_argument("--token", default="")
    parser.add_argument("--output", type=Path, default=Path("telemaco_rest_capture.json"))
    args = parser.parse_args()
    headers = {"Accept": "application/json"}
    if args.token:
        headers.update({"Authorization": f"Bearer {args.token}", "X-Auth-Token": args.token})

    results = {}
    for endpoint in ENDPOINTS:
        request = urllib.request.Request(
            f"http://{args.host}:{args.port}{endpoint}", headers=headers
        )
        try:
            with urllib.request.urlopen(request, timeout=5) as response:
                results[endpoint] = {
                    "status": response.status,
                    "payload": redact(json.load(response)),
                }
        except urllib.error.HTTPError as err:
            results[endpoint] = {"status": err.code}
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as err:
            results[endpoint] = {"error": type(err).__name__}

    args.output.write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(f"Saved sanitized capture to {args.output}")


if __name__ == "__main__":
    main()
