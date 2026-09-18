from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from math import log
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

from .devig import devig
from .structural import DixonColesStructuralModel, MatchRecord, StructuralConfig


@dataclass(frozen=True)
class WalkForwardConfig:
    min_training_matches: int = 60
    rolling_days: Optional[int] = None
    structural_config: StructuralConfig = StructuralConfig()

    def __post_init__(self) -> None:
        if self.min_training_matches < 1:
            raise ValueError("min_training_matches must be >= 1")
        if self.rolling_days is not None and self.rolling_days < 1:
            raise ValueError("rolling_days must be >= 1 when supplied")


@dataclass(frozen=True)
class WalkForwardPrediction:
    date: datetime
    home_team: str
    away_team: str
    home_goals: int
    away_goals: int
    p_home: float
    p_draw: float
    p_away: float
    lambda_home: float
    lambda_away: float
    rho: float
    training_matches: int
    model_reference_date: datetime

    @property
    def outcome_index(self) -> int:
        if self.home_goals > self.away_goals:
            return 0
        if self.home_goals == self.away_goals:
            return 1
        return 2

    @property
    def probabilities(self) -> Tuple[float, float, float]:
        return self.p_home, self.p_draw, self.p_away


@dataclass(frozen=True)
class CalibrationBin:
    lower: float
    upper: float
    count: int
    mean_probability: float
    observed_rate: float


@dataclass(frozen=True)
class BacktestSummary:
    n: int
    brier_1x2: float
    log_loss_1x2: float
    accuracy: float


@dataclass(frozen=True)
class Historical1X2Quote:
    date: datetime
    home_team: str
    away_team: str
    home_odds: float
    draw_odds: float
    away_odds: float
    bookmaker: str = "market"
    snapshot_type: str = "CURRENT"

    def fair_probabilities(self, method: str = "shin") -> Tuple[float, float, float]:
        p = devig([self.home_odds, self.draw_odds, self.away_odds], method=method)
        return p[0], p[1], p[2]


@dataclass(frozen=True)
class BetResult:
    odds: float
    stake: float
    won: bool
    closing_odds: Optional[float] = None

    @property
    def pnl(self) -> float:
        return self.stake * (self.odds - 1.0) if self.won else -self.stake

    @property
    def price_clv(self) -> Optional[float]:
        if self.closing_odds is None or self.closing_odds <= 1:
            return None
        return self.odds / self.closing_odds - 1.0


@dataclass(frozen=True)
class Blended1X2Prediction:
    date: datetime
    home_team: str
    away_team: str
    model_weight: float
    p_home: float
    p_draw: float
    p_away: float
    raw_model: Tuple[float, float, float]
    market: Tuple[float, float, float]
    outcome_index: int
    history_size: int

    @property
    def probabilities(self) -> Tuple[float, float, float]:
        return self.p_home, self.p_draw, self.p_away


def walk_forward_predict(
    records: Iterable[MatchRecord],
    config: WalkForwardConfig | None = None,
) -> List[WalkForwardPrediction]:
    """Generate strictly out-of-sample predictions grouped by kickoff timestamp.

    All matches sharing an identical timestamp are predicted from the same training
    set. No result at that timestamp can leak into another prediction at the same
    timestamp.
    """
    cfg = config or WalkForwardConfig()
    rows = sorted(list(records), key=lambda r: r.date)
    if not rows:
        return []

    predictions: List[WalkForwardPrediction] = []
    unique_dates = sorted({r.date for r in rows})

    for prediction_time in unique_dates:
        test_rows = [r for r in rows if r.date == prediction_time]
        train_rows = [r for r in rows if r.date < prediction_time]
        if cfg.rolling_days is not None:
            lower = prediction_time - timedelta(days=cfg.rolling_days)
            train_rows = [r for r in train_rows if r.date >= lower]
        if len(train_rows) < cfg.min_training_matches:
            continue

        model = DixonColesStructuralModel(cfg.structural_config).fit(
            train_rows,
            as_of=prediction_time,
        )
        for r in test_rows:
            f = model.forecast(r.home_team, r.away_team)
            p = f.probabilities
            predictions.append(
                WalkForwardPrediction(
                    date=r.date,
                    home_team=r.home_team,
                    away_team=r.away_team,
                    home_goals=int(r.home_goals),
                    away_goals=int(r.away_goals),
                    p_home=p["home_win"],
                    p_draw=p["draw"],
                    p_away=p["away_win"],
                    lambda_home=f.lambdas.lambda_home,
                    lambda_away=f.lambdas.lambda_away,
                    rho=f.lambdas.rho,
                    training_matches=model.n_matches,
                    model_reference_date=model.reference_date,
                )
            )
    return predictions


def multiclass_brier(predictions: Sequence[WalkForwardPrediction]) -> float:
    if not predictions:
        raise ValueError("No predictions")
    total = 0.0
    for pred in predictions:
        y = [0.0, 0.0, 0.0]
        y[pred.outcome_index] = 1.0
        total += sum((p - o) ** 2 for p, o in zip(pred.probabilities, y))
    return total / len(predictions)


