"""Local JSON store for hunt results and challenge cards."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from stump_press.models import PageCandidate

ROOT = Path.cwd()
DATA_DIR = ROOT / "data"
CHALLENGES_DIR = ROOT / "challenges"
HUNT_INDEX = DATA_DIR / "hunt_index.json"


def ensure_dirs() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    CHALLENGES_DIR.mkdir(parents=True, exist_ok=True)


def save_hunt_index(candidates: list[PageCandidate]) -> Path:
    ensure_dirs()
    payload = {
        "count": len(candidates),
        "candidates": [c.to_dict() for c in candidates],
    }
    HUNT_INDEX.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return HUNT_INDEX


def load_hunt_index() -> list[dict[str, Any]]:
    if not HUNT_INDEX.exists():
        return []
    data = json.loads(HUNT_INDEX.read_text(encoding="utf-8"))
    return list(data.get("candidates") or [])


def find_candidate(cid: str) -> dict[str, Any] | None:
    for c in load_hunt_index():
        if c.get("id") == cid:
            return c
    # Also scan challenges/
    path = CHALLENGES_DIR / f"{cid}.json"
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    for p in CHALLENGES_DIR.glob("*.json"):
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        if d.get("id") == cid:
            return d
    return None


def safe_filename(cid: str) -> str:
    return re.sub(r"[^a-zA-Z0-9._-]+", "_", cid)[:120]


def write_challenge(card: dict[str, Any], dest_dir: Path | None = None) -> Path:
    ensure_dirs()
    dest = dest_dir or CHALLENGES_DIR
    dest.mkdir(parents=True, exist_ok=True)
    cid = safe_filename(str(card.get("id") or "challenge"))
    path = dest / f"{cid}.json"
    path.write_text(json.dumps(card, indent=2), encoding="utf-8")
    return path
