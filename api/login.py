from __future__ import annotations

from http import HTTPStatus
from http.server import BaseHTTPRequestHandler

from _shared import authenticate, cors_headers, make_session_token, read_json, send_json


class handler(BaseHTTPRequestHandler):
    def do_OPTIONS(self):
        self.send_response(HTTPStatus.NO_CONTENT)
        cors_headers(self)
        self.end_headers()

    def do_POST(self):
        try:
            payload = read_json(self)
            user = authenticate(payload.get("email"), payload.get("password"))
            if not user:
                send_json(self, {"error": "Invalid user id or password"}, HTTPStatus.UNAUTHORIZED)
                return
            token = make_session_token(user)
            send_json(self, {"token": token, "user": {key: user[key] for key in ("email", "name", "brands", "locations")}})
        except Exception as exc:
            send_json(self, {"error": str(exc)}, HTTPStatus.INTERNAL_SERVER_ERROR)

