"""
Recipe Manager – desktop launcher
----------------------------------
Starts the Flask server on a free port and opens a native desktop window
via pywebview.  Works as a plain Python script and as a PyInstaller .exe.
"""

import sys
import os
import socket
import threading
import time

# ── Path setup ────────────────────────────────────────────────────────────────
if getattr(sys, "frozen", False):
    BASE_DIR = sys._MEIPASS                          # type: ignore[attr-defined]
    DATA_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    DATA_DIR = BASE_DIR

os.chdir(BASE_DIR)   # So Flask resolves relative paths inside the bundle

# Tell app.py where to store the database & uploads
os.environ["RECIPE_DATA_DIR"] = DATA_DIR

# ── Import the Flask app (after chdir so imports resolve) ────────────────────
import app as flask_app   # noqa: E402


# ── Helpers ───────────────────────────────────────────────────────────────────

def find_free_port(preferred: int = 5000) -> int:
    for port in [preferred] + list(range(5001, 5100)):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(("127.0.0.1", port))
                return port
            except OSError:
                continue
    raise RuntimeError("No free port found in range 5000-5099")


def wait_for_server(port: int, timeout: float = 10.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.2):
                return True
        except OSError:
            time.sleep(0.1)
    return False


def run_server(port: int) -> None:
    flask_app.init_db()
    from werkzeug.serving import make_server
    server = make_server("127.0.0.1", port, flask_app.app)
    server.serve_forever()


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    port = find_free_port()

    # Start Flask in a daemon thread
    t = threading.Thread(target=run_server, args=(port,), daemon=True)
    t.start()

    # Wait until Flask is ready before opening the window
    if not wait_for_server(port):
        print("ERROR: Flask server did not start in time.", file=sys.stderr)
        sys.exit(1)

    import webview  # imported late so pywebview isn't required just to run tests

    window = webview.create_window(
        "Recipe Manager",
        f"http://127.0.0.1:{port}",
        width=1280,
        height=860,
        min_size=(900, 600),
    )
    # gui="edgechromium" gives the best look on Windows; falls back automatically
    try:
        webview.start(gui="edgechromium")
    except Exception:
        webview.start()


if __name__ == "__main__":
    main()
