"""
Web dashboards, served from the bot process.

    /                 DC / MLA view (whole taluk)
    /citizen?t=...    one citizen's complaints
    /officer?t=...    one officer's queue and score; senior posts also see their team
    /demo             role switcher, only from the laptop itself (for the stage demo)

Citizens and officers get their personal link from the bot with /mydashboard.
A link carries a signed token, so one person cannot open another person's page.

Standard-library HTTP server in a background thread, so there is nothing
extra to install. Actions that must message people on Telegram (routing a
triage case, moving the demo clock) are handed to hooks that bot.py registers.
"""
import hashlib
import hmac
import json
import os
import secrets
import socket
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, quote, urlparse

import requests
from dotenv import load_dotenv

load_dotenv()

import cases  # noqa: E402
import database as db  # noqa: E402
from messages import STATUS_LABEL  # noqa: E402
from officer_directory import ALL_POSTS, get_senior_post  # noqa: E402

HOOKS = {"route": None, "tick": None}
HERE = Path(__file__).parent
PORT = int(os.environ.get("DASHBOARD_PORT", 8000))
_media_cache = {}


# ---------- links and tokens ----------

def lan_ip():
    """The laptop's address on the local network, so phones on the same Wi-Fi can open links."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))  # no packet is sent; this only picks the outgoing interface
            return s.getsockname()[0]
    except OSError:
        return "localhost"


def ngrok_url():
    """The public https address of a running ngrok tunnel (ngrok's local API), or None."""
    try:
        tunnels = requests.get("http://127.0.0.1:4040/api/tunnels", timeout=0.5).json()["tunnels"]
        return next((t["public_url"] for t in tunnels if t["public_url"].startswith("https://")), None)
    except Exception:
        return None


CLOUDFLARED_METRICS = "127.0.0.1:4041"  # start cloudflared with: --metrics 127.0.0.1:4041


def cloudflared_url():
    """The public address of a running cloudflared quick tunnel, or None."""
    try:
        host = requests.get(f"http://{CLOUDFLARED_METRICS}/quicktunnel", timeout=0.5).json().get("hostname")
        return f"https://{host}" if host else None
    except Exception:
        return None


def base_url():
    """Where links point: DASHBOARD_URL if set, else a running tunnel, else this laptop's Wi-Fi IP."""
    return (os.environ.get("DASHBOARD_URL") or cloudflared_url() or ngrok_url()
            or f"http://{lan_ip()}:{PORT}")


def _secret():
    value = db.get_setting("link_secret")
    if not value:
        value = secrets.token_hex(16)
        db.set_setting("link_secret", value)
    return value.encode()


def make_token(role, chat_id):
    body = f"{role}.{chat_id}"
    sig = hmac.new(_secret(), body.encode(), hashlib.sha256).hexdigest()[:20]
    return f"{body}.{sig}"


def read_token(token, role):
    """Return the chat_id in a valid token for this role, else None."""
    try:
        r, chat_id, sig = (token or "").split(".")
    except ValueError:
        return None
    if r != role or not hmac.compare_digest(sig, make_token(r, chat_id).split(".")[2]):
        return None
    return int(chat_id)


def citizen_link(chat_id):
    return f"{base_url()}/citizen?t={make_token('c', chat_id)}"


def officer_link(chat_id, post=None):
    url = f"{base_url()}/officer?t={make_token('o', chat_id)}"
    return url + (f"&post={quote(post)}" if post else "")


# ---------- media proxy (Telegram file_id -> bytes) ----------

def fetch_telegram_file(file_id):
    if file_id in _media_cache:
        return _media_cache[file_id]
    token = os.environ["TELEGRAM_BOT_TOKEN"]
    info = requests.get(f"https://api.telegram.org/bot{token}/getFile",
                        params={"file_id": file_id}, timeout=15).json()
    path = info["result"]["file_path"]
    data = requests.get(f"https://api.telegram.org/file/bot{token}/{path}", timeout=30).content
    kind = "audio/ogg" if path.endswith((".oga", ".ogg")) else "image/jpeg"
    if len(_media_cache) > 100:
        _media_cache.clear()
    _media_cache[file_id] = (data, kind)
    return data, kind


def can_see_case(query, case):
    citizen = read_token(query.get("t"), "c")
    if citizen is not None:
        return case["citizen_chat_id"] == citizen
    officer = read_token(query.get("t"), "o")
    if officer is not None:
        held = set(cases.posts_held_by(officer))
        return any(e["officer_post"] in held or e["from_post"] in held
                   for e in db.get_events(case["tracking_id"]))
    return False


# ---------- HTTP ----------

class Handler(BaseHTTPRequestHandler):
    def _send(self, code, body, content_type="application/json"):
        data = body if isinstance(body, bytes) else body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", content_type + ("; charset=utf-8" if "text" in content_type
                                                          or "json" in content_type else ""))
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _json(self, obj, code=200):
        self._send(code, json.dumps(obj))

    def _page(self, name):
        self._send(200, (HERE / name).read_bytes(), "text/html")

    def _is_local(self):
        """The laptop running the bot, or a trusted team laptop listed in DEMO_ALLOWED_IPS."""
        # A tunnel (cloudflared, ngrok) connects from localhost too, but adds forwarding headers.
        forwarded = any(self.headers.get(h) for h in ("X-Forwarded-For", "Cf-Connecting-Ip", "Forwarded"))
        trusted = {"127.0.0.1", "::1"} | {ip.strip() for ip in os.environ.get("DEMO_ALLOWED_IPS", "").split(",")
                                          if ip.strip()}
        return self.client_address[0] in trusted and not forwarded

    def do_GET(self):
        url = urlparse(self.path)
        q = {k: v[0] for k, v in parse_qs(url.query).items()}
        route = url.path

        if route in ("/", "/index.html"):
            return self._page("dashboard.html")
        if route == "/citizen":
            return self._page("citizen.html")
        if route == "/officer":
            return self._page("officer.html")
        if route == "/demo":
            return self._page("demo.html") if self._is_local() else self._send(403, "Laptop only", "text/plain")
        if route == "/common.css":
            return self._send(200, (HERE / "common.css").read_bytes(), "text/css")

        if route == "/api/stats":
            return self._json(cases.dashboard_stats())

        if route == "/api/citizen":
            chat_id = read_token(q.get("t"), "c")
            if chat_id is None:
                return self._json({"error": "This link is not valid. Send /mydashboard to the bot."}, 403)
            data = cases.citizen_view(chat_id)
            lang = data["language"]
            data["labels"] = {k: v[lang] for k, v in STATUS_LABEL.items()}
            return self._json(data)

        if route == "/api/officer":
            chat_id = read_token(q.get("t"), "o")
            if chat_id is None:
                return self._json({"error": "This link is not valid. Send /mydashboard to the bot."}, 403)
            held = cases.posts_held_by(chat_id)
            if not held:
                return self._json({"error": "This account holds no officer post. Use /officer in the bot."}, 403)
            post = q.get("post") if q.get("post") in held else held[0]
            data = cases.officer_view(post)
            data["posts"] = held
            return self._json(data)

        if route == "/api/demo":
            if not self._is_local():
                return self._json({"error": "laptop only"}, 403)
            citizens = {}
            for c in db.all_cases():
                if not c["is_seed"]:
                    citizens.setdefault(c["citizen_chat_id"], c["citizen_name"] or "Citizen")
            officers = []
            for p in ALL_POSTS:
                chat = cases.officer_chat(p)
                if chat:
                    level = ("senior" if not get_senior_post(p) else
                             "officer" if cases.team_of(p) else "field")
                    officers.append({"post": p, "level": level,
                                     "url": f"/officer?t={make_token('o', chat)}&post={quote(p)}"})
            return self._json({
                "citizens": [{"name": n, "url": f"/citizen?t={make_token('c', cid)}"}
                             for cid, n in citizens.items()],
                "officers": officers,
                "phone_base": base_url(),
            })

        if route == "/media":
            case = db.get_case(q.get("case", ""))
            if not case or not can_see_case(q, case):
                return self._send(403, "Not allowed", "text/plain")
            file_id = db.last_proof(case["tracking_id"]) if q.get("kind") == "proof" else case["media_file_id"]
            if not file_id:
                return self._send(404, "No file", "text/plain")
            try:
                data, kind = fetch_telegram_file(file_id)
            except Exception as exc:
                return self._send(502, f"Could not fetch file: {exc}", "text/plain")
            return self._send(200, data, kind)

        self._json({"error": "not found"}, 404)

    def do_POST(self):
        if not self._is_local():  # routing and the demo clock are laptop-only
            return self._json({"error": "Only from the laptop"}, 403)
        length = int(self.headers.get("Content-Length", 0))
        try:
            body = json.loads(self.rfile.read(length) or b"{}")
            if self.path == "/api/route" and HOOKS["route"]:
                HOOKS["route"](body["tracking_id"], body["post"])
            elif self.path == "/api/tick" and HOOKS["tick"]:
                HOOKS["tick"](float(body.get("hours", 48)))
            else:
                return self._json({"error": "not found"}, 404)
            self._json({"ok": True})
        except Exception as exc:
            self._json({"error": str(exc)}, 400)

    def log_message(self, *args):
        pass  # keep the terminal clean for the demo


class Server(ThreadingHTTPServer):
    # On Windows, address reuse lets a second copy bind the same port silently.
    # Without it, a second start fails at once, which is what we want.
    allow_reuse_address = False


def start(port=PORT):
    server = Server(("0.0.0.0", port), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server


if __name__ == "__main__":
    # View-only mode: `python dashboard.py` shows the dashboards without the bot.
    import time
    db.init_db()
    start()
    print(f"Dashboards (view only) at http://localhost:{PORT}  ·  role switcher: http://localhost:{PORT}/demo")
    while True:  # sleep loop, so Ctrl+C works on Windows
        time.sleep(1)
