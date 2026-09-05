"""Heuristics favoring unique local crumbs over famous national events."""

from __future__ import annotations

import re

# Language that often marks small-town / local-paper gold.
LOCAL_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("society", re.compile(r"\b(ladies['’]?\s+society|woman['’]?s\s+club|sewing\s+circle|aid\s+society)\b", re.I)),
    ("tea_party", re.compile(r"\b(tea\s+party|afternoon\s+tea|tea\s+social)\b", re.I)),
    ("church_social", re.compile(r"\b(church\s+social|strawberry\s+(festival|supper)|ice\s+cream\s+social|basket\s+supper|box\s+supper)\b", re.I)),
    ("church", re.compile(r"\b(methodist|baptist|presbyterian|episcopal|congregation|sunday\s+school|pastor\s+[A-Z])\b", re.I)),
    ("blotter", re.compile(r"\b(police\s+blotter|arrested|fined\s+\$|disorderly|vagrancy|drunk\s+and)\b", re.I)),
    ("obscure_ad", re.compile(r"\b(for\s+sale|wanted[.—:]|druggist|dry\s+goods|blacksmith|millinery|livery)\b", re.I)),
    ("local_notice", re.compile(r"\b(local\s+news|personals|about\s+town|town\s+and\s+county|society\s+notes)\b", re.I)),
    ("picnic", re.compile(r"\b(picnic|excursion|lawn\s+fete|lawn\s+fête)\b", re.I)),
]

# Soft down-rank if OCR is mostly national wire fame (still keep if OCR is garbage).
FAMOUS_PATTERNS = re.compile(
    r"\b(president\s+of\s+the\s+united\s+states|white\s+house|congress\s+passed|"
    r"declaration\s+of\s+independence|civil\s+war\s+ended|world\s+series)\b",
    re.I,
)


def detect_local_crumbs(text: str | None) -> tuple[list[str], float]:
    """Return (hit labels, bonus 0..0.15) for ranking hunters toward local crumbs."""
    if not text:
        return [], 0.0
    hits: list[str] = []
    for label, pat in LOCAL_PATTERNS:
        if pat.search(text):
            hits.append(label)
    bonus = min(0.15, 0.04 * len(hits))
    if FAMOUS_PATTERNS.search(text) and not hits:
        bonus = max(0.0, bonus - 0.05)
    return hits, round(bonus, 4)
