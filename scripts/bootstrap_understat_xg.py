from __future__ import annotations

import argparse
import csv
from pathlib import Path

from trf_one.providers.understat import FOOTBALL_DATA_TO_UNDERSTAT, UnderstatClient

DEFAULT_DIVISIONS = ["E0", "D1", "I1", "SP1", "F1"]
DEFAULT_YEARS = list(range(2019, 2026))


def main() -> None:
    p = argparse.ArgumentParser(description="Download public Understat match-level xG.")
    p.add_argument("--output", default="data/xg/understat_xg.csv")
    p.add_argument("--divisions", nargs="+", default=DEFAULT_DIVISIONS)
    p.add_argument("--years", nargs="+", type=int, default=DEFAULT_YEARS)
    args = p.parse_args()

    path = Path(args.output)
    path.parent.mkdir(parents=True, exist_ok=True)
    client = UnderstatClient()

    with path.open("w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh)
        w.writerow([
            "date","competition","understat_league","season","match_id",
            "home_team","away_team","home_goals","away_goals","home_xg","away_xg"
        ])
        for year in args.years:
            for division in args.divisions:
                league = FOOTBALL_DATA_TO_UNDERSTAT[division]
                print(f"Fetching Understat {league} {year}/{year+1} ...", flush=True)
                for m in client.fetch_league(league, year):
                    w.writerow([
                        m.date.isoformat(), division, league, year, m.match_id,
                        m.home_team, m.away_team, m.home_goals, m.away_goals, m.home_xg, m.away_xg
                    ])

    print(f"Wrote {path}")


if __name__ == "__main__":
    main()