def multiclass_log_loss(predictions: Sequence[WalkForwardPrediction], eps: float = 1e-15) -> float:
    if not predictions:
        raise ValueError("No predictions")
    total = 0.0
    for pred in predictions:
        p = min(max(pred.probabilities[pred.outcome_index], eps), 1.0 - eps)
        total += -log(p)
    return total / len(predictions)


def summarize_predictions(predictions: Sequence[WalkForwardPrediction]) -> BacktestSummary:
    if not predictions:
        raise ValueError("No predictions")
    correct = 0
    for pred in predictions:
        pick = max(range(3), key=lambda i: pred.probabilities[i])
        correct += int(pick == pred.outcome_index)
    return BacktestSummary(
        n=len(predictions),
        brier_1x2=multiclass_brier(predictions),
        log_loss_1x2=multiclass_log_loss(predictions),
        accuracy=correct / len(predictions),
    )


def calibration_bins(
    probabilities: Sequence[float],
    outcomes: Sequence[int],
    bins: int = 10,
) -> List[CalibrationBin]:
    if len(probabilities) != len(outcomes):
        raise ValueError("probabilities and outcomes must have equal length")
    if not probabilities:
        return []
    if bins < 2:
        raise ValueError("bins must be >= 2")

    bucket: List[List[Tuple[float, int]]] = [[] for _ in range(bins)]
    for p, y in zip(probabilities, outcomes):
        if not 0 <= p <= 1:
            raise ValueError("probabilities must be in [0,1]")
        if y not in (0, 1):
            raise ValueError("outcomes must be binary")
        idx = min(int(p * bins), bins - 1)
        bucket[idx].append((p, y))

    out: List[CalibrationBin] = []
    for i, values in enumerate(bucket):
        if not values:
            continue
        out.append(
            CalibrationBin(
                lower=i / bins,
                upper=(i + 1) / bins,
                count=len(values),
                mean_probability=sum(p for p, _ in values) / len(values),
                observed_rate=sum(y for _, y in values) / len(values),
            )
        )
    return out


def geometric_blend_1x2(
    market: Sequence[float],
    model: Sequence[float],
    model_weight: float,
) -> Tuple[float, float, float]:
    if len(market) != 3 or len(model) != 3:
        raise ValueError("market and model must each contain 3 probabilities")
    if not 0 <= model_weight <= 1:
        raise ValueError("model_weight must be in [0,1]")
    if any(p <= 0 for p in market) or any(p <= 0 for p in model):
        raise ValueError("probabilities must be > 0")

    raw = [
        (mkt ** (1.0 - model_weight)) * (mod ** model_weight)
        for mkt, mod in zip(market, model)
    ]
    s = sum(raw)
    return raw[0] / s, raw[1] / s, raw[2] / s


def fit_blend_weight(
    market_probabilities: Sequence[Sequence[float]],
    model_probabilities: Sequence[Sequence[float]],
    outcomes: Sequence[int],
    step: float = 0.05,
) -> float:
    """Fit market/model weight by grid search on PAST labeled observations only."""
    if not (len(market_probabilities) == len(model_probabilities) == len(outcomes)):
        raise ValueError("Inputs must have equal length")
    if not outcomes:
        raise ValueError("No observations")
    if not 0 < step <= 1:
        raise ValueError("step must be in (0,1]")

    candidates = []
    w = 0.0
    while w < 1.0 + 1e-12:
        candidates.append(min(w, 1.0))
        w += step
    if candidates[-1] != 1.0:
        candidates.append(1.0)

    best_w = 0.0
    best_loss = float("inf")
    for w in candidates:
        loss = 0.0
        for mkt, mod, y in zip(market_probabilities, model_probabilities, outcomes):
            if y not in (0, 1, 2):
                raise ValueError("1X2 outcomes must be 0, 1 or 2")
            blended = geometric_blend_1x2(mkt, mod, w)
            loss += -log(max(blended[y], 1e-15))
        loss /= len(outcomes)
        if loss < best_loss - 1e-15:
            best_loss = loss
            best_w = w
    return best_w


def betting_summary(bets: Sequence[BetResult]) -> Dict[str, float]:
    if not bets:
        raise ValueError("No bets")
    total_stake = sum(b.stake for b in bets)
    total_pnl = sum(b.pnl for b in bets)
    if total_stake <= 0:
        raise ValueError("Total stake must be > 0")

    bankroll_curve = []
    cumulative = 0.0
    for b in bets:
        cumulative += b.pnl
        bankroll_curve.append(cumulative)

    peak = 0.0
    max_drawdown = 0.0
    for value in bankroll_curve:
        peak = max(peak, value)
        max_drawdown = max(max_drawdown, peak - value)

    clv = [b.price_clv for b in bets if b.price_clv is not None]
    return {
        "bets": float(len(bets)),
        "stake": total_stake,
        "pnl": total_pnl,
        "roi": total_pnl / total_stake,
        "yield": total_pnl / total_stake,
        "max_drawdown_units": max_drawdown,
        "mean_price_clv": sum(clv) / len(clv) if clv else float("nan"),
    }


