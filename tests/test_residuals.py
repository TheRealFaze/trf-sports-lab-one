from trf_one.residuals import max_positive_residual, residual_threshold_report


def test_max_positive_residual_selects_largest_gap():
    r = max_positive_residual(
        competition="E0",
        season="2024/25",
        model_probabilities=(0.55, 0.25, 0.20),
        market_probabilities=(0.48, 0.27, 0.25),
        closing_odds=(2.05, 3.50, 4.10),
        outcome_index=0,
    )
    assert r.selected_index == 0
    assert abs(r.residual - 0.07) < 1e-12
    assert r.won
    assert abs(r.pnl_at_close - 1.05) < 1e-12


def test_threshold_report():
    rows = [
        max_positive_residual(
            competition="E0", season="x",
            model_probabilities=(0.60, 0.22, 0.18),
            market_probabilities=(0.52, 0.25, 0.23),
            closing_odds=(1.90, 3.50, 4.20), outcome_index=0,
        ),
        max_positive_residual(
            competition="E0", season="x",
            model_probabilities=(0.50, 0.30, 0.20),
            market_probabilities=(0.46, 0.29, 0.25),
            closing_odds=(2.10, 3.30, 3.80), outcome_index=2,
        ),
    ]
    report = residual_threshold_report(rows, thresholds=(0.05,))
    s = report["thresholds"]["0.05"]["overall"]
    assert s["n"] == 1
    assert s["hit_rate"] == 1.0
