"""Tiny local server for CBT_Interface.html.

It lives in <vault>/_tools, serves the interface, and lists every question-set
JSON found anywhere in the vault so the interface can show them automatically.
It only listens on this PC (127.0.0.1). Close the console window to stop it.
"""
import json
import os
import re
import sys
import threading
import urllib.parse
import urllib.request
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
ROOT = TOOLS.parent
HTML = TOOLS / "CBT_Interface.html"
SKIP_DIRS = {".obsidian", ".git", ".trash", "_tools", "_Extracted-Text", "_Raw-PYQs", "_Results", "_Images", "node_modules"}
PORTS = range(8765, 8776)


def is_question_set(data):
    return isinstance(data, list) and data and isinstance(data[0], dict) and "question" in data[0]


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def scan():
    found = []
    for dirpath, dirnames, filenames in os.walk(ROOT):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for name in filenames:
            low = name.lower()
            if not low.endswith(".json") or low.startswith("template_json"):
                continue
            path = Path(dirpath) / name
            try:
                data = read_json(path)
            except Exception:
                continue
            if is_question_set(data):
                found.append({"path": path.relative_to(ROOT).as_posix(), "count": len(data)})
    found.sort(key=lambda item: item["path"].lower())
    return found


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def send(self, code, body, ctype):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        url = urllib.parse.urlparse(self.path)
        if url.path in ("/", "/index.html"):
            try:
                self.send(200, HTML.read_bytes(), "text/html; charset=utf-8")
            except OSError:
                self.send(404, b"CBT_Interface.html was not found next to cbt_server.py", "text/plain")
        elif url.path == "/api/ping":
            self.send(200, b"cbt", "text/plain")
        elif url.path == "/api/sets":
            body = json.dumps({"root": str(ROOT), "sets": scan()}, ensure_ascii=False).encode("utf-8")
            self.send(200, body, "application/json; charset=utf-8")
        elif url.path == "/api/file":
            rel = urllib.parse.parse_qs(url.query).get("path", [""])[0]
            target = (ROOT / rel).resolve()
            if ROOT not in target.parents or target.suffix.lower() != ".json" or not target.is_file():
                self.send(404, b"not found", "text/plain")
                return
            try:
                body = json.dumps(read_json(target), ensure_ascii=False).encode("utf-8")
            except Exception:
                self.send(500, b"could not read that file", "text/plain")
                return
            self.send(200, body, "application/json; charset=utf-8")
        elif url.path.startswith("/img/"):
            name = urllib.parse.unquote(url.path[len("/img/"):])
            img_dir = (ROOT / "_Images").resolve()
            target = (img_dir / name).resolve()
            types = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
                     ".gif": "image/gif", ".webp": "image/webp", ".svg": "image/svg+xml"}
            if img_dir not in target.parents or target.suffix.lower() not in types or not target.is_file():
                self.send(404, b"not found", "text/plain")
                return
            self.send(200, target.read_bytes(), types[target.suffix.lower()])
        else:
            self.send(404, b"not found", "text/plain")

    def do_POST(self):
        url = urllib.parse.urlparse(self.path)
        if url.path != "/api/result" or self.headers.get("X-CBT") != "1":
            self.send(404, b"not found", "text/plain")
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length <= 0 or length > 2_000_000:
                raise ValueError("bad size")
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
            file_id = str(payload.get("fileId", ""))
            if not re.fullmatch(r"[A-Za-z0-9_.-]{1,150}", file_id) or ".." in file_id:
                raise ValueError("bad file id")
            data = payload.get("data")
            if not isinstance(data, dict):
                raise ValueError("bad data")
            out_dir = ROOT / "_Results"
            out_dir.mkdir(exist_ok=True)
            (out_dir / f"{file_id}.json").write_text(
                json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception:
            self.send(400, b"could not save", "text/plain")
            return
        self.send(200, b"ok", "text/plain")


class Server(ThreadingHTTPServer):
    allow_reuse_address = False  # on Windows this stops two copies sharing one port


def already_running(port):
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/ping", timeout=0.7) as r:
            return r.read() == b"cbt"
    except Exception:
        return False


def main():
    for port in PORTS:
        url = f"http://localhost:{port}/"
        if already_running(port):
            print("CBT Interface is already running, opening it in your browser.")
            webbrowser.open(url)
            return 0
        try:
            server = Server(("127.0.0.1", port), Handler)
        except OSError:
            continue
        print(f"CBT Interface is running at {url}")
        print(f"Reading question sets from {ROOT}")
        print("Keep this window open while you practise. Close it to stop.")
        threading.Timer(0.8, lambda: webbrowser.open(url)).start()
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass
        return 0
    print("Could not find a free port between 8765 and 8775.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
