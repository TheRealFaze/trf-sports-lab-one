from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from math import exp, log, sqrt
from statistics import mean
from typing import Dict, Iterable, List, Literal, Optional, Sequence, Tuple

from .poisson import market_probs_from_matrix, score_matrix

TargetMode = Literal["goals", "xg", "xg_blend"]


@dataclass(frozen=True)
class MatchRecord:
    date: datetime
    home_team: str
    away_team: str
    home_goals: float
    away_goals: float
    home_xg: Optional[float] = None
    away_xg: Optional[float] = None

    def __post_init__(self) -> None:
        if not self.home_team or not self.away_team:
            raise ValueError("Team names must be non-empty")
        if self.home_team == self.away_team:
            raise ValueError("home_team and away_team must differ")
        for name, value in (("home_goals", self.home_goals), ("away_goals", self.away_goals)):
            if value < 0:
                raise ValueError(f"{name} must be >= 0")
        for name, value in (("home_xg", self.home_xg), ("away_xg", self.away_xg)):
            if value is not None and value < 0:
                raise ValueError(f"{name} must be >= 0 when supplied")


@dataclass(frozen=True)
class StructuralConfig:
    half_life_days: float = 180.0
    ridge: float = 0.03
    learning_rate: float = 0.035
    max_iter: int = 2500
    tol: float = 1e-8
    target_mode: TargetMode = "goals"
    xg_blend_weight: float = 0.50
    rho_min: float = -0.20
    rho_max: float = 0.20
    rho_steps: int = 81
    uncertainty_scale: float = 0.95
    max_goals: int = 10

    def __post_init__(self) -> None:
        if self.half_life_days <= 0:
            raise ValueError("half_life_days must be > 0")
        if self.ridge < 0:
            raise ValueError("ridge must be >= 0")
        if self.learning_rate <= 0:
            raise ValueError("learning_rate must be > 0")
        if self.max_iter < 1:
            raise ValueError("max_iter must be >= 1")
        if not 0 <= self.xg_blend_weight <= 1:
            raise ValueError("xg_blend_weight must be in [0,1]")
        if self.rho_min >= self.rho_max:
            raise ValueError("rho_min must be < rho_max")
        if self.rho_steps < 3:
            raise ValueError("rho_steps must be >= 3")
        if self.uncertainty_scale <= 0:
            raise ValueError("uncertainty_scale must be > 0")


@dataclass(frozen=True)
class LambdaPrediction:
    home_team: str
    away_team: str
    lambda_home: float
    lambda_away: float
    lambda_home_low: float
    lambda_home_high: float
    lambda_away_low: float
    lambda_away_high: float
    rho: float
    home_effective_matches: float
    away_effective_matches: float

    def to_dict(self) -> Dict[str, float | str]:
        return asdict(self)


@dataclass(frozen=True)
class StructuralForecast:
    lambdas: LambdaPrediction
    probabilities: Dict[str, float]

    def to_dict(self) -> Dict[str, object]:
        return {"lambdas": self.lambdas.to_dict(), "probabilities": dict(self.probabilities)}


