"""Chaining-clue schema + dependency warnings."""

from stump_press.models import (
    empty_challenge_card,
    normalize_chaining_clues,
    validate_challenge,
    warn_independent_clues,
)
from stump_press.pack import write_sample_pack
from stump_press.local_crumbs import detect_local_crumbs


def test_normalize_exactly_three():
    assert normalize_chaining_clues(["a", "b"]) == ["a", "b", ""]
    assert len(normalize_chaining_clues(None)) == 3


def test_true_chain_no_independence_warning():
    clues = [
        "Identify which ladies' society placed the tea notice (entity A).",
        "Using that society's notice, where did they hold the tea? (entity B = hall).",
        "Using that hall's event line, which weekday and inst. date is given?",
    ]
    assert warn_independent_clues(clues) == []


def test_parallel_hints_warn():
    clues = [
        "Find the date on the page.",
        "Locate the mayor's name somewhere.",
        "Identify the price of coal independently.",
    ]
    warns = warn_independent_clues(clues)
    assert warns


def test_sample_pack_has_chaining_clues(tmp_path):
    n = write_sample_pack(tmp_path)
    assert n == 3
    import json
    card = json.loads((tmp_path / "sample_cedar_falls_tea_1884.json").read_text())
    assert len(card["chaining_clues"]) == 3
    assert all(isinstance(c, str) and c for c in card["chaining_clues"])
    assert card["answer"]
    # dependency language present in later clues
    assert "society" in card["chaining_clues"][1].lower() or "that" in card["chaining_clues"][1].lower()
    problems = validate_challenge(card)
    # may still have soft warnings empty
    assert not any(p.startswith("missing") for p in problems)


def test_empty_card_schema():
    card = empty_challenge_card({"id": "x"})
    assert card["chaining_clues"] == ["", "", ""]
    assert card["rules"]["chaining_clues_required"] == 3


def test_local_crumb_detect():
    hits, bonus = detect_local_crumbs("The Ladies' Society gave a tea party after the church social.")
    assert "tea_party" in hits or "society" in hits
    assert bonus > 0
