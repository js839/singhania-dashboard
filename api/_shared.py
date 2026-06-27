from __future__ import annotations

import json
import sys
from http import HTTPStatus
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from server import authenticate, build_report, make_session_token, read_session_token  # noqa: E402


def cors_headers(handler):
    handler.send_header("Access-Control-Allow-Origin", "*")
    handler.send_header("Access-Control-Allow-Headers", "Content-Type, X-Session-Token")
    handler.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")


def send_json(handler, payload, status=HTTPStatus.OK):
    data = json.dumps(payload, default=str).encode("utf-8")
    handler.send_response(status)
    cors_headers(handler)
    handler.send_header("Content-Type", "application/json")
    handler.send_header("Content-Length", str(len(data)))
    handler.end_headers()
    handler.wfile.write(data)


def read_json(handler):
    size = int(handler.headers.get("Content-Length", "0"))
    if not size:
        return {}
    return json.loads(handler.rfile.read(size).decode("utf-8"))