class DixonColesStructuralModel:
    """Time-decayed Poisson team-strength model with Dixon-Coles low-score correction.

    The model fits team attack and defence parameters plus an intercept and home
    advantage using weighted Poisson likelihood. rho is selected on a deterministic
    grid from weighted Dixon-Coles low-score likelihood.

    This is a reproducible v0.2 baseline designed for walk-forward fitting with
    strict as_of cutoffs.
    """

    def __init__(self, config: StructuralConfig | None = None) -> None:
        self.config = config or StructuralConfig()
        self.is_fitted = False
        self.teams: List[str] = []
        self.attack: Dict[str, float] = {}
        self.defence: Dict[str, float] = {}
        self.intercept = 0.0
        self.home_advantage = 0.0
        self.rho = 0.0
        self.reference_date: Optional[datetime] = None
        self.effective_matches: Dict[str, float] = {}
        self.training_loss: Optional[float] = None
        self.n_matches = 0

    @staticmethod
    def _as_utc(dt: datetime) -> datetime:
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)

    def _target(self, record: MatchRecord) -> Tuple[float, float]:
        mode = self.config.target_mode
        if mode == "goals":
            return float(record.home_goals), float(record.away_goals)
        if mode == "xg":
            if record.home_xg is None or record.away_xg is None:
                raise ValueError("target_mode='xg' requires home_xg and away_xg for every training row")
            return float(record.home_xg), float(record.away_xg)
        if mode == "xg_blend":
            if record.home_xg is None or record.away_xg is None:
                raise ValueError("target_mode='xg_blend' requires home_xg and away_xg for every training row")
            w = self.config.xg_blend_weight
            return (
                (1.0 - w) * float(record.home_goals) + w * float(record.home_xg),
                (1.0 - w) * float(record.away_goals) + w * float(record.away_xg),
            )
        raise ValueError(f"Unknown target_mode: {mode}")

    def _weight(self, record_date: datetime, reference_date: datetime) -> float:
        age_days = max(0.0, (reference_date - self._as_utc(record_date)).total_seconds() / 86400.0)
        return 0.5 ** (age_days / self.config.half_life_days)

    @staticmethod
    def _poisson_nll(y: float, lam: float) -> float:
        return lam - y * log(max(lam, 1e-15))

    def _select_training_rows(
        self,
        records: Iterable[MatchRecord],
        as_of: Optional[datetime],
    ) -> Tuple[List[MatchRecord], datetime]:
        rows = list(records)
        if not rows:
            raise ValueError("No training records supplied")
        if as_of is not None:
            cutoff = self._as_utc(as_of)
            rows = [r for r in rows if self._as_utc(r.date) < cutoff]
            if not rows:
                raise ValueError("No records exist strictly before as_of cutoff")
            reference = cutoff
        else:
            reference = max(self._as_utc(r.date) for r in rows)
        rows.sort(key=lambda r: self._as_utc(r.date))
        return rows, reference

    def fit(
        self,
        records: Iterable[MatchRecord],
        *,
        as_of: Optional[datetime] = None,
    ) -> "DixonColesStructuralModel":
        rows, reference = self._select_training_rows(records, as_of)
        teams = sorted({r.home_team for r in rows} | {r.away_team for r in rows})
        if len(teams) < 2:
            raise ValueError("Need at least two teams")

        idx = {team: i for i, team in enumerate(teams)}
        n = len(teams)
        attack = [0.0] * n
        defence = [0.0] * n

        weighted_home = weighted_away = total_w = 0.0
        eff = [0.0] * n
        prepared: List[Tuple[int, int, float, float, float, float, float]] = []
        for r in rows:
            hi, ai = idx[r.home_team], idx[r.away_team]
            yh, ya = self._target(r)
            w = self._weight(r.date, reference)
            prepared.append((hi, ai, yh, ya, w, float(r.home_goals), float(r.away_goals)))
            weighted_home += w * yh
            weighted_away += w * ya
            total_w += w
            eff[hi] += w
            eff[ai] += w

        if total_w <= 0:
            raise ValueError("Training weights collapsed to zero")

        avg_home = max(weighted_home / total_w, 0.05)
        avg_away = max(weighted_away / total_w, 0.05)
        intercept = log(sqrt(avg_home * avg_away))
        home_adv = 0.5 * log(avg_home / avg_away)

        dim = 2 * n + 2
        m = [0.0] * dim
        v = [0.0] * dim
        beta1, beta2, eps = 0.9, 0.999, 1e-8
        last_loss: Optional[float] = None

        for step in range(1, self.config.max_iter + 1):
            ga = [0.0] * n
            gd = [0.0] * n
            gi = 0.0
            gh = 0.0
            loss = 0.0

            for hi, ai, yh, ya, w, _, _ in prepared:
                eta_h = intercept + home_adv + attack[hi] - defence[ai]
                eta_a = intercept + attack[ai] - defence[hi]
                eta_h = min(max(eta_h, -4.0), 4.0)
                eta_a = min(max(eta_a, -4.0), 4.0)
                lh, la = exp(eta_h), exp(eta_a)

                loss += w * (self._poisson_nll(yh, lh) + self._poisson_nll(ya, la))
                err_h = w * (lh - yh)
                err_a = w * (la - ya)

                ga[hi] += err_h
                gd[ai] -= err_h
                ga[ai] += err_a
                gd[hi] -= err_a
                gi += err_h + err_a
                gh += err_h

            reg = self.config.ridge
            for i in range(n):
                loss += 0.5 * reg * (attack[i] ** 2 + defence[i] ** 2)
                ga[i] += reg * attack[i]
                gd[i] += reg * defence[i]

            scale = 1.0 / total_w
            grads = [g * scale for g in ga] + [g * scale for g in gd] + [gi * scale, gh * scale]
            params = attack + defence + [intercept, home_adv]

            lr = self.config.learning_rate
            for j, g in enumerate(grads):
                m[j] = beta1 * m[j] + (1.0 - beta1) * g
                v[j] = beta2 * v[j] + (1.0 - beta2) * (g * g)
                mhat = m[j] / (1.0 - beta1 ** step)
                vhat = v[j] / (1.0 - beta2 ** step)
                params[j] -= lr * mhat / (sqrt(vhat) + eps)

            attack = params[:n]
            defence = params[n:2*n]
            intercept, home_adv = params[-2], params[-1]

            a_mean = mean(attack)
            d_mean = mean(defence)
            attack = [x - a_mean for x in attack]
            defence = [x - d_mean for x in defence]
            intercept += a_mean - d_mean

            normalized_loss = loss * scale
            if last_loss is not None and abs(last_loss - normalized_loss) < self.config.tol:
                last_loss = normalized_loss
                break
            last_loss = normalized_loss

        self.teams = teams
        self.attack = {team: attack[idx[team]] for team in teams}
        self.defence = {team: defence[idx[team]] for team in teams}
        self.intercept = float(intercept)
        self.home_advantage = float(home_adv)
        self.reference_date = reference
        self.effective_matches = {team: eff[idx[team]] for team in teams}
        self.training_loss = float(last_loss if last_loss is not None else 0.0)
        self.n_matches = len(rows)
        self.rho = self._fit_rho(prepared)
        self.is_fitted = True
        return self

    def _fit_rho(
        self,
        prepared: Sequence[Tuple[int, int, float, float, float, float, float]],
    ) -> float:
        grid = [
            self.config.rho_min
            + i * (self.config.rho_max - self.config.rho_min) / (self.config.rho_steps - 1)
            for i in range(self.config.rho_steps)
        ]
        best_rho = 0.0
        best_ll = float("-inf")

        for rho in grid:
            ll = 0.0
            valid = True
            for hi, ai, _, _, w, gh, ga in prepared:
                if gh > 1 or ga > 1:
                    continue
                home = self.teams[hi]
                away = self.teams[ai]
                lh, la = self._raw_lambdas(home, away)
                if gh == 0 and ga == 0:
                    tau = 1.0 - lh * la * rho
                elif gh == 0 and ga == 1:
                    tau = 1.0 + lh * rho
                elif gh == 1 and ga == 0:
                    tau = 1.0 + la * rho
                else:
                    tau = 1.0 - rho
                if tau <= 0:
                    valid = False
                    break
                ll += w * log(tau)
            if valid and ll > best_ll:
                best_ll = ll
                best_rho = rho
        return float(best_rho)

    def _raw_lambdas(self, home_team: str, away_team: str) -> Tuple[float, float]:
        ah = self.attack.get(home_team, 0.0)
        dh = self.defence.get(home_team, 0.0)
        aa = self.attack.get(away_team, 0.0)
        da = self.defence.get(away_team, 0.0)
        lh = exp(self.intercept + self.home_advantage + ah - da)
        la = exp(self.intercept + aa - dh)
        return lh, la

    def predict_lambdas(self, home_team: str, away_team: str) -> LambdaPrediction:
        if not self.is_fitted:
            raise RuntimeError("Model must be fitted before prediction")
        if home_team == away_team:
            raise ValueError("home_team and away_team must differ")

        lh, la = self._raw_lambdas(home_team, away_team)
        eh = self.effective_matches.get(home_team, 0.0)
        ea = self.effective_matches.get(away_team, 0.0)
        sigma = self.config.uncertainty_scale * sqrt(1.0 / (eh + 1.0) + 1.0 / (ea + 1.0))
        mult = exp(1.96 * sigma)

        return LambdaPrediction(
            home_team=home_team,
            away_team=away_team,
            lambda_home=lh,
            lambda_away=la,
            lambda_home_low=lh / mult,
            lambda_home_high=lh * mult,
            lambda_away_low=la / mult,
            lambda_away_high=la * mult,
            rho=self.rho,
            home_effective_matches=eh,
            away_effective_matches=ea,
        )

    def forecast(self, home_team: str, away_team: str) -> StructuralForecast:
        pred = self.predict_lambdas(home_team, away_team)
        matrix = score_matrix(
            pred.lambda_home,
            pred.lambda_away,
            max_goals=self.config.max_goals,
            rho=pred.rho,
        )
        return StructuralForecast(pred, market_probs_from_matrix(matrix))

    def snapshot(self) -> Dict[str, object]:
        if not self.is_fitted:
            raise RuntimeError("Model must be fitted before snapshot")
        return {
            "schema_version": "0.2.0",
            "config": asdict(self.config),
            "teams": list(self.teams),
            "attack": dict(self.attack),
            "defence": dict(self.defence),
            "intercept": self.intercept,
            "home_advantage": self.home_advantage,
            "rho": self.rho,
            "reference_date": self.reference_date.isoformat() if self.reference_date else None,
            "effective_matches": dict(self.effective_matches),
            "training_loss": self.training_loss,
            "n_matches": self.n_matches,
        }

    @classmethod
    def from_snapshot(cls, payload: Dict[str, object]) -> "DixonColesStructuralModel":
        if payload.get("schema_version") != "0.2.0":
            raise ValueError("Unsupported structural model snapshot schema")
        config_raw = payload.get("config")
        if not isinstance(config_raw, dict):
            raise ValueError("Snapshot is missing config")

        model = cls(StructuralConfig(**config_raw))
        model.teams = [str(x) for x in payload.get("teams", [])]
        model.attack = {str(k): float(v) for k, v in dict(payload.get("attack", {})).items()}
        model.defence = {str(k): float(v) for k, v in dict(payload.get("defence", {})).items()}
        model.intercept = float(payload["intercept"])
        model.home_advantage = float(payload["home_advantage"])
        model.rho = float(payload["rho"])
        ref = payload.get("reference_date")
        model.reference_date = datetime.fromisoformat(str(ref)) if ref else None
        model.effective_matches = {
            str(k): float(v) for k, v in dict(payload.get("effective_matches", {})).items()
        }
        model.training_loss = (
            float(payload["training_loss"]) if payload.get("training_loss") is not None else None
        )
        model.n_matches = int(payload.get("n_matches", 0))
        model.is_fitted = True
        return model
