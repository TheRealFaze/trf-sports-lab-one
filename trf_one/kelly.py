from __future__ import annotations


def kelly_fraction(decimal_odds: float, probability: float, fraction: float = 0.25, cap: float | None = None) -> float:
    """Conservative fractional Kelly. Returns 0 when edge is non-positive."""
    if decimal_odds <= 1:
        raise ValueError("decimal_odds must be > 1")
    if not 0 < probability < 1:
        raise ValueError("probability must be in (0,1)")
    if not 0 < fraction <= 1:
        raise ValueError("fraction must be in (0,1]")
    b = decimal_odds - 1.0
    q = 1.0 - probability
    full = (b*probability - q) / b
    stake_frac = max(0.0, full) * fraction
    if cap is not None:
        stake_frac = min(stake_frac, cap)
    return stake_frac
