#!/usr/bin/env python3
"""Read-only Telemaco-like REST server for UI development."""

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

PAYLOAD = (Path(__file__).parents[1] / "tests" / "fixtures" / "status.json").read_bytes()


class Handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        if self.path not in {"/api/status", "/api/v1/status", "/rest/status", "/api/device"}:
            self.send_error(404)
            return
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(PAYLOAD)))
        self.end_headers()
        self.wfile.write(PAYLOAD)

    def do_POST(self) -> None:
        length = int(self.headers.get("Content-Length", "0"))
        command = json.loads(self.rfile.read(length) or b"{}")
        body = json.dumps({"ok": True, "received": command}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


if __name__ == "__main__":
    print("Demo Telemaco: http://127.0.0.1:8088/api/status")
    ThreadingHTTPServer(("0.0.0.0", 8088), Handler).serve_forever()
