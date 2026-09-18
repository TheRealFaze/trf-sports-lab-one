from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import List

from trf_one.market_scanner import MarketOutcomeInput, ScannerConfig, scan_markets


def load_rows(path: Path) -> List[MarketOutcomeInput]:
    rows = []
    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(fh)
        required = {
            "fixture_id", "market_group", "selection",
            "consensus_odds", "execution_odds",
        }
        missing = required - set(reader.fieldnames or [])
        if missing:
            raise ValueError(f"Input CSV missing required columns: {sorted(missing)}")

        for line_no, r in enumerate(reader, start=2):
            try:
                raw_model = (r.get("model_probability") or "").strip()
                rows.append(MarketOutcomeInput(
                    fixture_id=r["fixture_id"].strip(),
                    market_group=r["market_group"].strip(),
                    selection=r["selection"].strip(),
                    consensus_odds=float(r["consensus_odds"]),
                    execution_odds=float(r["execution_odds"]),
                    competition=(r.get("competition") or "").strip(),
                    kickoff=(r.get("kickoff") or "").strip(),
                    home_team=(r.get("home_team") or "").strip(),
                    away_team=(r.get("away_team") or "").strip(),
                    consensus_source=(r.get("consensus_source") or "consensus").strip(),
                    execution_source=(r.get("execution_source") or "execution").strip(),
                    model_probability=float(raw_model) if raw_model else None,
                ))
            except Exception as exc:
                raise ValueError(f"Invalid input at line {line_no}: {exc}") from exc
    return rows


def main() -> None:
    p = argparse.ArgumentParser(description="T.R.F ONE market-first pre-match scanner")
    p.add_argument("input_csv")
    p.add_argument("--output", default="one_scan.json")
    p.add_argument("--devig", choices=["shin", "power", "proportional"], default="shin")
    p.add_argument("--min-ev", type=float, default=0.02)
    p.add_argument("--model-weight", type=float, default=0.0)
    p.add_argument("--model-veto-pp", type=float, default=0.10)
    p.add_argument("--allow-same-source", action="store_true")
    p.add_argument("--top", type=int, default=20)
    args = p.parse_args()

    config = ScannerConfig(
        devig_method=args.devig,
        min_prudent_ev=args.min_ev,
        model_weight=args.model_weight,
        model_veto_pp=args.model_veto_pp,
        reject_same_source=not args.allow_same_source,
    )
    results = scan_markets(load_rows(Path(args.input_csv)), config=config)
    payload = {
        "status": "SHADOW-EXECUTION",
        "config": {
            "devig_method": config.devig_method,
            "min_prudent_ev": config.min_prudent_ev,
            "model_weight": config.model_weight,
            "model_veto_pp": config.model_veto_pp,
            "reject_same_source": config.reject_same_source,
        },
        "qualified": [r.to_dict() for r in results if r.decision == "QUALIFY"][: args.top],
        "all": [r.to_dict() for r in results],
    }
    Path(args.output).write_text(json.dumps(payload, indent=2), encoding="utf-8")

    qualified = payload["qualified"]
    print(f"ONE SHADOW-EXECUTION — {len(qualified)} qualified outcome(s)")
    for i, r in enumerate(qualified, start=1):
        print(
            f"{i:>2}. {r['home_team']} - {r['away_team']} | "
            f"{r['market_group']} {r['selection']} | "
            f"exec {r['execution_odds']:.3f} | fair {r['market_fair_odds']:.3f} | "
            f"EV prudent {r['ev_prudent']:.2%}"
        )
    print(f"Wrote {args.output}")


if __name__ == "__main__":
    main()
