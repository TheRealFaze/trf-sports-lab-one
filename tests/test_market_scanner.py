from trf_one.market_scanner import (
    MarketOutcomeInput,
    ScannerConfig,
    assess_derived_price,
    derive_double_chance_probabilities,
    scan_market_group,
    scan_markets,
)


def rows(exec_home=2.05):
    return [
        MarketOutcomeInput("m1","1X2","H",1.90,exec_home,consensus_source="sharp",execution_source="napoleon",model_probability=0.54),
        MarketOutcomeInput("m1","1X2","D",3.60,3.50,consensus_source="sharp",execution_source="napoleon",model_probability=0.27),
        MarketOutcomeInput("m1","1X2","A",4.20,4.00,consensus_source="sharp",execution_source="napoleon",model_probability=0.19),
    ]


def test_market_scanner_probabilities_sum_to_one():
    out = scan_market_group(rows(), ScannerConfig(min_prudent_ev=0.0))
    assert abs(sum(x.market_fair_probability for x in out) - 1.0) < 1e-10


def test_scanner_qualifies_execution_price_above_consensus_fair():
    out = scan_market_group(rows(2.10), ScannerConfig(min_prudent_ev=0.02))
    home = next(x for x in out if x.selection == "H")
    assert home.price_ev_market > 0.02
    assert home.decision == "QUALIFY"
    assert home.tier == "SHADOW VALUE"


def test_model_is_veto_not_unearned_boost_by_default():
    inputs = rows(2.10)
    inputs[0] = MarketOutcomeInput(
        "m1","1X2","H",1.90,2.10,
        consensus_source="sharp",execution_source="napoleon",
        model_probability=0.20,
    )
    out = scan_market_group(inputs, ScannerConfig(min_prudent_ev=0.0, model_weight=0.0, model_veto_pp=0.10))
    home = next(x for x in out if x.selection == "H")
    assert home.central_probability == home.market_fair_probability
    assert home.decision == "PASS"
    assert "contradicts" in home.reason


def test_same_source_is_rejected():
    inputs = [
        MarketOutcomeInput("m1","BTTS","YES",1.80,1.90,consensus_source="napoleon",execution_source="napoleon"),
        MarketOutcomeInput("m1","BTTS","NO",2.00,2.10,consensus_source="napoleon",execution_source="napoleon"),
    ]
    out = scan_market_group(inputs)
    assert all(x.decision == "PASS" for x in out)


def test_double_chance_derivation():
    dc = derive_double_chance_probabilities({"H":0.50,"D":0.28,"A":0.22})
    assert abs(dc["1X"] - 0.78) < 1e-12
    assert abs(dc["X2"] - 0.50) < 1e-12
    assert abs(dc["12"] - 0.72) < 1e-12

    p = assess_derived_price(
        fixture_id="m1",market_group="DOUBLE CHANCE",selection="1X",
        fair_probability=dc["1X"],execution_odds=1.35,min_ev=0.02,
    )
    assert p.ev > 0
    assert p.decision == "QUALIFY"


def test_scan_markets_is_sorted_by_prudent_ev():
    a = [
        MarketOutcomeInput("a","BTTS","YES",1.90,2.10,consensus_source="c",execution_source="e"),
        MarketOutcomeInput("a","BTTS","NO",1.95,1.90,consensus_source="c",execution_source="e"),
        MarketOutcomeInput("b","OU2.5","OVER",2.00,2.02,consensus_source="c",execution_source="e"),
        MarketOutcomeInput("b","OU2.5","UNDER",1.90,1.90,consensus_source="c",execution_source="e"),
    ]
    out = scan_markets(a, ScannerConfig(min_prudent_ev=0.0))
    assert out[0].ev_prudent >= out[-1].ev_prudent
