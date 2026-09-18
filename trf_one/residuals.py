from __future__ import annotations

from dataclasses import dataclass
from statistics import mean
from typing import Dict, Iterable, List, Sequence, Tuple


OUTCOME_NAMES = {0: "HOME", 1: "DRAW", 2: "AWAY"}


@dataclass(frozen=True)
class ResidualObservation:
    competition: str
    season: str
    selected_index: int
    residual: float
    model_probability: float
    market_probability: float
    closing_odds: float
    outcome_index: int

    @property
    def won(self) -> bool:
        return self.selected_index == self.outcome_index

    @property
    def pnl_at_close(self) -> float:
        return self.closing_odds - 1.0 if self.won else -1.0

    @property
    def model_ev_at_close(self) -> float:
        return self.model_probability * self.closing_odds - 1.0


def max_positive_residual(
    *,
    competition: str,
    season: str,
    model_probabilities: Sequence[float],
    market_probabilities: Sequence[float],
    closing_odds: Sequence[float],
    outcome_index: int,
) -> ResidualObservation:
    if not (len(model_probabilities) == len(market_probabilities) == len(closing_odds) == 3):
        raise ValueError("1X2 vectors must contain exactly 3 elements")
    residuals = [m - p for m, p in zip(model_probabilities, market_probabilities)]
    idx = max(range(3), key=lambda i: residuals[i])
    return ResidualObservation(
        competition=competition,
        season=season,
        selected_index=idx,
        residual=float(residuals[idx]),
        model_probability=float(model_probabilities[idx]),
        market_probability=float(market_probabilities[idx]),
        closing_odds=float(closing_odds[idx]),
        outcome_index=int(outcome_index),
    )


def summarize_observations(rows: Sequence[ResidualObservation]) -> Dict[str, float]:
    if not rows:
        return {
            "n": 0,
            "hit_rate": 0.0,
            "mean_market_probability": 0.0,
            "mean_model_probability": 0.0,
            "mean_residual": 0.0,
            "mean_closing_odds": 0.0,
            "market_calibration_gap": 0.0,
            "model_calibration_gap": 0.0,
            "theoretical_roi_at_avg_close": 0.0,
            "mean_model_ev_at_close": 0.0,
        }

    hit_rate = sum(int(r.won) for r in rows) / len(rows)
    market_p = mean(r.market_probability for r in rows)
    model_p = mean(r.model_probability for r in rows)
    return {
        "n": len(rows),
        "hit_rate": hit_rate,
        "mean_market_probability": market_p,
        "mean_model_probability": model_p,
        "mean_residual": mean(r.residual for r in rows),
        "mean_closing_odds": mean(r.closing_odds for r in rows),
        "market_calibration_gap": hit_rate - market_p,
        "model_calibration_gap": hit_rate - model_p,
        "theoretical_roi_at_avg_close": mean(r.pnl_at_close for r in rows),
        "mean_model_ev_at_close": mean(r.model_ev_at_close for r in rows),
    }


def _odds_band(odds: float) -> str:
    if odds < 1.50:
        return "<1.50"
    if odds < 2.00:
        return "1.50-1.99"
    if odds < 3.00:
        return "2.00-2.99"
    return "3.00+"


def residual_threshold_report(
    rows: Iterable[ResidualObservation],
    thresholds: Sequence[float] = (0.02, 0.05, 0.08, 0.10, 0.15),
) -> Dict[str, object]:
    observations = list(rows)
    report: Dict[str, object] = {
        "all_max_residuals": summarize_observations(observations),
        "thresholds": {},
    }

    for threshold in thresholds:
        selected = [r for r in observations if r.residual >= threshold]
        by_outcome = {
            OUTCOME_NAMES[i]: summarize_observations([r for r in selected if r.selected_index == i])
            for i in range(3)
        }
        by_odds_band = {
            band: summarize_observations([r for r in selected if _odds_band(r.closing_odds) == band])
            for band in ("<1.50", "1.50-1.99", "2.00-2.99", "3.00+")
        }
        by_competition = {
            comp: summarize_observations([r for r in selected if r.competition == comp])
            for comp in sorted({r.competition for r in selected})
        }

        report["thresholds"][f"{threshold:.2f}"] = {
            "overall": summarize_observations(selected),
            "by_outcome": by_outcome,
            "by_odds_band": by_odds_band,
            "by_competition": by_competition,
        }

    return report
