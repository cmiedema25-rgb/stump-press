"""OCR garbage scorer tests (fixtures only — no live network)."""

from stump_press.scorer import score_ocr


def test_empty_is_max_junk():
    r = score_ocr("")
    assert r.score == 1.0
    assert "empty" in r.reasons


def test_clean_prose_low_score():
    text = (
        "The ladies of the church will meet on Thursday evening at the hall. "
        "Mrs. Holbrook and Mrs. Van Deusen poured tea for the society. "
        "Local news from the county town reported fair weather for the picnic."
    )
    r = score_ocr(text)
    assert r.score < 0.45
    assert "empty" not in r.reasons


def test_garbage_high_score():
    text = "@@@@ #### qqqq ~~~~ Illl /\\/\\/\\ rn rn rn Th# L4d13s' S0c13ty *** $$$ ^^^"
    r = score_ocr(text)
    assert r.score >= 0.55
    assert r.reasons  # some junk signal


def test_very_short():
    r = score_ocr("xx")
    assert r.score >= 0.5
    assert "very_short" in r.reasons


def test_repeated_junk():
    text = "aaaa aaaa **** **** the the hall hall " + ("~~~~" * 10)
    r = score_ocr(text)
    assert "repeated_junk_chars" in r.reasons or r.score >= 0.3
