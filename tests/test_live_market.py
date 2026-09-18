from datetime import datetime, timezone

from trf_one.live_market import (
    ExecutionPrice,
    assess_execution_prices,
    build_consensus_quotes,
    build_execution_queue,
    required_execution_odds,
)


def payload():
    return [
        {
            "id": "evt1",
            "commence_time": "2026-09-18T18:00:00Z",
            "home_team": "Alpha",
            "away_team": "Beta",
            "bookmakers": [
                {
                    "key": "a",
                    "markets": [
                        {"key": "h2h", "outcomes": [
                            {"name": "Alpha", "price": 2.0},
                            {"name": "Draw", "price": 3.5},
                            {"name": "Beta", "price": 4.0},
                        ]},
                        {"key": "totals", "outcomes": [
                            {"name": "Over", "price": 1.90, "point": 2.5},
                            {"name": "Under", "price": 1.95, "point": 2.5},
                        ]},
                    ],
                },
                {
                    "key": "b",
                    "markets": [
                        {"key": "h2h", "outcomes": [
                            {"name": "Alpha", "price": 1.95},
                            {"name": "Draw", "price": 3.6},
                            {"name": "Beta", "price": 4.2},
                        ]},
                        {"key": "totals", "outcomes": [
                            {"name": "Over", "price": 1.92, "point": 2.5},
                            {"name": "Under", "price": 1.93, "point": 2.5},
                        ]},
                    ],
                },
                {
                    "key": "c",
                    "markets": [
                        {"key": "h2h", "outcomes": [
                            {"name": "Alpha", "price": 1.98},
                            {"name": "Draw", "price": 3.55},
                            {"name": "Beta", "price": 4.1},
                        ]},
                        {"key": "totals", "outcomes": [
                            {"name": "Over", "price": 1.91, "point": 2.5},
                            {"name": "Under", "price": 1.94, "point": 2.5},
                        ]},
                    ],
                },
            ],
        }
    ]


def test_build_consensus_h2h_and_totals():
    quotes = build_consensus_quotes(
        payload(),
        sport="soccer_test",
        fetched_at=datetime(2026, 9, 18, tzinfo=timezone.utc),
        min_books=3,
    )
    h2h = [q for q in quotes if q.market_group == "1X2"]
    totals = [q for q in quotes if q.market_group == "TOTALS_2.5"]
    assert len(h2h) == 3
    assert len(totals) == 2
    assert abs(sum(q.fair_probability for q in h2h) - 1.0) < 1e-10
    assert abs(sum(q.fair_probability for q in totals) - 1.0) < 1e-10
    assert all(q.bookmakers == 3 for q in quotes)


def test_execution_queue_is_not_a_pick_and_has_threshold():
    quotes = build_consensus_quotes(payload(), sport="soccer_test", min_books=3)
    queue = build_execution_queue(quotes, min_ev=0.02, top=1)
    assert len(queue) == 1
    assert queue[0].status == "CHECK PRICE"
    assert queue[0].required_execution_odds > queue[0].fair_odds


def test_execution_assessment_qualifies_only_if_price_clears_ev():
    quotes = build_consensus_quotes(payload(), sport="soccer_test", min_books=3)
    home = next(q for q in quotes if q.market_group == "1X2" and q.selection == "H")
    threshold = required_execution_odds(home.fair_probability, 0.02)

    prices = [
        ExecutionPrice(
            fixture_id=home.fixture_id,
            market_group=home.market_group,
            selection=home.selection,
            execution_odds=threshold + 0.05,
            execution_source="Napoleon",
            line=home.line,
        )
    ]
    out = assess_execution_prices(quotes, prices, min_ev=0.02)
    assert out[0].decision == "QUALIFY"
    assert out[0].ev >= 0.02
