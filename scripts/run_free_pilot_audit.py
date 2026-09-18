from __future__ import annotations

import argparse
import csv
import json
from dataclasses import asdict
from datetime import datetime
from math import log
from pathlib import Path
from statistics import mean
from typing import Dict, List, Sequence, Tuple

from trf_one.backtest import Historical1X2Quote, fit_blend_weight, geometric_blend_1x2
from trf_one.structural import DixonColesStructuralModel, MatchRecord, StructuralConfig


def parse_dt(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def load_matches(path: Path) -> Dict[str, List[MatchRecord]]:
    out: Dict[str, List[MatchRecord]] = {}
    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        for row in csv.DictReader(fh):
            comp = row["competition"].strip()
            out.setdefault(comp, []).append(
                MatchRecord(
                    date=parse_dt(row["date"]),
                    home_team=row["home_team"].strip(),
                    away_team=row["away_team"].strip(),
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
            comp = row["competition"].strip()
            out.setdefault(comp, []).append(
                Historical1X2Quote(
                    date=parse_dt(row["date"]),
                    home_team=row["home_team"].strip(),
                    away_team=row["away_team"].strip(),
                    home_odds=float(row["home_odds"]),
                    draw_odds=float(row["draw_odds"]),
                    away_odds=float(row["away_odds"]),
                    bookmaker=row.get("bookmaker", "market").strip(),
                    snapshot_type=row.get("snapshot_type", "CURRENT").strip(),
                )
            )
    return out


def outcome_index(match: MatchRecord) -> int:
    if match.home_goals > match.away_goals:
        return 0
    if match.home_goals == match.away_goals:
        return 1
    return 2


def brier(rows: Sequence[Tuple[Tuple[float, float, float], int]]) -> float:
    return sum(
        sum((p - (1.0 if i == y else 0.0)) ** 2 for i, p in enumerate(probs))
        for probs, y in rows
    ) / len(rows)


def logloss(rows: Sequence[Tuple[Tuple[float, float, float], int]]) -> float:
    eps = 1e-15
    return sum(-log(min(max(probs[y], eps), 1.0 - eps)) for probs, y in rows) / len(rows)


def accuracy(rows: Sequence[Tuple[Tuple[float, float, float], int]]) -> float:
    return sum(int(max(range(3), key=lambda i: probs[i]) == y) for probs, y in rows) / len(rows)


def season_label(dt: datetime) -> str:
    start = dt.year if dt.month >= 7 else dt.year - 1
    return f"{start}/{str(start + 1)[-2:]}"


def audit_competition(
    matches: List[MatchRecord],
    quotes: List[Historical1X2Quote],
    *,
    min_training_matches: int,
    max_iter: int,
    blend_min_history: int,
) -> dict:
    quote_map = {(q.date, q.home_team, q.away_team): q for q in quotes if q.snapshot_type == "CLOSE"}
    months = sorted({(m.date.year, m.date.month) for m in matches})

    model_rows: List[Tuple[Tuple[float, float, float], int]] = []
    market_rows: List[Tuple[Tuple[float, float, float], int]] = []
    blend_rows: List[Tuple[Tuple[float, float, float], int]] = []
    blend_weights: List[float] = []
    history_market: List[Tuple[float, float, float]] = []
    history_model: List[Tuple[float, float, float]] = []
    history_y: List[int] = []
    by_season: Dict[str, dict] = {}

    structural_config = StructuralConfig(
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

        model = DixonColesStructuralModel(structural_config).fit(train, as_of=cutoff)
        current: List[Tuple[Tuple[float, float, float], Tuple[float, float, float], int, str]] = []

        if len(history_y) >= blend_min_history:
            w = fit_blend_weight(history_market, history_model, history_y, step=0.05)
        else:
            w = 0.0

        for m in test:
            quote = quote_map.get((m.date, m.home_team, m.away_team))
            if quote is None:
                continue
            forecast = model.forecast(m.home_team, m.away_team)
            p_model = (
                forecast.probabilities["home_win"],
                forecast.probabilities["draw"],
                forecast.probabilities["away_win"],
            )
            p_market = quote.fair_probabilities("shin")
            y = outcome_index(m)
            p_blend = geometric_blend_1x2(p_market, p_model, w)
            current.append((p_model, p_market, y, season_label(m.date)))
            model_rows.append((p_model, y))
            market_rows.append((p_market, y))
            blend_rows.append((p_blend, y))
            blend_weights.append(w)

            season = season_label(m.date)
            slot = by_season.setdefault(season, {"model": [], "market": [], "blend": []})
            slot["model"].append((p_model, y))
            slot["market"].append((p_market, y))
            slot["blend"].append((p_blend, y))

        # Outcomes from this month enter calibration only after the whole month is forecast.
        for p_model, p_market, y, _ in current:
            history_model.append(p_model)
            history_market.append(p_market)
            history_y.append(y)

    if not model_rows:
        raise RuntimeError("No matched out-of-sample predictions")

    season_metrics = {}
    for season, payload in by_season.items():
        if not payload["model"]:
            continue
        season_metrics[season] = {
            "n": len(payload["model"]),
            "model_log_loss": logloss(payload["model"]),
            "market_log_loss": logloss(payload["market"]),
            "blend_log_loss": logloss(payload["blend"]),
            "model_brier": brier(payload["model"]),
            "market_brier": brier(payload["market"]),
            "blend_brier": brier(payload["blend"]),
        }

    return {
        "n": len(model_rows),
        "model": {
            "log_loss": logloss(model_rows),
            "brier": brier(model_rows),
            "accuracy": accuracy(model_rows),
        },
        "market": {
            "log_loss": logloss(market_rows),
            "brier": brier(market_rows),
            "accuracy": accuracy(market_rows),
        },
        "blend": {
            "log_loss": logloss(blend_rows),
            "brier": brier(blend_rows),
            "accuracy": accuracy(blend_rows),
            "mean_model_weight": mean(blend_weights) if blend_weights else 0.0,
            "final_model_weight": blend_weights[-1] if blend_weights else 0.0,
        },
        "delta_vs_market": {
            "model_log_loss": logloss(model_rows) - logloss(market_rows),
            "blend_log_loss": logloss(blend_rows) - logloss(market_rows),
            "model_brier": brier(model_rows) - brier(market_rows),
            "blend_brier": brier(blend_rows) - brier(market_rows),
        },
        "by_season": season_metrics,
        "method": {
            "refit": "monthly blocked walk-forward",
            "min_training_matches": min_training_matches,
            "max_iter": max_iter,
            "blend_min_history": blend_min_history,
            "market_devig": "shin",
            "target_mode": "goals",
            "note": "Closing-market benchmark; no ROI claim because closing odds are not an execution timestamp.",
        },
    }


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--matches", default="data/bootstrap/matches.csv")
    p.add_argument("--odds", default="data/bootstrap/odds_1x2.csv")
    p.add_argument("--output", default="data/bootstrap/pilot_audit.json")
    p.add_argument("--min-training", type=int, default=500)
    p.add_argument("--max-iter", type=int, default=180)
    p.add_argument("--blend-min-history", type=int, default=250)
    args = p.parse_args()

    matches = load_matches(Path(args.matches))
    quotes = load_quotes(Path(args.odds))
    report = {"competitions": {}}

    for comp in sorted(matches):
        if comp not in quotes:
            continue
        print(f"Auditing {comp}: {len(matches[comp])} matches", flush=True)
        report["competitions"][comp] = audit_competition(
            matches[comp],
            quotes[comp],
            min_training_matches=args.min_training,
            max_iter=args.max_iter,
            blend_min_history=args.blend_min_history,
        )

    Path(args.output).write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
