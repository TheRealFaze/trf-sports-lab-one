from __future__ import annotations

import argparse
import csv
from pathlib import Path

from trf_one.providers.football_data_uk import FootballDataUKClient

DEFAULT_DIVISIONS = ["E0", "D1", "I1", "SP1", "F1", "N1", "B1", "P1"]
DEFAULT_YEARS = list(range(2019, 2026))


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Download Football-Data.co.uk league-seasons and normalize TRF match/odds/process CSVs."
    )
    parser.add_argument("--output", default="data/bootstrap")
    parser.add_argument("--divisions", nargs="+", default=DEFAULT_DIVISIONS)
    parser.add_argument("--years", nargs="+", type=int, default=DEFAULT_YEARS)
    args = parser.parse_args()

    out_dir = Path(args.output)
    out_dir.mkdir(parents=True, exist_ok=True)
    client = FootballDataUKClient()

    match_path = out_dir / "matches.csv"
    odds_path = out_dir / "odds_1x2.csv"
    process_path = out_dir / "process.csv"
    quality_path = out_dir / "quality.csv"

    with (
        match_path.open("w", encoding="utf-8", newline="") as mf,
        odds_path.open("w", encoding="utf-8", newline="") as of,
        process_path.open("w", encoding="utf-8", newline="") as pf,
        quality_path.open("w", encoding="utf-8", newline="") as qf,
    ):
        mw, ow, pw, qw = csv.writer(mf), csv.writer(of), csv.writer(pf), csv.writer(qf)
        mw.writerow(["date","competition","home_team","away_team","home_goals","away_goals"])
        ow.writerow(["date","competition","home_team","away_team","home_odds","draw_odds","away_odds","bookmaker","snapshot_type"])
        pw.writerow([
            "date","competition","home_team","away_team","home_goals","away_goals",
            "home_shots","away_shots","home_sot","away_sot","home_corners","away_corners"
        ])
        qw.writerow([
            "division","start_year","matches","quotes","closing_quotes","fallback_quotes",
            "process_matches","missing_process_rows","skipped_rows","duplicate_matches"
        ])

        for year in args.years:
            for division in args.divisions:
                print(f"Fetching {division} {year}/{year+1} ...", flush=True)
                season = client.fetch_season(division, year)
                for m in season.matches:
                    mw.writerow([m.date.isoformat(),division,m.home_team,m.away_team,int(m.home_goals),int(m.away_goals)])
                for o in season.quotes:
                    ow.writerow([o.date.isoformat(),division,o.home_team,o.away_team,o.home_odds,o.draw_odds,o.away_odds,o.bookmaker,o.snapshot_type])
                for p in season.process_matches:
                    pw.writerow([
                        p.date.isoformat(),division,p.home_team,p.away_team,p.home_goals,p.away_goals,
                        p.home_shots,p.away_shots,p.home_sot,p.away_sot,p.home_corners,p.away_corners
                    ])
                q=season.quality
                qw.writerow([
                    division,year,q.matches,q.quotes,q.closing_quotes,q.fallback_quotes,
                    q.process_matches,q.missing_process_rows,q.skipped_rows,q.duplicate_matches
                ])

    for p in (match_path,odds_path,process_path,quality_path):
        print(f"Wrote {p}")


if __name__ == "__main__":
    main()
