"""Shared data shapes for candidates and chaining-clue challenge cards."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class ScoreResult:
    score: float  # 0 = clean OCR, 1 = unusable junk
    reasons: list[str] = field(default_factory=list)
    metrics: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class PageCandidate:
    id: str
    title: str
    date: str
    lccn: str
    page_url: str
    image_url: str | None
    image_urls: list[str] = field(default_factory=list)
    ocr_text: str = ""
    ocr_excerpt: str = ""
    score: float = 0.0
    reasons: list[str] = field(default_factory=list)
    metrics: dict[str, Any] = field(default_factory=dict)
    image_stats: dict[str, Any] = field(default_factory=dict)
    fulltext_url: str | None = None
    source: str = "chronicling-america"
    local_crumb_hits: list[str] = field(default_factory=list)
    local_crumb_bonus: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_challenge_stub(self) -> dict[str, Any]:
        return empty_challenge_card(
            {
                "id": self.id,
                "title": self.title,
                "date": self.date,
                "lccn": self.lccn,
                "page_url": self.page_url,
                "image_url": self.image_url,
                "image_urls": self.image_urls,
                "ocr_excerpt": self.ocr_excerpt or (self.ocr_text[:800] if self.ocr_text else ""),
                "ocr_score": self.score,
                "ocr_reasons": self.reasons,
                "ocr_metrics": self.metrics,
                "image_stats": self.image_stats,
                "local_crumb_hits": self.local_crumb_hits,
            }
        )


CHAINING_RULES = {
    "unique_local_crumb": True,
    "prefer": [
        "society notices",
        "tea parties",
        "church socials",
        "obscure ads",
        "minor police blotter",
    ],
    "avoid": ["famous national events", "well-known historical facts"],
    "chaining_clues_required": 3,
    "chaining_dependency": (
        "Clue 1 identifies entity A (society/person/place). "
        "Clue 2 is only resolvable using A and yields B. "
        "Clue 3 is only resolvable using B and yields the final answer. "
        "These are chaining clues, not three parallel hints."
    ),
}


def empty_challenge_card(base: dict[str, Any] | None = None) -> dict[str, Any]:
    """Canonical challenge schema: unique local crumb + 3 chaining clues."""
    card: dict[str, Any] = {
        "id": "",
        "title": "",
        "date": "",
        "lccn": "",
        "page_url": "",
        "image_url": None,
        "image_urls": [],
        "ocr_excerpt": "",
        "ocr_score": 0.0,
        "ocr_reasons": [],
        "ocr_metrics": {},
        "image_stats": {},
        "local_crumb_hits": [],
        "crumb_type": "local_notice",
        "question": "",
        # Primary field: ordered chaining clues (dependency required)
        "chaining_clues": ["", "", ""],
        # Legacy alias — same three strings; prefer chaining_clues
        "hops": [
            {"step": 1, "clue": ""},
            {"step": 2, "clue": ""},
            {"step": 3, "clue": ""},
        ],
        "answer": "",
        "why_stumps_text_model": "",
        "why_model_fails": "",
        "source": "chronicling-america",
        "license_note": (
            "Public domain historic newspaper page via Library of Congress "
            "Chronicling America / loc.gov. Respect LOC terms of use; do not abuse servers."
        ),
        "rules": dict(CHAINING_RULES),
    }
    if base:
        card.update({k: v for k, v in base.items() if v is not None})
        card["chaining_clues"] = normalize_chaining_clues(
            card.get("chaining_clues"), fallback_hops=card.get("hops")
        )
        card["hops"] = clues_to_hops(card["chaining_clues"])
        if card.get("why_model_fails") and not card.get("why_stumps_text_model"):
            card["why_stumps_text_model"] = card["why_model_fails"]
        card["rules"] = dict(CHAINING_RULES)
    return card


def normalize_chaining_clues(
    clues: Any, *, fallback_hops: Any = None
) -> list[str]:
    """Force exactly 3 clue strings in dependency order [c1, c2, c3]."""
    out: list[str] = []
    if isinstance(clues, list) and clues:
        for c in clues[:3]:
            if isinstance(c, dict):
                out.append(str(c.get("clue") or c.get("text") or "").strip())
            else:
                out.append(str(c).strip())
    elif isinstance(fallback_hops, list) and fallback_hops:
        for h in fallback_hops[:3]:
            if isinstance(h, dict):
                out.append(str(h.get("clue") or h.get("text") or "").strip())
            else:
                out.append(str(h).strip())
    while len(out) < 3:
        out.append("")
    return out[:3]


def clues_to_hops(clues: list[str]) -> list[dict[str, Any]]:
    return [{"step": i + 1, "clue": clues[i]} for i in range(3)]


def normalize_hops(hops: Any) -> list[dict[str, Any]]:
    return clues_to_hops(normalize_chaining_clues(None, fallback_hops=hops))


def validate_challenge(card: dict[str, Any]) -> list[str]:
    """Return validation problems (empty = finished card structurally ok)."""
    problems: list[str] = []
    if not (card.get("question") or "").strip():
        problems.append("missing question")
    if not (card.get("answer") or "").strip():
        problems.append("missing answer")
    if not (card.get("why_stumps_text_model") or card.get("why_model_fails") or "").strip():
        problems.append("missing why_stumps_text_model")
    clues = normalize_chaining_clues(card.get("chaining_clues"), fallback_hops=card.get("hops"))
    for i, c in enumerate(clues, start=1):
        if not c.strip():
            problems.append(f"missing chaining clue {i}")
    problems.extend(warn_independent_clues(clues))
    return problems


def warn_independent_clues(clues: list[str]) -> list[str]:
    """Heuristic warnings when clues look like parallel hints, not a chain.

    A true chain: C1→A, C2 uses A→B, C3 uses B→answer.
    Soft check: later clues should share lexical residue with earlier ones
    (names/places), or explicitly refer to prior entities ("that society",
    "the hall", "named above", pronouns tying back).
    """
    warnings: list[str] = []
    c1, c2, c3 = (clues + ["", "", ""])[:3]
    if not (c1 and c2 and c3):
        return warnings

    backref = (
        r"\b(that|those|the same|said|aforementioned|above|this|their|its|"
        r"which|who|where|there|hall|society|church|club|notice|named)\b"
    )
    import re

    def tokens(s: str) -> set[str]:
        return {t.lower() for t in re.findall(r"[A-Za-z][A-Za-z']{2,}", s)}

    t1, t2, t3 = tokens(c1), tokens(c2), tokens(c3)
    # Content words longer than stop-ish
    stop = {
        "the", "and", "for", "that", "with", "from", "this", "which", "find",
        "read", "note", "locate", "using", "only", "onto", "into", "page",
        "clue", "answer", "final", "yields", "identify", "resolvable",
    }
    sig1 = t1 - stop

    c2_back = bool(re.search(backref, c2, re.I)) or bool(sig1 & t2)
    c3_back = bool(re.search(backref, c3, re.I)) or bool((sig1 | t2) & t3)

    if not c2_back:
        warnings.append(
            "clue 2 may be independent of clue 1 — chain should use entity A from clue 1"
        )
    if not c3_back:
        warnings.append(
            "clue 3 may be independent of prior clues — chain should use entity B from clue 2"
        )
    # Very similar length parallel "Find X" starters without backrefs
    starters = [re.match(r"^\s*(find|locate|read|note|identify)\b", c, re.I) for c in (c1, c2, c3)]
    if all(starters) and not c2_back and not c3_back:
        warnings.append("clues look like three parallel hints, not a dependency chain")
    return warnings
