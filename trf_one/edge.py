from __future__ import annotations

from dataclasses import dataclass, asdict
from math import log
from typing import Dict


def _check_probability(p: float, name: str) -> float:
    p = float(p)
    if not 0 < p < 1:
        raise ValueError(f"{name} must be in (0,1), got {p}")
    return p


def logit(p: float) -> float:
    p = _check_probability(p, "p")
    return log(p / (1.0 - p))


def logistic(x: float) -> float:
    from math import exp
    if x >= 0:
        z = exp(-x)
        return 1.0 / (1.0 + z)
    z = exp(x)
    return z / (1.0 + z)


def provisional_log_odds_blend(p_market: float, p_model: float, model_weight: float) -> float:
    """Blend market and model in log-odds space.

    model_weight MUST be treated as provisional until learned out of sample.
    0 -> market only, 1 -> model only.
    """
    if not 0 <= model_weight <= 1:
        raise ValueError("model_weight must be between 0 and 1")
    return logistic((1-model_weight)*logit(p_market) + model_weight*logit(p_model))


@dataclass(frozen=True)
class PickEvaluation:
    market_probability: float
    model_probability: float
    prudent_low: float
    prudent_high: float
    available_odds: float
    edge_pp: float
    break_even_probability: float
    fair_odds_model: float
    fair_odds_prudent: float
    ev_central: float
    ev_prudent: float
    decision_gate: str
    price_status: str

    def to_dict(self) -> Dict[str, float | str]:
        return asdict(self)


def evaluate_edge(
    *,
    market_probability: float,
    model_probability: float,
    prudent_low: float,
    prudent_high: float,
    available_odds: float,
) -> PickEvaluation:
    p_mkt = _check_probability(market_probability, "market_probability")
    p_mod = _check_probability(model_probability, "model_probability")
    p_low = _check_probability(prudent_low, "prudent_low")
    p_high = _check_probability(prudent_high, "prudent_high")
    if not p_low <= p_mod <= p_high:
        raise ValueError("Require prudent_low <= model_probability <= prudent_high")
    if available_odds <= 1.0:
        raise ValueError("available_odds must be > 1")

    breakeven = 1.0 / available_odds
    edge_pp = p_mod - p_mkt
    fair_model = 1.0 / p_mod
    fair_prudent = 1.0 / p_low
    ev_central = p_mod * available_odds - 1.0
    ev_prudent = p_low * available_odds - 1.0

    if ev_prudent > 0:
        gate = "ROBUST EDGE"
    elif ev_central > 0:
        gate = "FRAGILE EDGE"
    else:
        gate = "NO EDGE"

    if available_odds >= fair_prudent:
        price = "ABOVE PRUDENT FAIR"
    elif available_odds >= fair_model:
        price = "ABOVE MODEL FAIR / BELOW PRUDENT FAIR"
    else:
        price = "BELOW MODEL FAIR"

    return PickEvaluation(
        market_probability=p_mkt,
        model_probability=p_mod,
        prudent_low=p_low,
        prudent_high=p_high,
        available_odds=float(available_odds),
        edge_pp=edge_pp,
        break_even_probability=breakeven,
        fair_odds_model=fair_model,
        fair_odds_prudent=fair_prudent,
        ev_central=ev_central,
        ev_prudent=ev_prudent,
        decision_gate=gate,
        price_status=price,
    )


def brier_component(probability: float, outcome: int) -> float:
    p = _check_probability(probability, "probability")
    if outcome not in (0,1):
        raise ValueError("outcome must be 0 or 1")
    return (p-outcome)**2


def log_loss_component(probability: float, outcome: int, eps: float = 1e-15) -> float:
    p = min(max(float(probability), eps), 1.0-eps)
    if outcome not in (0,1):
        raise ValueError("outcome must be 0 or 1")
    return -(outcome*log(p) + (1-outcome)*log(1-p))
