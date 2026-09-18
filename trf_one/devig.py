from __future__ import annotations

from math import sqrt
from typing import Iterable, List, Literal

Method = Literal["proportional", "power", "shin"]


def _validate_odds(odds: Iterable[float]) -> List[float]:
    xs = [float(x) for x in odds]
    if len(xs) < 2:
        raise ValueError("At least two mutually exclusive outcomes are required.")
    if any(x <= 1.0 for x in xs):
        raise ValueError("Decimal odds must be > 1.0.")
    return xs


def proportional_devig(odds: Iterable[float]) -> List[float]:
    """Normalize raw implied probabilities so they sum to 1."""
    xs = _validate_odds(odds)
    q = [1.0 / x for x in xs]
    s = sum(q)
    return [x / s for x in q]


def power_devig(odds: Iterable[float], tol: float = 1e-12, max_iter: int = 200) -> List[float]:
    """Power de-vig: p_i = q_i^k with k chosen so sum(p_i)=1."""
    xs = _validate_odds(odds)
    q = [1.0 / x for x in xs]

    lo, hi = 0.01, 20.0
    for _ in range(max_iter):
        mid = (lo + hi) / 2.0
        s = sum(x**mid for x in q)
        if abs(s - 1.0) < tol:
            break
        if s > 1.0:
            lo = mid
        else:
            hi = mid
    k = (lo + hi) / 2.0
    p = [x**k for x in q]
    total = sum(p)
    return [x / total for x in p]


def _shin_probs_for_z(q: List[float], z: float) -> List[float]:
    """Shin probabilities for fixed insider parameter z."""
    Q = sum(q)
    if z >= 1.0:
        z = 1.0 - 1e-12
    denom = 2.0 * (1.0 - z)
    return [
        (sqrt(z * z + 4.0 * (1.0 - z) * (x * x) / Q) - z) / denom
        for x in q
    ]


def shin_devig(odds: Iterable[float], tol: float = 1e-12, max_iter: int = 200) -> List[float]:
    """Estimate fair probabilities with Shin's insider-trading correction.

    Falls back to proportional de-vig if no stable root is found. This is a
    market-pricing aid, not a claim that Shin is universally optimal.
    """
    xs = _validate_odds(odds)
    q = [1.0 / x for x in xs]

    def f(z: float) -> float:
        return sum(_shin_probs_for_z(q, z)) - 1.0

    lo, hi = 0.0, 0.999999
    flo, fhi = f(lo), f(hi)
    if flo == 0:
        return _shin_probs_for_z(q, lo)
    if flo * fhi > 0:
        return proportional_devig(xs)

    for _ in range(max_iter):
        mid = (lo + hi) / 2.0
        fm = f(mid)
        if abs(fm) < tol:
            probs = _shin_probs_for_z(q, mid)
            s = sum(probs)
            return [p / s for p in probs]
        if flo * fm <= 0:
            hi = mid
            fhi = fm
        else:
            lo = mid
            flo = fm

    probs = _shin_probs_for_z(q, (lo + hi) / 2.0)
    s = sum(probs)
    if not (0.999 <= s <= 1.001) or any(p <= 0 for p in probs):
        return proportional_devig(xs)
    return [p / s for p in probs]


def devig(odds: Iterable[float], method: Method = "shin") -> List[float]:
    if method == "proportional":
        return proportional_devig(odds)
    if method == "power":
        return power_devig(odds)
    if method == "shin":
        return shin_devig(odds)
    raise ValueError(f"Unknown de-vig method: {method}")
