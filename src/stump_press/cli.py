"""stump CLI — hunt / show / pack / serve."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from stump_press import __version__
from stump_press.fetcher import LocClient, hunt, make_page_id
from stump_press.image_stats import analyze_image_bytes
from stump_press.models import empty_challenge_card
from stump_press.scorer import score_ocr
from stump_press.store import (
    CHALLENGES_DIR,
    DATA_DIR,
    find_candidate,
    save_hunt_index,
    write_challenge,
)


def cmd_hunt(args: argparse.Namespace) -> int:
    print(
        f"Hunting Chronicling America pages {args.year_start}–{args.year_end} "
        f"(limit={args.limit}, min_score={args.min_score}) …",
        file=sys.stderr,
    )
    try:
        cands = hunt(
            year_start=args.year_start,
            year_end=args.year_end,
            limit=args.limit,
            query=args.query,
            state=args.state,
            min_score=args.min_score,
            fetch_ocr=not args.skip_ocr,
        )
    except Exception as exc:  # noqa: BLE001
        print(f"Hunt failed (network/API): {exc}", file=sys.stderr)
        return 2

    save_hunt_index(cands)
    print(f"{'SCORE':>6}  {'ID':<42}  DATE        REASONS")
    print("-" * 100)
    for c in cands:
        reasons = ",".join(c.reasons[:4])
        print(f"{c.score:6.3f}  {c.id:<42}  {c.date:<10}  {reasons}")
        if args.verbose:
            excerpt = (c.ocr_excerpt or "").replace("\n", " ")[:120]
            print(f"         {c.title[:80]}")
            print(f"         OCR: {excerpt!r}")
    print(f"\nSaved index → {DATA_DIR / 'hunt_index.json'}", file=sys.stderr)
    print(f"Next: stump show <id>   or   make serve", file=sys.stderr)
    return 0


def cmd_show(args: argparse.Namespace) -> int:
    cid = args.id
    found = find_candidate(cid)
    if not found:
        print(f"No candidate '{cid}'. Run `stump hunt` first.", file=sys.stderr)
        return 1

    # Rebuild PageCandidate-ish dict / ensure score fields
    ocr = found.get("ocr_text") or found.get("ocr_excerpt") or ""
    if args.refresh_score:
        scored = score_ocr(ocr)
        found["score"] = scored.score
        found["ocr_score"] = scored.score
        found["reasons"] = scored.reasons
        found["ocr_reasons"] = scored.reasons
        found["metrics"] = scored.metrics

    card = empty_challenge_card({
        "id": found.get("id") or cid,
        "title": found.get("title"),
        "date": found.get("date"),
        "lccn": found.get("lccn"),
        "page_url": found.get("page_url"),
        "image_url": found.get("image_url"),
        "image_urls": found.get("image_urls") or [],
        "ocr_excerpt": found.get("ocr_excerpt") or (ocr[:800] if ocr else ""),
        "ocr_score": found.get("ocr_score", found.get("score")),
        "ocr_reasons": found.get("ocr_reasons", found.get("reasons")),
        "ocr_metrics": found.get("ocr_metrics", found.get("metrics")),
        "image_stats": found.get("image_stats") or {},
        "local_crumb_hits": found.get("local_crumb_hits") or [],
        "crumb_type": found.get("crumb_type") or "local_notice",
        "question": found.get("question") or "",
        "chaining_clues": found.get("chaining_clues"),
        "hops": found.get("hops"),
        "answer": found.get("answer") or "",
        "why_stumps_text_model": found.get("why_stumps_text_model")
            or found.get("why_model_fails")
            or "",
        "why_model_fails": found.get("why_model_fails") or "",
        "source": found.get("source") or "chronicling-america",
        "license_note": found.get("license_note"),
    })

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    thumb_path = None
    image_url = card.get("image_url")
    if image_url and not args.no_download:
        try:
            client = LocClient()
            # Prefer a small II IF pct if available
            urls = list(card.get("image_urls") or [])
            pick = image_url
            for u in urls:
                if "pct:6.25" in u or "pct:12.5" in u:
                    pick = u
                    break
            blob = client.download_bytes(pick.split("#")[0])
            # Save as jpeg/png based on magic
            ext = ".jpg"
            if blob[:8] == b"\x89PNG\r\n\x1a\n":
                ext = ".png"
            elif blob[:2] == b"\xff\xd8":
                ext = ".jpg"
            elif blob[:4] == b"\x00\x00\x00\x0c" or b"jP" in blob[:20]:
                ext = ".jp2"
            thumb_path = out_dir / f"{card['id']}_thumb{ext}"
            thumb_path.write_bytes(blob)
            card["local_thumb"] = str(thumb_path)
            if ext in (".jpg", ".jpeg", ".png") or blob[:2] == b"\xff\xd8":
                card["image_stats"] = analyze_image_bytes(blob)
            print(f"Downloaded thumb → {thumb_path}", file=sys.stderr)
        except Exception as exc:  # noqa: BLE001
            card["download_error"] = str(exc)
            print(f"Thumb download skipped: {exc}", file=sys.stderr)

    path = write_challenge(card, out_dir)
    print(json.dumps(card, indent=2))
    print(f"\nWrote challenge card → {path}", file=sys.stderr)
    return 0


def cmd_pack(args: argparse.Namespace) -> int:
    """Write sample challenge cards into challenges/ (fixtures + any hunt hits)."""
    from stump_press.pack import write_sample_pack

    n = write_sample_pack(Path(args.out_dir))
    print(f"Packed {n} challenge card(s) → {args.out_dir}")
    return 0


def cmd_serve(args: argparse.Namespace) -> int:
    from stump_press.webapp import serve

    return serve(host=args.host, port=args.port)


def cmd_score(args: argparse.Namespace) -> int:
    text = Path(args.file).read_text(encoding="utf-8") if args.file else sys.stdin.read()
    result = score_ocr(text)
    print(json.dumps(result.to_dict(), indent=2))
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="stump",
        description="Stump Press — find garbage-OCR newspaper pages and invent stump-the-AI questions.",
    )
    p.add_argument("--version", action="version", version=f"stump-press {__version__}")
    sub = p.add_subparsers(dest="cmd", required=True)

    h = sub.add_parser("hunt", help="Query LOC and list high-junk OCR page candidates")
    h.add_argument("--year-start", type=int, default=1880)
    h.add_argument("--year-end", type=int, default=1895)
    h.add_argument("--limit", type=int, default=20)
    h.add_argument("--query", type=str, default=None, help="Optional keyword (qs)")
    h.add_argument("--state", type=str, default=None)
    h.add_argument("--min-score", type=float, default=0.0)
    h.add_argument("--skip-ocr", action="store_true", help="Search only (no OCR fetch)")
    h.add_argument("-v", "--verbose", action="store_true")
    h.set_defaults(func=cmd_hunt)

    s = sub.add_parser("show", help="Save a challenge card JSON (+ optional thumb)")
    s.add_argument("id", help="Candidate id from hunt")
    s.add_argument("--out-dir", default=str(CHALLENGES_DIR))
    s.add_argument("--no-download", action="store_true")
    s.add_argument("--refresh-score", action="store_true")
    s.set_defaults(func=cmd_show)

    pk = sub.add_parser("pack", help="Write sample challenge cards into challenges/")
    pk.add_argument("--out-dir", default=str(CHALLENGES_DIR))
    pk.set_defaults(func=cmd_pack)

    sv = sub.add_parser("serve", help="Serve the minimal local web UI")
    sv.add_argument("--host", default="127.0.0.1")
    sv.add_argument("--port", type=int, default=8765)
    sv.set_defaults(func=cmd_serve)

    sc = sub.add_parser("score", help="Score OCR text from a file or stdin")
    sc.add_argument("file", nargs="?", help="Text file (default: stdin)")
    sc.set_defaults(func=cmd_score)

    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
