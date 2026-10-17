"""In-memory room storage and player matchmaking operations."""

import secrets
import string
import threading

try:
    from server.config import MAX_PLAYERS, ROOM_ID_LENGTH
except ImportError:
    from config import MAX_PLAYERS, ROOM_ID_LENGTH

ROOM_ID_CHARS = string.ascii_uppercase + string.digits

# In-memory store: { room_id: {"players": [{"name": ..., "token": ...}]} }
rooms = {}
rooms_lock = threading.Lock()


def _generate_room_id():
    return "".join(secrets.choice(ROOM_ID_CHARS) for _ in range(ROOM_ID_LENGTH))


def _generate_token():
    return secrets.token_hex(8)


def create_room(player_name):
    """Creates a new room with player_name as the first player.

    Returns:
        tuple[str, str]: (room_id, token)
    """
    token = _generate_token()
    with rooms_lock:
        room_id = _generate_room_id()
        while room_id in rooms:  # astronomically unlikely, cheap to guard
            room_id = _generate_room_id()
        rooms[room_id] = {
            "players": [{"name": player_name, "token": token}]
        }
    return room_id, token


def join_room(room_id, player_name):
    """Joins an existing room if it has space.

    Returns:
        tuple[str | None, str | None]: (token, None) on success, or (None, error_code) on failure.
    """
    token = _generate_token()
    with rooms_lock:
        room = rooms.get(room_id)
        if room is None:
            return None, "ROOM_NOT_FOUND"
        if len(room["players"]) >= MAX_PLAYERS:
            return None, "ROOM_FULL"
        room["players"].append({"name": player_name, "token": token})
    return token, None


def get_room(room_id, player_token):
    """Fetches room status for a player holding player_token.

    Returns:
        tuple[dict | None, str | None]: (room_data, None) on success, or (None, error_code) on failure.
    """
    with rooms_lock:
        room = rooms.get(room_id)
        if room is None:
            return None, "ROOM_NOT_FOUND"
        players = list(room["players"])  # snapshot while holding the lock

    me = next((p for p in players if p["token"] == player_token), None)
    if me is None:
        return None, "INVALID_TOKEN"

    opponent = next((p["name"] for p in players if p["token"] != player_token), None)
    status = "full" if len(players) >= MAX_PLAYERS else "waiting"

    return {"you": me["name"], "opponent": opponent, "status": status}, None

