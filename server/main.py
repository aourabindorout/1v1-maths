"""Entry point for the 1v1 Maths room manager server."""

from http.server import ThreadingHTTPServer

try:
    from server.config import HOST, PORT
    from server.handler import RoomRequestHandler
except ImportError:
    from config import HOST, PORT
    from handler import RoomRequestHandler


def run_server():
    server = ThreadingHTTPServer((HOST, PORT), RoomRequestHandler)
    print(f"Room manager listening on http://{HOST}:{PORT} (Ctrl+C to stop)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down.")
        server.shutdown()


if __name__ == "__main__":
    run_server()