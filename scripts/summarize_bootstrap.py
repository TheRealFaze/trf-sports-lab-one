from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--quality", default="data/bootstrap/quality.csv")
    p.add_argument("--output", default="data/bootstrap/quality_summary.json")
    args = p.parse_args()

    rows = list(csv.DictReader(Path(args.quality).open("r", encoding="utf-8")))
    if not rows:
        raise SystemExit("No quality rows")

    totals = {
        "league_seasons": len(rows),
        "matches": sum(int(r["matches"]) for r in rows),
        "quotes": sum(int(r["quotes"]) for r in rows),
        "closing_quotes": sum(int(r["closing_quotes"]) for r in rows),
        "fallback_quotes": sum(int(r["fallback_quotes"]) for r in rows),
        "skipped_rows": sum(int(r["skipped_rows"]) for r in rows),
        "duplicate_matches": sum(int(r["duplicate_matches"]) for r in rows),
    }
    totals["closing_quote_coverage"] = (
        totals["closing_quotes"] / totals["matches"] if totals["matches"] else 0.0
    )
    payload = {"totals": totals, "league_seasons": rows}
    Path(args.output).write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(json.dumps(payload["totals"], indent=2))


if __name__ == "__main__":
    main()
