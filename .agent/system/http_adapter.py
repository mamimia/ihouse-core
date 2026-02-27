#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import subprocess
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Dict, Tuple


HOST = os.environ.get("IHOUSE_HTTP_HOST", "127.0.0.1")
PORT_STR = os.environ.get("IHOUSE_HTTP_PORT", "8000")
PORT = int(PORT_STR)

HERE = os.path.dirname(os.path.abspath(__file__))
EVENT_ROUTER_PATH = os.path.join(HERE, "event_router.py")


INDEX_HTML = r"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width,initial-scale=1" />
  <title>iHouse Core</title>
  <style>
    body { font-family: ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, Arial; padding: 24px; }
    .card { max-width: 980px; margin: 0 auto; border: 1px solid #333; border-radius: 10px; padding: 16px; }
    code, pre { background: #111; color: #eee; padding: 10px; border-radius: 8px; display: block; overflow: auto; }
    a { color: #7dd3fc; }
  </style>
</head>
<body>
  <div class="card">
    <h1>iHouse Core is running</h1>
    <p>Try these:</p>
    <pre>GET  /health
POST /event</pre>
    <p>Example curl:</p>
    <pre>curl -s http://127.0.0.1:8000/health

curl -s http://127.0.0.1:8000/event \
  -H "Content-Type: application/json" \
  --data-binary @smoke_events/01_state_transition.json | python3 -m json.tool</pre>
  </div>
</body>
</html>
"""


def _read_body(handler: BaseHTTPRequestHandler) -> bytes:
    length_str = handler.headers.get("Content-Length", "")
    try:
        length = int(length_str)
    except Exception:
        length = 0

    if length <= 0:
        return b""
    return handler.rfile.read(length)


def _run_event_router(stdin_bytes: bytes) -> Tuple[int, bytes, bytes]:
    p = subprocess.Popen(
        ["python3", EVENT_ROUTER_PATH],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    out, err = p.communicate(input=stdin_bytes)
    return p.returncode, out, err


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt: str, *args: Any) -> None:
        return

    def _send_json(self, code: int, obj: Dict[str, Any]) -> None:
        body = json.dumps(obj).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_html(self, code: int, html: str) -> None:
        body = html.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        if self.path == "/" or self.path.startswith("/index"):
            self._send_html(200, INDEX_HTML)
            return

        if self.path == "/health":
            self._send_json(200, {"ok": True, "service": "ihouse-http-adapter"})
            return

        self._send_json(404, {"ok": False, "error": "NOT_FOUND"})

    def do_POST(self) -> None:
        if self.path != "/event":
            self._send_json(404, {"ok": False, "error": "NOT_FOUND"})
            return

        body = _read_body(self)
        if not body:
            self._send_json(400, {"ok": False, "error": "EMPTY_BODY"})
            return

        rc, out, err = _run_event_router(body)

        if rc != 0:
            self._send_json(
                500,
                {
                    "ok": False,
                    "error": "EVENT_ROUTER_EXITED_NONZERO",
                    "stderr": (err or b"")[:2000].decode("utf-8", errors="replace"),
                },
            )
            return

        try:
            parsed = json.loads(out.decode("utf-8", errors="replace"))
        except Exception:
            self._send_json(
                500,
                {
                    "ok": False,
                    "error": "EVENT_ROUTER_OUTPUT_NOT_JSON",
                    "stdout": (out or b"")[:2000].decode("utf-8", errors="replace"),
                    "stderr": (err or b"")[:2000].decode("utf-8", errors="replace"),
                },
            )
            return

        self._send_json(200, parsed)


def main() -> int:
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    print(f"ihouse http adapter listening on http://{HOST}:{PORT}", flush=True)
    server.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
