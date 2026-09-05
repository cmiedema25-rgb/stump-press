"""Minimal stdlib HTTP server for the challenge gallery UI."""

from __future__ import annotations

import json
import mimetypes
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from stump_press.models import empty_challenge_card, normalize_chaining_clues, clues_to_hops, validate_challenge
from stump_press.store import CHALLENGES_DIR, DATA_DIR, ensure_dirs, write_challenge

# Package-adjacent web/ at repo root when running from checkout
REPO_WEB = Path(__file__).resolve().parents[2] / "web"


def _load_gallery() -> list[dict]:
    ensure_dirs()
    items: list[dict] = []
    # Prefer challenges/
    for p in sorted(CHALLENGES_DIR.glob("*.json")):
        if p.name.startswith("_"):
            continue
        try:
            items.append(json.loads(p.read_text(encoding="utf-8")))
        except json.JSONDecodeError:
            continue
    # Merge hunt index high-junk if not already present
    idx = DATA_DIR / "hunt_index.json"
    if idx.exists():
        try:
            data = json.loads(idx.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            data = {}
        have = {i.get("id") for i in items}
        for c in data.get("candidates") or []:
            if c.get("id") in have:
                continue
            if float(c.get("score") or 0) < 0.35 and not c.get("local_crumb_hits"):
                continue
            items.append(empty_challenge_card(c))
    items.sort(key=lambda x: float(x.get("ocr_score") or x.get("score") or 0), reverse=True)
    return items


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt: str, *args) -> None:  # quieter
        pass

    def _send(self, code: int, body: bytes, content_type: str) -> None:
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _json(self, code: int, obj: object) -> None:
        raw = json.dumps(obj, indent=2).encode("utf-8")
        self._send(code, raw, "application/json; charset=utf-8")

    def do_GET(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        if path in ("/", "/index.html"):
            return self._static("index.html")
        if path.startswith("/static/"):
            return self._static(path[len("/static/") :])
        if path in ("/app.js", "/style.css"):
            return self._static(path.lstrip("/"))
        if path == "/api/challenges":
            return self._json(200, {"challenges": _load_gallery()})
        if path.startswith("/api/challenges/"):
            cid = path.split("/")[-1]
            for c in _load_gallery():
                if c.get("id") == cid:
                    return self._json(200, c)
            return self._json(404, {"error": "not found"})
        self._json(404, {"error": "not found"})

    def do_POST(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        if path != "/api/challenges":
            return self._json(404, {"error": "not found"})
        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length) if length else b"{}"
        try:
            payload = json.loads(raw.decode("utf-8"))
        except json.JSONDecodeError:
            return self._json(400, {"error": "invalid json"})
        card = empty_challenge_card(payload if isinstance(payload, dict) else {})
        card["chaining_clues"] = normalize_chaining_clues(
            card.get("chaining_clues"), fallback_hops=card.get("hops")
        )
        card["hops"] = clues_to_hops(card["chaining_clues"])
        problems = validate_challenge(card)
        # Allow saving drafts, but flag incompleteness
        path_out = write_challenge(card)
        return self._json(
            200,
            {
                "ok": True,
                "path": str(path_out),
                "incomplete": problems,
                "challenge": card,
            },
        )

    def _static(self, name: str) -> None:
        # Prevent path escape
        name = name.lstrip("/")
        if ".." in name or name.startswith("/"):
            return self._json(400, {"error": "bad path"})
        base = REPO_WEB if REPO_WEB.is_dir() else Path.cwd() / "web"
        fp = (base / name).resolve()
        if not str(fp).startswith(str(base.resolve())) or not fp.is_file():
            return self._send(404, b"not found", "text/plain")
        data = fp.read_bytes()
        ctype = mimetypes.guess_type(str(fp))[0] or "application/octet-stream"
        self._send(200, data, ctype)


def serve(host: str = "127.0.0.1", port: int = 8765) -> int:
    ensure_dirs()
    # Ensure samples exist for first-run demo
    if not any(CHALLENGES_DIR.glob("sample_*.json")):
        from stump_press.pack import write_sample_pack

        write_sample_pack(CHALLENGES_DIR)
    httpd = ThreadingHTTPServer((host, port), Handler)
    print(f"Stump Press UI → http://{host}:{port}/")
    print("Gallery of high-garbage / local-crumb pages. Write 3-hop stump questions.")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
    return 0
