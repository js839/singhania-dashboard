from __future__ import annotations

from http import HTTPStatus
from http.server import BaseHTTPRequestHandler

from _shared import build_report, cors_headers, read_json, read_session_token, send_json


class handler(BaseHTTPRequestHandler):
    def do_OPTIONS(self):
        self.send_response(HTTPStatus.NO_CONTENT)
        cors_headers(self)
        self.end_headers()

    def do_POST(self):
        try:
            user = read_session_token(self.headers.get("X-Session-Token", ""))
            if not user:
                send_json(self, {"error": "Session expired. Please login again."}, HTTPStatus.UNAUTHORIZED)
                return
            payload = read_json(self)
            report = build_report(
                user,
                payload.get("brand"),
                payload.get("filters") or {},
                payload.get("reportType") or "location",
            )
            send_json(self, report)
        except Exception as exc:
            send_json(self, {"error": str(exc)}, HTTPStatus.INTERNAL_SERVER_ERROR)

