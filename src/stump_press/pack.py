"""Write sample challenge cards with true 3-clue dependency chains."""

from __future__ import annotations

import json
from pathlib import Path

from stump_press.models import empty_challenge_card, normalize_chaining_clues


def _samples() -> list[dict]:
    """Synthetic bad-OCR local-crumb challenges; chaining_clues form a true funnel."""
    return [
        empty_challenge_card(
            {
                "id": "sample_cedar_falls_tea_1884",
                "title": "Image 3 of The Cedar Falls gazette (Cedar Falls, Iowa), June 13, 1884",
                "date": "1884-06-13",
                "lccn": "sn85049551",
                "page_url": "https://www.loc.gov/resource/sn85049551/1884-06-13/ed-1/?sp=3",
                "image_url": None,
                "ocr_excerpt": (
                    "S0ci3ty N0t3s — Th3 L4di3s' M1ss10n4ry S0c13ty 0f th3 "
                    "F1rst Pr3sbyt3r14n Chu4ch w1ll g1v3 4 t3a 4t M4s0n1c H4ll "
                    "0n Th#rsd4y 3v3n1ng 0f l4st w33k, th3 12th 1nst. "
                    "M3sd4m3s H0lbr00k 4nd V4n D#s3n p0#r3d. "
                    "@@@@ #### qqqq ~~~~ Illl /\\/\\/\\ rn rn rn"
                ),
                "ocr_score": 0.82,
                "ocr_reasons": [
                    "high_non_alnum",
                    "low_dictionary_rate",
                    "repeated_junk_chars",
                    "local_crumb_language",
                ],
                "local_crumb_hits": ["society", "tea_party", "church"],
                "crumb_type": "tea_party",
                "question": (
                    "On what weekday and calendar date did the tea at Masonic Hall take place?"
                ),
                "chaining_clues": [
                    (
                        "On the society-notes column, identify which ladies' society "
                        "placed the tea notice (entity A = that society)."
                    ),
                    (
                        "Using that society’s notice only: where did they hold the tea? "
                        "(entity B = the named hall in A’s notice — Masonic Hall)."
                    ),
                    (
                        "Using that hall’s event line from the same notice: which weekday "
                        "and ‘inst.’ date does it assign to the tea at B? Combine with the "
                        "issue date (June 13, 1884) to land the calendar answer."
                    ),
                ],
                "answer": "Thursday, June 12, 1884",
                "why_stumps_text_model": (
                    "OCR is digit-substituted garbage; the tea date is a unique Cedar Falls "
                    "society crumb; each clue needs the prior entity (society → hall → date)."
                ),
                "image_note": (
                    "URL-only sample; open page_url on loc.gov for the public-domain scan."
                ),
            }
        ),
        empty_challenge_card(
            {
                "id": "sample_emporia_strawberry_1891",
                "title": "Image 4 of The Emporia weekly news (Emporia, Kan.), July 3, 1891",
                "date": "1891-07-03",
                "lccn": "sn85066616",
                "page_url": "https://www.loc.gov/resource/sn85066616/1891-07-03/ed-1/?sp=4",
                "image_url": None,
                "ocr_excerpt": (
                    "CH#RCH S0C14L — Th3 y0#ng p30pl3 0f th3 M3th0d1st 3p1sc0p4l "
                    "ch#rch s3rv3d 4 str4wb3rry f3st1v4l 1n th3 ch#rch p4rl0rs "
                    "W3dn3sd4y 3v3n1ng. Pr0c33ds t0 th3 c4rp3t f#nd. "
                    "~~~~ //// .... ,, ,, Ill1 ||| 0O0O"
                ),
                "ocr_score": 0.78,
                "ocr_reasons": [
                    "high_non_alnum",
                    "low_dictionary_rate",
                    "lots_of_weird_chars",
                    "local_crumb_language",
                ],
                "local_crumb_hits": ["church_social", "church"],
                "crumb_type": "church_social",
                "question": (
                    "What weekday evening was the strawberry festival held, and what were "
                    "the proceeds for?"
                ),
                "chaining_clues": [
                    (
                        "Find the strawberry-festival notice and name the congregation that "
                        "hosted it (entity A = Methodist Episcopal Church)."
                    ),
                    (
                        "From A’s notice: where on the premises was the festival served? "
                        "(entity B = church parlors — only stated in A’s crumb)."
                    ),
                    (
                        "From the line about the event at B: which weekday evening was it, "
                        "and which fund received the proceeds? That pair is the answer."
                    ),
                ],
                "answer": "Wednesday evening; carpet fund",
                "why_stumps_text_model": (
                    "Bad OCR hides congregation → parlors → weekday/fund chain; minor Emporia "
                    "social, not a national fact."
                ),
                "image_note": "URL-only card; use page_url for the scan.",
            }
        ),
        empty_challenge_card(
            {
                "id": "sample_oswego_blotter_1879",
                "title": "Image 2 of The Oswego daily times (Oswego, N.Y.), March 18, 1879",
                "date": "1879-03-18",
                "lccn": "sn83031387",
                "page_url": "https://www.loc.gov/resource/sn83031387/1879-03-18/ed-1/?sp=2",
                "image_url": None,
                "ocr_excerpt": (
                    "P0L1C3 — J4s. M#ll1g4n, 4 b04tman, w4s f1n3d $3 4nd c0sts "
                    "f0r d1s0rd3rly c0nd#ct 0n W4t3r str33t S#nd4y n1ght. "
                    "M4g1str4t3 H#bb4rd.  *** ### $$$ ^^^ ~~~ rnrnrn"
                ),
                "ocr_score": 0.74,
                "ocr_reasons": [
                    "elevated_non_alnum",
                    "weak_dictionary_rate",
                    "repeated_junk_chars",
                    "local_crumb_language",
                ],
                "local_crumb_hits": ["blotter"],
                "crumb_type": "blotter",
                "question": (
                    "Before which magistrate was boatman Jas. Mulligan fined, and what was "
                    "the fine?"
                ),
                "chaining_clues": [
                    (
                        "On the police blotter, identify the defendant described as a boatman "
                        "(entity A = Jas. Mulligan)."
                    ),
                    (
                        "Using A’s blotter line: what charge and street/time context is given? "
                        "(entity B = disorderly conduct on Water Street Sunday night)."
                    ),
                    (
                        "From the disposition of B’s case in that same line: what fine/costs "
                        "and which magistrate close the notice? That is the answer."
                    ),
                ],
                "answer": "Magistrate Hubbard; $3 and costs",
                "why_stumps_text_model": (
                    "OCR mangling plus an obscure local blotter; must chain person → charge "
                    "context → magistrate/fine from the scan."
                ),
                "image_note": "Synthetic OCR fixture; page_url is the real LOC resource.",
            }
        ),
    ]


def write_sample_pack(out_dir: Path) -> int:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    samples = _samples()
    for card in samples:
        card["chaining_clues"] = normalize_chaining_clues(card.get("chaining_clues"))
        path = out_dir / f"{card['id']}.json"
        path.write_text(json.dumps(card, indent=2) + "\n", encoding="utf-8")
    stub = empty_challenge_card({"id": "_schema_stub", "title": "Empty chaining-clue stub"})
    (out_dir / "_schema_stub.json").write_text(
        json.dumps(stub, indent=2) + "\n", encoding="utf-8"
    )
    return len(samples)
