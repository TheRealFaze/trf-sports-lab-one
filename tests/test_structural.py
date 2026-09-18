from datetime import datetime, timedelta, timezone

from trf_one.structural import DixonColesStructuralModel, MatchRecord, StructuralConfig


def synthetic_records():
    start = datetime(2025, 1, 1, tzinfo=timezone.utc)
    teams = ["Alpha", "Beta", "Gamma", "Delta"]
    rows = []
    strengths = {"Alpha": 1.9, "Beta": 1.4, "Gamma": 1.0, "Delta": 0.7}
    defence = {"Alpha": 0.75, "Beta": 1.0, "Gamma": 1.15, "Delta": 1.35}
    day = 0
    for cycle in range(12):
        for home in teams:
            for away in teams:
                if home == away:
                    continue
                lh = strengths[home] * defence[away] * 1.12
                la = strengths[away] * defence[home]
                hg = int(round(lh + (0.2 if (cycle + day) % 3 == 0 else -0.1)))
                ag = int(round(la + (0.15 if (cycle + day) % 4 == 0 else -0.1)))
                rows.append(
                    MatchRecord(
                        date=start + timedelta(days=day),
                        home_team=home,
                        away_team=away,
                        home_goals=max(0, hg),
                        away_goals=max(0, ag),
                    )
                )
                day += 2
    return rows


def test_fit_and_predict_strength_ordering():
    model = DixonColesStructuralModel(
        StructuralConfig(max_iter=1800, learning_rate=0.03, half_life_days=500, ridge=0.05)
    ).fit(synthetic_records())
    pred = model.predict_lambdas("Alpha", "Delta")
    reverse = model.predict_lambdas("Delta", "Alpha")
    assert model.is_fitted
    assert pred.lambda_home > pred.lambda_away
    assert pred.lambda_home > reverse.lambda_home
    assert pred.lambda_home_low < pred.lambda_home < pred.lambda_home_high


def test_forecast_probabilities_are_valid():
    model = DixonColesStructuralModel(
        StructuralConfig(max_iter=1200, learning_rate=0.03)
    ).fit(synthetic_records())
    p = model.forecast("Alpha", "Beta").probabilities
    assert abs(p["home_win"] + p["draw"] + p["away_win"] - 1.0) < 1e-9
    assert 0 < p["btts_yes"] < 1


def test_as_of_cutoff_prevents_future_leakage():
    rows = synthetic_records()
    cutoff = rows[len(rows)//2].date
    model = DixonColesStructuralModel(StructuralConfig(max_iter=800)).fit(rows, as_of=cutoff)
    assert model.reference_date == cutoff
    assert model.n_matches == sum(1 for r in rows if r.date < cutoff)


def test_unseen_team_has_wider_uncertainty():
    model = DixonColesStructuralModel(StructuralConfig(max_iter=1000)).fit(synthetic_records())
    known = model.predict_lambdas("Alpha", "Beta")
    unseen = model.predict_lambdas("Alpha", "New Club")
    known_width = known.lambda_home_high / known.lambda_home_low
    unseen_width = unseen.lambda_home_high / unseen.lambda_home_low
    assert unseen_width > known_width
