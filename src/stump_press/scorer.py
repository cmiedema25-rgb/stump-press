"""Deterministic OCR garbage / junkiness scorer."""

from __future__ import annotations

import re
from functools import lru_cache
from importlib import resources
from pathlib import Path

from stump_press.models import ScoreResult

_TOKEN_RE = re.compile(r"[A-Za-z]+(?:'[A-Za-z]+)?|\d+")
_WEIRD_RE = re.compile(r"[^A-Za-z0-9\s.,;:!?'\"\-—–()\[\]/&$%]")
_REPEAT_RE = re.compile(r"(.)\1{3,}")  # aaaa, ****, etc.
_BROKEN_RE = re.compile(r"\b[A-Za-z]*[^A-Za-z0-9\s][A-Za-z]+\b|\b[^\w\s]{2,}\b")


@lru_cache(maxsize=1)
def _load_wordlist() -> set[str]:
    try:
        ref = resources.files("stump_press").joinpath("data/english_words.txt")
        text = ref.read_text(encoding="utf-8")
    except (FileNotFoundError, TypeError, AttributeError):
        # Fallback for editable / source layouts
        path = Path(__file__).resolve().parent / "data" / "english_words.txt"
        text = path.read_text(encoding="utf-8") if path.exists() else ""
    return {w.strip().lower() for w in text.splitlines() if w.strip()}


def _tokens(text: str) -> list[str]:
    return [m.group(0) for m in _TOKEN_RE.finditer(text)]


def score_ocr(text: str | None, *, min_chars: int = 40) -> ScoreResult:
    """Return junkiness score in [0, 1] plus human-readable reasons.

    1.0 means OCR is essentially unusable for answering image questions.
    """
    reasons: list[str] = []
    metrics: dict[str, float | int] = {}
    raw = text or ""
    stripped = raw.strip()
    n = len(stripped)
    metrics["char_count"] = n

    if n == 0:
        return ScoreResult(1.0, ["empty"], metrics)
    if n < min_chars:
        reasons.append("very_short")
        metrics["shortness"] = 1.0 - (n / min_chars)

    # Non-alphanumeric ratio (ignore ordinary whitespace)
    non_ws = re.sub(r"\s+", "", stripped)
    if non_ws:
        alnum = sum(1 for c in non_ws if c.isalnum())
        non_alnum_ratio = 1.0 - (alnum / len(non_ws))
    else:
        non_alnum_ratio = 1.0
    metrics["non_alnum_ratio"] = round(non_alnum_ratio, 4)
    if non_alnum_ratio > 0.35:
        reasons.append("high_non_alnum")
    elif non_alnum_ratio > 0.22:
        reasons.append("elevated_non_alnum")

    tokens = _tokens(stripped)
    metrics["token_count"] = len(tokens)
    alpha_tokens = [t for t in tokens if any(c.isalpha() for c in t)]
    metrics["alpha_token_count"] = len(alpha_tokens)

    wordlist = _load_wordlist()
    if alpha_tokens:
        known = sum(1 for t in alpha_tokens if t.lower() in wordlist)
        dict_rate = known / len(alpha_tokens)
    else:
        dict_rate = 0.0
    metrics["dictionary_word_rate"] = round(dict_rate, 4)
    if len(alpha_tokens) < 5:
        reasons.append("few_word_tokens")
    if dict_rate < 0.12 and len(alpha_tokens) >= 5:
        reasons.append("low_dictionary_rate")
    elif dict_rate < 0.22 and len(alpha_tokens) >= 8:
        reasons.append("weak_dictionary_rate")

    # Repeated junk chars
    repeats = list(_REPEAT_RE.finditer(stripped))
    metrics["repeat_runs"] = len(repeats)
    if len(repeats) >= 3 or (n > 0 and sum(len(m.group(0)) for m in repeats) / max(n, 1) > 0.05):
        reasons.append("repeated_junk_chars")

    # Broken / weird tokens
    weird_chars = len(_WEIRD_RE.findall(stripped))
    weird_ratio = weird_chars / max(n, 1)
    metrics["weird_char_ratio"] = round(weird_ratio, 4)
    if weird_ratio > 0.08:
        reasons.append("lots_of_weird_chars")

    # Unique weird short tokens (OCR confetti)
    weird_tokens = []
    for t in alpha_tokens:
        tl = t.lower()
        if len(t) <= 2:
            continue
        if tl in wordlist:
            continue
        # mostly consonants / mixed case noise / rare letter patterns
        vowels = sum(1 for c in tl if c in "aeiou")
        if vowels == 0 or (len(t) >= 4 and vowels / len(t) < 0.15):
            weird_tokens.append(t)
        elif re.search(r"[A-Z]{3,}.*[a-z].*[A-Z]|[a-z]+[A-Z]{2,}", t):
            weird_tokens.append(t)
    unique_weird = len(set(weird_tokens))
    metrics["unique_weird_tokens"] = unique_weird
    if unique_weird >= 12 and len(alpha_tokens) > 0 and unique_weird / len(alpha_tokens) > 0.25:
        reasons.append("many_unique_weird_tokens")

    # Very high unique-token chaos (almost no repetition of real words)
    if alpha_tokens:
        unique_ratio = len(set(t.lower() for t in alpha_tokens)) / len(alpha_tokens)
        metrics["unique_token_ratio"] = round(unique_ratio, 4)
        if unique_ratio > 0.92 and dict_rate < 0.25 and len(alpha_tokens) >= 20:
            reasons.append("chaotic_unique_tokens")

    # Compose score from weighted signals
    score = 0.0
    if "empty" in reasons:
        score = 1.0
    else:
        if "very_short" in reasons:
            score += 0.55 * float(metrics.get("shortness", 1.0))
        score += min(0.35, non_alnum_ratio * 0.7)
        score += max(0.0, (0.30 - dict_rate)) * 1.4  # penalize low dict rate
        if "few_word_tokens" in reasons:
            score += 0.25
        if "repeated_junk_chars" in reasons:
            score += 0.15
        if "lots_of_weird_chars" in reasons:
            score += min(0.25, weird_ratio * 2.0)
        if "many_unique_weird_tokens" in reasons:
            score += 0.18
        if "chaotic_unique_tokens" in reasons:
            score += 0.12
        if "elevated_non_alnum" in reasons and "high_non_alnum" not in reasons:
            score += 0.08

    score = max(0.0, min(1.0, score))
    # If OCR looks fine, keep reasons sparse
    if score < 0.25 and not reasons:
        reasons.append("looks_ok")
    elif score >= 0.55 and not reasons:
        reasons.append("junk_signals")

    metrics["score"] = round(score, 4)
    return ScoreResult(round(score, 4), reasons, metrics)
