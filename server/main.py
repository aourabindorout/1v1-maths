"""
Pure-Python room manager backend -- standard library only, no frameworks.

Endpoints:
    POST /rooms                  {"name": "Alice"}      -> create a room
    POST /rooms/<room_id>/join   {"name": "Bob"}         -> join a room
    GET  /rooms/<room_id>        header: X-Player-Token  -> read room state

Run:
    python3 server.py
Then hit http://127.0.0.1:8000 with curl / Postman (see the curl examples
from earlier in the conversation -- the request/response shapes match).
"""

import json
import re
import secrets
import string
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HOST = "127.0.0.1"
PORT = 8000
MAX_PLAYERS = 2

# ---------------------------------------------------------------------------
# In-memory state. This is the ENTIRE database: one dict, one lock.
#
# rooms = {
#     "AB12CD": {
#         "players": [
#             {"name": "Alice", "token": "..."},
#             {"name": "Bob",   "token": "..."},
#         ]
#     }
# }
# ---------------------------------------------------------------------------
rooms = {}
rooms_lock = threading.Lock()

ROOM_ID_CHARS = string.ascii_uppercase + string.digits
ROOM_PATH = re.compile(r"^/rooms/([A-Za-z0-9]+)$")
JOIN_PATH = re.compile(r"^/rooms/([A-Za-z0-9]+)/join$")


def new_room_id(length=6):
    return "".join(secrets.choice(ROOM_ID_CHARS) for _ in range(length))


def new_token():
    return secrets.token_hex(8)


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        print("[%s] %s" % (self.address_string(), fmt % args))

    # -- helpers --------------------------------------------------------
    def _send_json(self, status, payload):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        # Harmless now; saves a headache once a frontend page polls this
        # from a different port/origin during local testing.
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def _read_json_body(self):
        length = int(self.headers.get("Content-Length", 0))
        if length == 0:
            return {}
        return json.loads(self.rfile.read(length))

    # -- routing ----------------------------------------------------------
    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, X-Player-Token")
        self.end_headers()

    def do_GET(self):
        match = ROOM_PATH.match(self.path)
        if match:
            return self._get_room(match.group(1))
        if self.path == "/":
            return self._send_json(200, {"status": "ok", "service": "room-manager"})
        self._send_json(404, {"error": "NOT_FOUND"})

    def do_POST(self):
        if self.path == "/rooms":
            return self._create_room()
        match = JOIN_PATH.match(self.path)
        if match:
            return self._join_room(match.group(1))
        self._send_json(404, {"error": "NOT_FOUND"})

    # -- handlers -----------------------------------------------------
    def _create_room(self):
        try:
            name = self._read_json_body()["name"].strip()
        except (json.JSONDecodeError, KeyError, AttributeError):
            return self._send_json(400, {"error": "NAME_REQUIRED"})
        if not name:
            return self._send_json(400, {"error": "NAME_REQUIRED"})

        token = new_token()
        with rooms_lock:
            room_id = new_room_id()
            while room_id in rooms:  # astronomically unlikely, cheap to guard
                room_id = new_room_id()
            rooms[room_id] = {"players": [{"name": name, "token": token}]}

        self._send_json(201, {"room_id": room_id, "token": token})

    def _join_room(self, room_id):
        try:
            name = self._read_json_body()["name"].strip()
        except (json.JSONDecodeError, KeyError, AttributeError):
            return self._send_json(400, {"error": "NAME_REQUIRED"})
        if not name:
            return self._send_json(400, {"error": "NAME_REQUIRED"})

        token = new_token()
        # Everything inside this lock is the atomic "check-then-append" --
        # this is what stops two simultaneous joiners both getting admitted.
        with rooms_lock:
            room = rooms.get(room_id)
            if room is None:
                return self._send_json(404, {"error": "ROOM_NOT_FOUND"})
            if len(room["players"]) >= MAX_PLAYERS:
                return self._send_json(409, {"error": "ROOM_FULL"})
            room["players"].append({"name": name, "token": token})

        self._send_json(200, {"token": token})

    def _get_room(self, room_id):
        player_token = self.headers.get("X-Player-Token", "")
        with rooms_lock:
            room = rooms.get(room_id)
            if room is None:
                return self._send_json(404, {"error": "ROOM_NOT_FOUND"})
            players = list(room["players"])  # snapshot while still holding the lock

        me = next((p for p in players if p["token"] == player_token), None)
        if me is None:
            return self._send_json(403, {"error": "INVALID_TOKEN"})

        opponent = next((p["name"] for p in players if p["token"] != player_token), None)
        status = "full" if len(players) >= MAX_PLAYERS else "waiting"
        self._send_json(200, {"you": me["name"], "opponent": opponent, "status": status})


if __name__ == "__main__":
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    print(f"Room manager listening on http://{HOST}:{PORT}  (Ctrl+C to stop)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down.")
        server.shutdown()