def compare_prediction_to_quote(
    prediction: WalkForwardPrediction,
    quote: Historical1X2Quote,
    *,
    devig_method: str = "shin",
) -> Dict[str, Tuple[float, float, float]]:
    if (prediction.date, prediction.home_team, prediction.away_team) != (
        quote.date,
        quote.home_team,
        quote.away_team,
    ):
        raise ValueError("Prediction and quote refer to different fixtures")
    market = quote.fair_probabilities(devig_method)
    model = prediction.probabilities
    odds = (quote.home_odds, quote.draw_odds, quote.away_odds)
    edge = tuple(mod - mkt for mod, mkt in zip(model, market))
    ev = tuple(mod * odd - 1.0 for mod, odd in zip(model, odds))
    return {
        "market": market,
        "model": model,
        "edge_pp": edge,
        "ev": ev,
    }


def load_1x2_quotes_csv(path: str) -> List[Historical1X2Quote]:
    """Load a minimal historical 1X2 market CSV.

    Required columns:
    date, home_team, away_team, home_odds, draw_odds, away_odds
    Optional columns: bookmaker, snapshot_type
    """
    import csv

    out: List[Historical1X2Quote] = []
    with open(path, "r", encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(fh)
        required = {"date", "home_team", "away_team", "home_odds", "draw_odds", "away_odds"}
        missing = required - set(reader.fieldnames or [])
        if missing:
            raise ValueError(f"Odds CSV is missing required columns: {sorted(missing)}")
        for line_no, row in enumerate(reader, start=2):
            try:
                date = datetime.fromisoformat(row["date"].strip().replace("Z", "+00:00"))
                out.append(
                    Historical1X2Quote(
                        date=date,
                        home_team=row["home_team"].strip(),
                        away_team=row["away_team"].strip(),
                        home_odds=float(row["home_odds"]),
                        draw_odds=float(row["draw_odds"]),
                        away_odds=float(row["away_odds"]),
                        bookmaker=(row.get("bookmaker") or "market").strip(),
                        snapshot_type=(row.get("snapshot_type") or "CURRENT").strip(),
                    )
                )
            except Exception as exc:
                raise ValueError(f"Invalid odds row at CSV line {line_no}: {exc}") from exc
    return out


def walk_forward_market_blend(
    predictions: Sequence[WalkForwardPrediction],
    quotes: Sequence[Historical1X2Quote],
    *,
    min_history: int = 60,
    step: float = 0.05,
    devig_method: str = "shin",
) -> List[Blended1X2Prediction]:
    """Learn market-vs-model weight using only earlier out-of-sample observations.

    Predictions at the same timestamp share one weight learned from strictly earlier
    timestamps. Their outcomes are added to the calibration history only after the
    entire timestamp batch has been predicted.
    """
    if min_history < 1:
        raise ValueError("min_history must be >= 1")

    quote_map = {(q.date, q.home_team, q.away_team): q for q in quotes}
    pred_rows = sorted(predictions, key=lambda p: p.date)
    dates = sorted({p.date for p in pred_rows})

    hist_market: List[Tuple[float, float, float]] = []
    hist_model: List[Tuple[float, float, float]] = []
    hist_outcome: List[int] = []
    output: List[Blended1X2Prediction] = []

    for dt in dates:
        batch = [p for p in pred_rows if p.date == dt]
        matched = []
        for p in batch:
            q = quote_map.get((p.date, p.home_team, p.away_team))
            if q is None:
                continue
            matched.append((p, q.fair_probabilities(devig_method)))

        if len(hist_outcome) >= min_history:
            weight = fit_blend_weight(hist_market, hist_model, hist_outcome, step=step)
        else:
            weight = 0.0

        pending = []
        for p, market in matched:
            model = p.probabilities
            blended = geometric_blend_1x2(market, model, weight)
            output.append(
                Blended1X2Prediction(
                    date=p.date,
                    home_team=p.home_team,
                    away_team=p.away_team,
                    model_weight=weight,
                    p_home=blended[0],
                    p_draw=blended[1],
                    p_away=blended[2],
                    raw_model=model,
                    market=market,
                    outcome_index=p.outcome_index,
                    history_size=len(hist_outcome),
                )
            )
            pending.append((market, model, p.outcome_index))

        for market, model, outcome in pending:
            hist_market.append(market)
            hist_model.append(model)
            hist_outcome.append(outcome)

    return output


def blended_log_loss(predictions: Sequence[Blended1X2Prediction], eps: float = 1e-15) -> float:
    if not predictions:
        raise ValueError("No predictions")
    return sum(
        -log(min(max(p.probabilities[p.outcome_index], eps), 1.0 - eps))
        for p in predictions
    ) / len(predictions)
