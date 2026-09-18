from __future__ import annotations

import argparse
import csv
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List

from trf_one.backtest import Historical1X2Quote
from trf_one.residuals import ResidualObservation, max_positive_residual, residual_threshold_report
from trf_one.structural import DixonColesStructuralModel, MatchRecord, StructuralConfig


def parse_dt(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def season_label(dt: datetime) -> str:
    start = dt.year if dt.month >= 7 else dt.year - 1
    return f"{start}/{str(start + 1)[-2:]}"


def load_matches(path: Path) -> Dict[str, List[MatchRecord]]:
    out: Dict[str, List[MatchRecord]] = {}
    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        for row in csv.DictReader(fh):
            out.setdefault(row["competition"], []).append(
                MatchRecord(
                    date=parse_dt(row["date"]),
                    home_team=row["home_team"],
                    away_team=row["away_team"],
                    home_goals=float(row["home_goals"]),
                    away_goals=float(row["away_goals"]),
                )
            )
    for rows in out.values():
        rows.sort(key=lambda r: r.date)
    return out


def load_quotes(path: Path) -> Dict[str, List[Historical1X2Quote]]:
    out: Dict[str, List[Historical1X2Quote]] = {}
    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        for row in csv.DictReader(fh):
            out.setdefault(row["competition"], []).append(
                Historical1X2Quote(
                    date=parse_dt(row["date"]),
                    home_team=row["home_team"],
                    away_team=row["away_team"],
                    home_odds=float(row["home_odds"]),
                    draw_odds=float(row["draw_odds"]),
                    away_odds=float(row["away_odds"]),
                    bookmaker=row["bookmaker"],
                    snapshot_type=row["snapshot_type"],
                )
            )
    return out


def outcome_index(m: MatchRecord) -> int:
    if m.home_goals > m.away_goals:
        return 0
    if m.home_goals == m.away_goals:
        return 1
    return 2


def collect_residuals(
    competition: str,
    matches: List[MatchRecord],
    quotes: List[Historical1X2Quote],
    *,
    min_training_matches: int = 500,
    max_iter: int = 180,
) -> List[ResidualObservation]:
    quote_map = {(q.date, q.home_team, q.away_team): q for q in quotes if q.snapshot_type == "CLOSE"}
    months = sorted({(m.date.year, m.date.month) for m in matches})
    out: List[ResidualObservation] = []

    config = StructuralConfig(
        half_life_days=365.0,
        ridge=0.05,
        learning_rate=0.035,
        max_iter=max_iter,
        tol=1e-7,
        target_mode="goals",
        rho_min=-0.18,
        rho_max=0.18,
        rho_steps=37,
        uncertainty_scale=0.95,
        max_goals=9,
    )

    for year, month in months:
        test = [m for m in matches if (m.date.year, m.date.month) == (year, month)]
        if not test:
            continue
        cutoff = min(m.date for m in test)
        train = [m for m in matches if m.date < cutoff]
        if len(train) < min_training_matches:
            continue
        model = DixonColesStructuralModel(config).fit(train, as_of=cutoff)

        for m in test:
            q = quote_map.get((m.date, m.home_team, m.away_team))
            if q is None:
                continue
            f = model.forecast(m.home_team, m.away_team)
            p_model = (
                f.probabilities["home_win"],
                f.probabilities["draw"],
                f.probabilities["away_win"],
            )
            p_market = q.fair_probabilities("shin")
            odds = (q.home_odds, q.draw_odds, q.away_odds)
            out.append(
                max_positive_residual(
                    competition=competition,
                    season=season_label(m.date),
                    model_probabilities=p_model,
                    market_probabilities=p_market,
                    closing_odds=odds,
                    outcome_index=outcome_index(m),
                )
            )
    return out


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--matches", default="data/bootstrap/matches.csv")
    p.add_argument("--odds", default="data/bootstrap/odds_1x2.csv")
    p.add_argument("--output", default="data/bootstrap/residual_diagnostics.json")
    args = p.parse_args()

    matches = load_matches(Path(args.matches))
    quotes = load_quotes(Path(args.odds))
    all_rows: List[ResidualObservation] = []
    per_comp = {}

    for comp in sorted(matches):
        if comp not in quotes:
            continue
        print(f"Residual diagnostics {comp}", flush=True)
        rows = collect_residuals(comp, matches[comp], quotes[comp])
        all_rows.extend(rows)
        per_comp[comp] = residual_threshold_report(rows)

    report = {
        "method": {
            "selection": "one outcome per match: largest positive model-minus-market residual",
            "thresholds": [0.02, 0.05, 0.08, 0.10, 0.15],
            "market": "Football-Data average closing 1X2, Shin de-vig",
            "model": "TRF v0.2 structural goals model, monthly blocked OOS refit",
            "roi_note": "theoretical equal-stake ROI at average closing price; not a Napoleon/execution ROI",
        },
        "pooled": residual_threshold_report(all_rows),
        "competitions": per_comp,
    }
    Path(args.output).write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report["pooled"], indent=2))


if __name__ == "__main__":
    main()
