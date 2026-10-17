"""HTTP request handler for the room management API."""

import json
import re
from http.server import BaseHTTPRequestHandler

try:
    from server import rooms
except ImportError:
    import rooms

ROOM_PATH = re.compile(r"^/rooms/([A-Za-z0-9]+)$")
JOIN_PATH = re.compile(r"^/rooms/([A-Za-z0-9]+)/join$")


class RoomRequestHandler(BaseHTTPRequestHandler):
    """Handles HTTP requests for creating, joining, and inspecting game rooms."""

    def log_message(self, fmt, *args):
        print("[%s] %s" % (self.address_string(), fmt % args))

    # -- JSON Helpers ---------------------------------------------------
    def _send_json(self, status, payload):
        body = (json.dumps(payload) + "\n").encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        # CORS header allows future web frontend pages to talk to the server
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def _read_json_body(self):
        length = int(self.headers.get("Content-Length", 0))
        if length == 0:
            return {}
        return json.loads(self.rfile.read(length))

    # -- Routing --------------------------------------------------------
    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, X-Player-Token")
        self.end_headers()

    def do_GET(self):
        if self.path == "/":
            return self._send_json(200, {"status": "ok", "service": "room-manager"})

        match = ROOM_PATH.match(self.path)
        if match:
            return self._handle_get_room(match.group(1))

        self._send_json(404, {"error": "NOT_FOUND"})

    def do_POST(self):
        if self.path == "/rooms":
            return self._handle_create_room()

        match = JOIN_PATH.match(self.path)
        if match:
            return self._handle_join_room(match.group(1))

        self._send_json(404, {"error": "NOT_FOUND"})

    # -- Endpoint Handlers ----------------------------------------------
    def _handle_create_room(self):
        try:
            name = self._read_json_body()["name"].strip()
        except (json.JSONDecodeError, KeyError, AttributeError):
            return self._send_json(400, {"error": "NAME_REQUIRED"})

        if not name:
            return self._send_json(400, {"error": "NAME_REQUIRED"})

        room_id, token = rooms.create_room(name)
        self._send_json(201, {"room_id": room_id, "token": token})

    def _handle_join_room(self, room_id):
        try:
            name = self._read_json_body()["name"].strip()
        except (json.JSONDecodeError, KeyError, AttributeError):
            return self._send_json(400, {"error": "NAME_REQUIRED"})

        if not name:
            return self._send_json(400, {"error": "NAME_REQUIRED"})

        token, error = rooms.join_room(room_id, name)
        if error == "ROOM_NOT_FOUND":
            return self._send_json(404, {"error": "ROOM_NOT_FOUND"})
        if error == "ROOM_FULL":
            return self._send_json(409, {"error": "ROOM_FULL"})

        self._send_json(200, {"token": token})

    def _handle_get_room(self, room_id):
        player_token = self.headers.get("X-Player-Token", "")
        data, error = rooms.get_room(room_id, player_token)

        if error == "ROOM_NOT_FOUND":
            return self._send_json(404, {"error": "ROOM_NOT_FOUND"})
        if error == "INVALID_TOKEN":
            return self._send_json(403, {"error": "INVALID_TOKEN"})

        self._send_json(200, data)

