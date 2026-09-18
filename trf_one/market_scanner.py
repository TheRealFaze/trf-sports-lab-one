from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

from .devig import devig
from .backtest import geometric_blend_1x2


@dataclass(frozen=True)
class MarketOutcomeInput:
    fixture_id: str
    market_group: str
    selection: str
    consensus_odds: float
    execution_odds: float
    competition: str = ""
    kickoff: str = ""
    home_team: str = ""
    away_team: str = ""
    consensus_source: str = "consensus"
    execution_source: str = "execution"
    model_probability: Optional[float] = None

    def __post_init__(self) -> None:
        if not self.fixture_id:
            raise ValueError("fixture_id is required")
        if not self.market_group:
            raise ValueError("market_group is required")
        if not self.selection:
            raise ValueError("selection is required")
        if self.consensus_odds <= 1:
            raise ValueError("consensus_odds must be > 1")
        if self.execution_odds <= 1:
            raise ValueError("execution_odds must be > 1")
        if self.model_probability is not None and not 0 < self.model_probability < 1:
            raise ValueError("model_probability must be in (0,1)")


@dataclass(frozen=True)
class ScannerConfig:
    devig_method: str = "shin"
    min_prudent_ev: float = 0.02
    model_weight: float = 0.0
    model_veto_pp: float = 0.10
    reject_same_source: bool = True

    def __post_init__(self) -> None:
        if not 0 <= self.model_weight <= 1:
            raise ValueError("model_weight must be in [0,1]")
        if self.min_prudent_ev < 0:
            raise ValueError("min_prudent_ev must be >= 0")
        if self.model_veto_pp < 0:
            raise ValueError("model_veto_pp must be >= 0")


@dataclass(frozen=True)
class ScannedOutcome:
    fixture_id: str
    competition: str
    kickoff: str
    home_team: str
    away_team: str
    market_group: str
    selection: str
    consensus_source: str
    execution_source: str
    consensus_odds: float
    execution_odds: float
    market_fair_probability: float
    market_fair_odds: float
    model_probability: Optional[float]
    central_probability: float
    prudent_probability: float
    model_residual_pp: Optional[float]
    price_ev_market: float
    ev_central: float
    ev_prudent: float
    decision: str
    tier: str
    reason: str

    def to_dict(self) -> Dict[str, object]:
        return asdict(self)


def _normalize_probs(values: Sequence[float]) -> Tuple[float, ...]:
    if any(v <= 0 for v in values):
        raise ValueError("probabilities must be > 0")
    s = sum(values)
    if s <= 0:
        raise ValueError("probability sum must be > 0")
    return tuple(v / s for v in values)


def _blend_group(
    market_probs: Sequence[float],
    model_probs: Sequence[Optional[float]],
    model_weight: float,
) -> Tuple[float, ...]:
    if model_weight <= 0 or any(p is None for p in model_probs):
        return tuple(market_probs)
    model = _normalize_probs([float(p) for p in model_probs if p is not None])
    raw = [
        (mkt ** (1.0 - model_weight)) * (mod ** model_weight)
        for mkt, mod in zip(market_probs, model)
    ]
    return _normalize_probs(raw)


