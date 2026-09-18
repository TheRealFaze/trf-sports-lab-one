from __future__ import annotations

from dataclasses import dataclass
from math import exp, log1p, sqrt
from typing import Iterable, List, Tuple

from .providers.football_data_uk import ProcessMatchRecord
from .structural import MatchRecord


@dataclass(frozen=True)
class ProcessProxyConfig:
    learning_rate: float = 0.035
    max_iter: int = 500
    ridge: float = 0.02
    tol: float = 1e-8
    min_lambda: float = 0.05
    max_lambda: float = 5.5


class ProcessXGProxy:
    """League-specific Poisson proxy learned from shots, SOT and corners.

    It is not labelled as real xG. It creates an independent process target from
    publicly available match statistics, fitted strictly inside each training window.
    """

    def __init__(self, config: ProcessProxyConfig | None = None) -> None:
        self.config = config or ProcessProxyConfig()
        self.params = [0.0] * 5  # intercept, log1p(SOT), log1p(non-SOT shots), log1p(corners), home
        self.is_fitted = False

    @staticmethod
    def _features(shots: float, sot: float, corners: float, is_home: bool) -> Tuple[float, ...]:
        non_sot = max(0.0, shots - sot)
        return (1.0, log1p(sot), log1p(non_sot), log1p(corners), 1.0 if is_home else 0.0)

    def _predict_features(self, x: Tuple[float, ...]) -> float:
        z = sum(b * v for b, v in zip(self.params, x))
        z = min(max(z, -3.0), 2.5)
        lam = exp(z)
        return min(max(lam, self.config.min_lambda), self.config.max_lambda)

    def fit(self, records: Iterable[ProcessMatchRecord]) -> "ProcessXGProxy":
        rows = list(records)
        if len(rows) < 20:
            raise ValueError("Need at least 20 process matches")

        samples: List[Tuple[Tuple[float, ...], float]] = []
        for r in rows:
            samples.append((self._features(r.home_shots, r.home_sot, r.home_corners, True), r.home_goals))
            samples.append((self._features(r.away_shots, r.away_sot, r.away_corners, False), r.away_goals))

        total_goals = sum(y for _, y in samples)
        avg = max(total_goals / len(samples), 0.05)
        from math import log
        self.params[0] = log(avg)

        m = [0.0] * len(self.params)
        v = [0.0] * len(self.params)
        beta1, beta2, eps = 0.9, 0.999, 1e-8
        last_loss = None

        for step in range(1, self.config.max_iter + 1):
            grads = [0.0] * len(self.params)
            loss = 0.0
            for x, y in samples:
                lam = self._predict_features(x)
                loss += lam - y * log(max(lam, 1e-12))
                err = lam - y
                for j, value in enumerate(x):
                    grads[j] += err * value

            n = float(len(samples))
            for j in range(1, len(self.params)):
                loss += 0.5 * self.config.ridge * self.params[j] ** 2
                grads[j] += self.config.ridge * self.params[j]

            for j, g in enumerate(grads):
                g /= n
                m[j] = beta1 * m[j] + (1 - beta1) * g
                v[j] = beta2 * v[j] + (1 - beta2) * g * g
                mhat = m[j] / (1 - beta1 ** step)
                vhat = v[j] / (1 - beta2 ** step)
                self.params[j] -= self.config.learning_rate * mhat / (sqrt(vhat) + eps)

            normalized = loss / n
            if last_loss is not None and abs(last_loss - normalized) < self.config.tol:
                break
            last_loss = normalized

        self.is_fitted = True
        return self

    def proxy_pair(self, record: ProcessMatchRecord) -> Tuple[float, float]:
        if not self.is_fitted:
            raise RuntimeError("ProcessXGProxy must be fitted")
        home = self._predict_features(self._features(
            record.home_shots, record.home_sot, record.home_corners, True
        ))
        away = self._predict_features(self._features(
            record.away_shots, record.away_sot, record.away_corners, False
        ))
        return home, away

    def transform(self, records: Iterable[ProcessMatchRecord]) -> List[MatchRecord]:
        out = []
        for r in records:
            hxg, axg = self.proxy_pair(r)
            out.append(MatchRecord(
                date=r.date, home_team=r.home_team, away_team=r.away_team,
                home_goals=r.home_goals, away_goals=r.away_goals,
                home_xg=hxg, away_xg=axg,
            ))
        return out
