# Stump Press

**Historic newspaper scans so badly OCRed that only a human with eyes can answer.**

Stump Press hunts 19th-century U.S. newspaper page scans (Chronicling America / loc.gov,
public domain) where the OCR is missing or garbage. You look at the **page image**, invent
a question about a **tiny local crumb** (tea party, church social, blotter line, obscure ad),
and lock the answer behind **three chaining clues**. Text-only models choke: the OCR is junk,
and the fact was never famous enough to memorize.

```
Clue 1  →  identify entity A (which ladies’ society?)
Clue 2  →  only using A, get entity B (where did *that* society hold the tea?)
Clue 3  →  only using B, land the answer (what weekday/date was the event at *that* hall?)
```

Not three parallel hints. A funnel. A chain.

## The game

1. Hunt pages with high OCR junk scores (and a nudge toward local-notice language).
2. Open the scan. Ignore the OCR paste.
3. Prefer **unique local crumbs** — society notes, strawberry festivals, $3 fines on Water
   Street — **not** presidents, wars, or anything a general LLM already knows.
4. Write a stump question + **exactly 3 chaining clues** + answer + why a text model fails.
5. Share the challenge card JSON. Watch models guess from garbage text and lose.

### Challenge card shape

```json
{
  "question": "On what weekday and calendar date did the tea at Masonic Hall take place?",
  "chaining_clues": [
    "Identify which ladies' society placed the tea notice (A).",
    "Using that society's notice: where was the tea held? (B = the hall).",
    "Using that hall's event line + issue date: which weekday and 'inst.' date?"
  ],
  "answer": "Thursday, June 12, 1884",
  "why_stumps_text_model": "Bad OCR; unique local crumb; needs A→B→answer from the image."
}
```

`hops` is kept as a legacy mirror of the same three strings. Prefer `chaining_clues`.

## Quick start

```bash
python3 -m venv .venv && .venv/bin/pip install -e ".[dev]"
make verify          # tests + sample pack
.venv/bin/stump hunt --year-start 1880 --year-end 1895 --limit 10 -v
.venv/bin/stump show <id>   # writes challenges/<id>.json (+ thumb if downloadable)
make serve           # http://127.0.0.1:8765/
```

Offline demo: `stump pack` writes three sample cards under `challenges/` with synthetic bad
OCR and real loc.gov `page_url`s. The UI loads them with no network hunt required.

### CLI

| Command | What it does |
|--------|----------------|
| `stump hunt --year-start 1880 --year-end 1895 --limit 20` | Live LOC search → score OCR → list junkiest / local-crumb-ish pages |
| `stump show <id>` | Save challenge card JSON; try a small JPEG thumb |
| `stump pack` | Write sample chaining-clue cards |
| `stump serve` | Gallery + form (3 chaining clue fields, independence warning) |
| `stump score file.txt` | Score OCR text alone |

Hunter ranking = OCR junkiness **plus** a small bonus when OCR (even mangled) still smells
like society / tea / church / blotter / strawberry-festival language.

## How the OCR score works

Deterministic heuristics (no GPU, no Tesseract required):

- empty / very short
- high non-alphanumeric ratio
- low dictionary-ish word rate (bundled tiny English list)
- repeated junk characters, weird tokens, chaotic unique tokens

Returns `0–1` (1 = unusable) + reasons. Pillow can add contrast/brightness “hard scan”
stats when a thumb downloads; if Tesseract isn’t around we simply don’t re-OCR.

## Legal / politeness

Pages are **public domain** historic newspapers via the Library of Congress Chronicling
America collection on loc.gov. This tool uses the **public JSON / text-services endpoints**
with a clear User-Agent, small result limits, and short pauses between requests. Don’t hammer
LOC. Don’t scrape abusively. Read LOC terms of use. We’re here to play a research game, not
to DDoS a library.

## Dev

```bash
make test
make verify
```

Tests use fixtures only (no live API). `stump hunt` needs network and may flake if LOC is
grumpy — that’s expected.

## License

MIT — see `LICENSE`.
