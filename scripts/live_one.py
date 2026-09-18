from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Iterable, List

from trf_one.live_market import (
    ExecutionPrice,
    assess_execution_prices,
    build_consensus_quotes,
    build_execution_queue,
)
from trf_one.providers.the_odds_api import TheOddsAPIClient


def write_queue(path: Path, queue) -> None:
    fields = [
        "fixture_id","sport","commence_time","home_team","away_team",
        "market_group","selection","line","fair_probability","fair_odds",
        "required_execution_odds","best_market_odds","bookmakers",
        "priority_ratio","status","execution_source","execution_odds"
    ]
    with path.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fields)
        w.writeheader()
        for item in queue:
            row = item.to_dict()
            row["execution_source"] = "Napoleon"
            row["execution_odds"] = ""
            w.writerow({k: row.get(k, "") for k in fields})


def load_execution_prices(path: Path) -> List[ExecutionPrice]:
    out = []
    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        for line_no, row in enumerate(csv.DictReader(fh), start=2):
            raw_odds = (row.get("execution_odds") or "").strip()
            if not raw_odds:
                continue
            raw_line = (row.get("line") or "").strip()
            try:
                out.append(
                    ExecutionPrice(
                        fixture_id=row["fixture_id"].strip(),
                        market_group=row["market_group"].strip(),
                        selection=row["selection"].strip(),
                        line=float(raw_line) if raw_line else None,
                        execution_odds=float(raw_odds),
                        execution_source=(row.get("execution_source") or "Napoleon").strip(),
                    )
                )
            except Exception as exc:
                raise ValueError(f"Invalid execution row at line {line_no}: {exc}") from exc
    return out


def active_soccer_keys(client: TheOddsAPIClient) -> List[str]:
    return sorted(
        str(row["key"])
        for row in client.sports()
        if row.get("active") and str(row.get("key", "")).startswith("soccer_")
    )


def main() -> None:
    p = argparse.ArgumentParser(description="T.R.F ONE real-time market-first scanner")
    p.add_argument("--sports", nargs="+", help="The Odds API sport keys")
    p.add_argument("--payload-json", help="Offline/current-odds JSON fixture for smoke tests or manual fallback")
    p.add_argument("--list-sports", action="store_true")
    p.add_argument("--regions", default="eu,uk")
    p.add_argument("--markets", default="h2h,totals")
    p.add_argument("--devig", choices=["shin","power","proportional"], default="shin")
    p.add_argument("--min-books", type=int, default=3)
    p.add_argument("--min-ev", type=float, default=0.02)
    p.add_argument("--queue-top", type=int, default=3)
    p.add_argument("--execution", help="Filled execution queue CSV, usually Napoleon")
    p.add_argument("--output-dir", default="live_output")
    args = p.parse_args()

    client = TheOddsAPIClient()

    if args.list_sports:
        for key in active_soccer_keys(client):
            print(key)
        return

    if not args.sports and not args.payload_json:
        p.error("--sports is required unless --list-sports or --payload-json is used")

    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    market_keys = tuple(x.strip() for x in args.markets.split(",") if x.strip())
    quotes = []
    snapshots = []

    if args.payload_json:
        raw = json.loads(Path(args.payload_json).read_text(encoding="utf-8"))
        sport = str(raw.get("sport") or (args.sports[0] if args.sports else "offline"))
        from datetime import datetime, timezone
        fetched_raw = raw.get("fetched_at")
        fetched_at = (
            datetime.fromisoformat(str(fetched_raw).replace("Z", "+00:00"))
            if fetched_raw else datetime.now(timezone.utc)
        )
        events = raw.get("events") or []
        snapshots.append({"sport": sport, "fetched_at": fetched_at.isoformat(), "events": len(events)})
        quotes.extend(
            build_consensus_quotes(
                events,
                sport=sport,
                fetched_at=fetched_at,
                devig_method=args.devig,
                min_books=args.min_books,
                market_keys=market_keys,
            )
        )
    else:
        for sport in args.sports:
            print(f"Fetching {sport} ...", flush=True)
            payload = client.current_odds(
                sport=sport,
                regions=args.regions,
                markets=args.markets,
            )
            snapshots.append({
                "sport": sport,
                "fetched_at": payload.fetched_at.isoformat(),
                "events": len(payload.events),
            })
            quotes.extend(
                build_consensus_quotes(
                    payload.events,
                    sport=sport,
                    fetched_at=payload.fetched_at,
                    devig_method=args.devig,
                    min_books=args.min_books,
                    market_keys=market_keys,
                )
            )

    queue = build_execution_queue(
        quotes,
        min_ev=args.min_ev,
        top=args.queue_top,
        one_per_fixture=True,
    )
    queue_path = out_dir / "execution_queue.csv"
    write_queue(queue_path, queue)

    assessments = []
    if args.execution:
        prices = load_execution_prices(Path(args.execution))
        assessments = assess_execution_prices(quotes, prices, min_ev=args.min_ev)

    qualified = [x for x in assessments if x.decision == "QUALIFY"]

    payload = {
        "status": "SHADOW-EXECUTION",
        "source": "The Odds API multi-book consensus",
        "execution_default": "Napoleon Sports Belgique",
        "config": {
            "sports": args.sports or [snapshots[0]["sport"]] if snapshots else [],
            "regions": args.regions,
            "markets": list(market_keys),
            "devig_method": args.devig,
            "min_books": args.min_books,
            "min_ev": args.min_ev,
            "queue_top": args.queue_top,
        },
        "snapshots": snapshots,
        "market_quotes": [q.to_dict() for q in quotes],
        "execution_queue": [q.to_dict() for q in queue],
        "assessments": [x.to_dict() for x in assessments],
        "qualified": [x.to_dict() for x in qualified],
    }
    output_path = out_dir / "live_scan.json"
    output_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    print(f"Market quotes: {len(quotes)}")
    print(f"Napoleon soft-gate queue: {len(queue)}")
    for i, item in enumerate(queue, start=1):
        line = "" if item.line is None else f" {item.line:g}"
        print(
            f"{i}. {item.home_team} - {item.away_team} | "
            f"{item.market_group}{line} {item.selection} | "
            f"fair {item.fair_odds:.3f} | Napoleon threshold >= {item.required_execution_odds:.3f} | "
            f"{item.bookmakers} books"
        )
    if args.execution:
        print(f"Qualified after execution check: {len(qualified)}")
        for i, item in enumerate(qualified, start=1):
            print(
                f"VALUE {i}. {item.home_team} - {item.away_team} | "
                f"{item.market_group} {item.selection} | "
                f"{item.execution_source} {item.execution_odds:.3f} | EV {item.ev:.2%}"
            )

    print(f"Wrote {output_path}")
    print(f"Wrote {queue_path}")


if __name__ == "__main__":
    main()
