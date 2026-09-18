from dataclasses import replace
from datetime import datetime, timedelta, timezone

from trf_one.backtest import (
    BetResult,
    WalkForwardConfig,
    betting_summary,
    calibration_bins,
    fit_blend_weight,
    geometric_blend_1x2,
    walk_forward_predict,
)
from trf_one.structural import MatchRecord, StructuralConfig


def records(n_days=100):
    start = datetime(2025, 1, 1, tzinfo=timezone.utc)
    teams = ["A", "B", "C", "D"]
    rows = []
    for i in range(n_days):
        h = teams[i % 4]
        a = teams[(i + 1 + (i // 4) % 2) % 4]
        if h == a:
            a = teams[(i + 2) % 4]
        hg = 2 if h in ("A", "B") else 1
        ag = 0 if a == "D" else 1
        rows.append(MatchRecord(start + timedelta(days=i), h, a, hg, ag))
    return rows


def test_walk_forward_blocks_future_leakage():
    rows = records(90)
    cfg = WalkForwardConfig(
        min_training_matches=30,
        structural_config=StructuralConfig(max_iter=350, learning_rate=0.03),
    )
    base = walk_forward_predict(rows, cfg)
    future_cut = rows[70].date
    altered = [
        replace(r, home_goals=9, away_goals=9) if r.date > future_cut else r
        for r in rows
    ]
    changed = walk_forward_predict(altered, cfg)
    base_early = [(p.date, p.p_home, p.p_draw, p.p_away) for p in base if p.date <= future_cut]
    changed_early = [(p.date, p.p_home, p.p_draw, p.p_away) for p in changed if p.date <= future_cut]
    assert base_early == changed_early


def test_geometric_blend_and_weight_fit():
    mkt = [(0.34, 0.33, 0.33)] * 6
    model = [
        (0.85, 0.10, 0.05),
        (0.10, 0.80, 0.10),
        (0.05, 0.10, 0.85),
        (0.80, 0.15, 0.05),
        (0.10, 0.80, 0.10),
        (0.05, 0.10, 0.85),
    ]
    outcomes = [0, 1, 2, 0, 1, 2]
    assert fit_blend_weight(mkt, model, outcomes, step=0.1) >= 0.9
    p = geometric_blend_1x2(mkt[0], model[0], 0.5)
    assert abs(sum(p) - 1.0) < 1e-12


def test_calibration_bins():
    bins = calibration_bins([0.12, 0.18, 0.82, 0.88], [0, 0, 1, 1], bins=5)
    assert sum(b.count for b in bins) == 4
    assert bins[0].observed_rate == 0.0
    assert bins[-1].observed_rate == 1.0


def test_betting_summary():
    bets = [
        BetResult(2.0, 1.0, True, 1.8),
        BetResult(2.0, 1.0, False, 2.1),
        BetResult(1.8, 1.0, True, 1.7),
    ]
    s = betting_summary(bets)
    assert abs(s["pnl"] - 0.8) < 1e-12
    assert abs(s["roi"] - (0.8 / 3.0)) < 1e-12
    assert s["max_drawdown_units"] >= 1.0


def test_market_comparison_and_quote_loader(tmp_path):
    from trf_one.backtest import (
        Historical1X2Quote,
        compare_prediction_to_quote,
        load_1x2_quotes_csv,
    )

    preds = walk_forward_predict(
        records(45),
        WalkForwardConfig(
            min_training_matches=30,
            structural_config=StructuralConfig(max_iter=250, learning_rate=0.03),
        ),
    )
    pred = preds[0]
    q = Historical1X2Quote(pred.date, pred.home_team, pred.away_team, 2.1, 3.4, 3.5)
    c = compare_prediction_to_quote(pred, q)
    assert abs(sum(c["market"]) - 1.0) < 1e-9
    assert len(c["ev"]) == 3

    p = tmp_path / "odds.csv"
    p.write_text(
        "date,home_team,away_team,home_odds,draw_odds,away_odds,bookmaker,snapshot_type\n"
        f"{pred.date.isoformat()},{pred.home_team},{pred.away_team},2.1,3.4,3.5,Consensus,CLOSE\n",
        encoding="utf-8",
    )
    rows = load_1x2_quotes_csv(str(p))
    assert rows[0].bookmaker == "Consensus"
    assert rows[0].snapshot_type == "CLOSE"


def test_walk_forward_market_blend_uses_only_past_history():
    from trf_one.backtest import Historical1X2Quote, walk_forward_market_blend

    preds = walk_forward_predict(
        records(80),
        WalkForwardConfig(
            min_training_matches=25,
            structural_config=StructuralConfig(max_iter=220, learning_rate=0.03),
        ),
    )
    quotes = [
        Historical1X2Quote(p.date, p.home_team, p.away_team, 2.4, 3.3, 2.9)
        for p in preds
    ]
    blended = walk_forward_market_blend(preds, quotes, min_history=10, step=0.2)
    assert blended[0].model_weight == 0.0
    assert blended[0].history_size == 0
    assert all(0.0 <= p.model_weight <= 1.0 for p in blended)
    assert all(abs(sum(p.probabilities) - 1.0) < 1e-12 for p in blended)
