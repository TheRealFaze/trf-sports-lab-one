from __future__ import annotations

from math import exp, factorial
from typing import Dict, List, Tuple


def poisson_pmf(k: int, lam: float) -> float:
    if lam <= 0:
        raise ValueError("lambda must be > 0")
    if k < 0:
        return 0.0
    return exp(-lam) * lam**k / factorial(k)


def dixon_coles_tau(home_goals: int, away_goals: int, lambda_home: float, lambda_away: float, rho: float) -> float:
    if home_goals == 0 and away_goals == 0:
        return 1.0 - (lambda_home * lambda_away * rho)
    if home_goals == 0 and away_goals == 1:
        return 1.0 + (lambda_home * rho)
    if home_goals == 1 and away_goals == 0:
        return 1.0 + (lambda_away * rho)
    if home_goals == 1 and away_goals == 1:
        return 1.0 - rho
    return 1.0


def score_matrix(lambda_home: float, lambda_away: float, max_goals: int = 10, rho: float = 0.0) -> List[List[float]]:
    """Return normalized scoreline probabilities under Poisson/Dixon-Coles."""
    if max_goals < 5:
        raise ValueError("max_goals should normally be at least 5")
    h = [poisson_pmf(i, lambda_home) for i in range(max_goals + 1)]
    a = [poisson_pmf(j, lambda_away) for j in range(max_goals + 1)]
    matrix: List[List[float]] = []
    total = 0.0
    for i in range(max_goals + 1):
        row = []
        for j in range(max_goals + 1):
            p = h[i] * a[j] * dixon_coles_tau(i, j, lambda_home, lambda_away, rho)
            p = max(0.0, p)
            row.append(p)
            total += p
        matrix.append(row)
    if total <= 0:
        raise ValueError("Invalid probability matrix")
    return [[p / total for p in row] for row in matrix]


def market_probs_from_matrix(matrix: List[List[float]]) -> Dict[str, float]:
    home = draw = away = btts = 0.0
    over_05 = over_15 = over_25 = over_35 = 0.0
    home_score = away_score = 0.0

    for i, row in enumerate(matrix):
        for j, p in enumerate(row):
            if i > j:
                home += p
            elif i == j:
                draw += p
            else:
                away += p

            total = i + j
            if total >= 1:
                over_05 += p
            if total >= 2:
                over_15 += p
            if total >= 3:
                over_25 += p
            if total >= 4:
                over_35 += p
            if i > 0 and j > 0:
                btts += p
            if i > 0:
                home_score += p
            if j > 0:
                away_score += p

    return {
        "home_win": home,
        "draw": draw,
        "away_win": away,
        "home_or_draw": home + draw,
        "away_or_draw": away + draw,
        "over_0_5": over_05,
        "over_1_5": over_15,
        "over_2_5": over_25,
        "over_3_5": over_35,
        "btts_yes": btts,
        "home_to_score": home_score,
        "away_to_score": away_score,
    }


def expected_goals_from_matrix(matrix: List[List[float]]) -> Tuple[float, float]:
    eh = ea = 0.0
    for i, row in enumerate(matrix):
        for j, p in enumerate(row):
            eh += i * p
            ea += j * p
    return eh, ea
