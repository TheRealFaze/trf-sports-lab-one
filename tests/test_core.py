from trf_one.devig import proportional_devig, power_devig, shin_devig
from trf_one.poisson import score_matrix, market_probs_from_matrix
from trf_one.edge import evaluate_edge, brier_component, log_loss_component
from trf_one.kelly import kelly_fraction


def test_devig_methods_sum_to_one():
    odds = [1.80, 3.70, 4.60]
    for fn in (proportional_devig, power_devig, shin_devig):
        p = fn(odds)
        assert abs(sum(p)-1.0) < 1e-8
        assert all(0 < x < 1 for x in p)


def test_poisson_matrix_and_markets():
    m = score_matrix(1.6, 1.1, max_goals=10, rho=-0.06)
    assert abs(sum(sum(r) for r in m)-1.0) < 1e-10
    p = market_probs_from_matrix(m)
    assert abs(p["home_win"] + p["draw"] + p["away_win"] - 1.0) < 1e-10
    assert 0 < p["btts_yes"] < 1


def test_edge_gate():
    e = evaluate_edge(
        market_probability=0.54,
        model_probability=0.61,
        prudent_low=0.57,
        prudent_high=0.65,
        available_odds=1.90,
    )
    assert e.ev_central > 0
    assert e.ev_prudent > 0
    assert e.decision_gate == "ROBUST EDGE"


def test_scoring_and_kelly():
    assert abs(brier_component(0.7, 1)-0.09) < 1e-12
    assert log_loss_component(0.7, 1) > 0
    assert kelly_fraction(2.0, 0.55, fraction=0.25) > 0
    assert kelly_fraction(1.80, 0.50, fraction=0.25) == 0