def scan_market_group(
    rows: Sequence[MarketOutcomeInput],
    config: ScannerConfig | None = None,
) -> List[ScannedOutcome]:
    cfg = config or ScannerConfig()
    if len(rows) < 2:
        raise ValueError("A mutually exclusive market group needs at least two outcomes")

    fixture_ids = {r.fixture_id for r in rows}
    groups = {r.market_group for r in rows}
    if len(fixture_ids) != 1 or len(groups) != 1:
        raise ValueError("rows must belong to one fixture and one market_group")

    market_probs = devig([r.consensus_odds for r in rows], method=cfg.devig_method)
    central_probs = _blend_group(
        market_probs,
        [r.model_probability for r in rows],
        cfg.model_weight,
    )

    out: List[ScannedOutcome] = []
    for row, p_market, p_central in zip(rows, market_probs, central_probs):
        p_model = row.model_probability
        residual = None if p_model is None else p_model - p_market

        # Market remains the strong prior. If an experimental model is blended in,
        # prudent probability never exceeds the de-vigged market estimate.
        p_prudent = min(p_market, p_central)

        market_ev = p_market * row.execution_odds - 1.0
        ev_central = p_central * row.execution_odds - 1.0
        ev_prudent = p_prudent * row.execution_odds - 1.0

        same_source = (
            row.consensus_source.strip().lower()
            == row.execution_source.strip().lower()
        )
        model_veto = residual is not None and residual < -cfg.model_veto_pp

        if cfg.reject_same_source and same_source:
            decision = "PASS"
            tier = "PASS"
            reason = "execution source equals consensus source; no independent price benchmark"
        elif model_veto:
            decision = "PASS"
            tier = "PASS"
            reason = f"experimental model contradicts market by more than {cfg.model_veto_pp:.1%}"
        elif ev_prudent >= cfg.min_prudent_ev:
            decision = "QUALIFY"
            tier = "SHADOW VALUE"
            reason = "execution price exceeds de-vigged consensus fair price by required margin"
        else:
            decision = "PASS"
            tier = "PASS"
            reason = "execution price does not clear prudent EV threshold"

        out.append(
            ScannedOutcome(
                fixture_id=row.fixture_id,
                competition=row.competition,
                kickoff=row.kickoff,
                home_team=row.home_team,
                away_team=row.away_team,
                market_group=row.market_group,
                selection=row.selection,
                consensus_source=row.consensus_source,
                execution_source=row.execution_source,
                consensus_odds=row.consensus_odds,
                execution_odds=row.execution_odds,
                market_fair_probability=p_market,
                market_fair_odds=1.0 / p_market,
                model_probability=p_model,
                central_probability=p_central,
                prudent_probability=p_prudent,
                model_residual_pp=residual,
                price_ev_market=market_ev,
                ev_central=ev_central,
                ev_prudent=ev_prudent,
                decision=decision,
                tier=tier,
                reason=reason,
            )
        )
    return out


def scan_markets(
    rows: Iterable[MarketOutcomeInput],
    config: ScannerConfig | None = None,
) -> List[ScannedOutcome]:
    grouped: Dict[Tuple[str, str], List[MarketOutcomeInput]] = {}
    for row in rows:
        grouped.setdefault((row.fixture_id, row.market_group), []).append(row)

    out: List[ScannedOutcome] = []
    for key in sorted(grouped):
        out.extend(scan_market_group(grouped[key], config=config))
    return sorted(out, key=lambda r: r.ev_prudent, reverse=True)


def derive_double_chance_probabilities(
    selections: Mapping[str, float],
) -> Dict[str, float]:
    """Derive 1X / X2 / 12 fair probabilities from a de-vigged 1X2 market.

    Accepted home aliases: H, HOME, 1
    draw aliases: D, DRAW, X
    away aliases: A, AWAY, 2
    """
    normalized = {str(k).strip().upper(): float(v) for k, v in selections.items()}

    def pick(aliases: Sequence[str]) -> float:
        for key in aliases:
            if key in normalized:
                return normalized[key]
        raise ValueError(f"Missing 1X2 selection; expected one of {aliases}")

    h = pick(("H", "HOME", "1"))
    d = pick(("D", "DRAW", "X"))
    a = pick(("A", "AWAY", "2"))
    total = h + d + a
    if abs(total - 1.0) > 1e-6:
        h, d, a = (x / total for x in (h, d, a))
    return {"1X": h + d, "X2": d + a, "12": h + a}


@dataclass(frozen=True)
class DerivedPriceAssessment:
    fixture_id: str
    market_group: str
    selection: str
    fair_probability: float
    fair_odds: float
    execution_odds: float
    ev: float
    decision: str
    tier: str

    def to_dict(self) -> Dict[str, object]:
        return asdict(self)


def assess_derived_price(
    *,
    fixture_id: str,
    market_group: str,
    selection: str,
    fair_probability: float,
    execution_odds: float,
    min_ev: float = 0.02,
) -> DerivedPriceAssessment:
    if not 0 < fair_probability < 1:
        raise ValueError("fair_probability must be in (0,1)")
    if execution_odds <= 1:
        raise ValueError("execution_odds must be > 1")
    ev = fair_probability * execution_odds - 1.0
    qualify = ev >= min_ev
    return DerivedPriceAssessment(
        fixture_id=fixture_id,
        market_group=market_group,
        selection=selection,
        fair_probability=fair_probability,
        fair_odds=1.0 / fair_probability,
        execution_odds=execution_odds,
        ev=ev,
        decision="QUALIFY" if qualify else "PASS",
        tier="SHADOW VALUE" if qualify else "PASS",
    )
