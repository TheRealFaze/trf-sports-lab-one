from datetime import datetime, timezone

from trf_one.providers.football_data_uk import FootballDataUKClient, season_code
from trf_one.providers.the_odds_api import TheOddsAPIClient
from trf_one.providers.sportmonks import SportmonksClient


def test_season_code():
    assert season_code(2025) == "2526"
    assert season_code(2019) == "1920"


def test_football_data_parser_prefers_avg_closing_and_process():
    text = """Div,Date,HomeTeam,AwayTeam,FTHG,FTAG,HS,AS,HST,AST,HC,AC,B365H,B365D,B365A,AvgH,AvgD,AvgA,B365CH,B365CD,B365CA,AvgCH,AvgCD,AvgCA
E0,01/08/2025,Alpha,Beta,2,1,14,8,6,2,7,3,1.90,3.50,4.20,1.92,3.55,4.10,1.80,3.60,4.50,1.85,3.70,4.40
"""
    season = FootballDataUKClient().parse_season(text, division="E0", start_year=2025)
    assert len(season.matches) == 1
    assert len(season.process_matches) == 1
    assert season.process_matches[0].home_sot == 6
    assert season.quality.process_matches == 1
    assert season.quality.missing_process_rows == 0
    q = season.quotes[0]
    assert q.bookmaker == "FootballData Avg Close"
    assert q.snapshot_type == "CLOSE"
    assert q.home_odds == 1.85


def test_football_data_parser_marks_snapshot_and_missing_process():
    text = """Date,HomeTeam,AwayTeam,FTHG,FTAG,AvgH,AvgD,AvgA
01/08/2018,Alpha,Beta,1,0,2.10,3.30,3.60
"""
    season = FootballDataUKClient().parse_season(text, division="E0", start_year=2018)
    assert season.quotes[0].snapshot_type == "CURRENT"
    assert season.quality.fallback_quotes == 1
    assert season.quality.process_matches == 0
    assert season.quality.missing_process_rows == 1


def test_odds_api_consensus_de_vigs_each_book_first():
    payload = {
        "timestamp": "2025-08-01T10:00:00Z",
        "data": [{
            "id": "evt1","commence_time": "2025-08-01T19:00:00Z",
            "home_team": "Alpha","away_team": "Beta",
            "bookmakers": [
                {"key":"a","markets":[{"key":"h2h","outcomes":[
                    {"name":"Alpha","price":2.0},{"name":"Draw","price":3.5},{"name":"Beta","price":4.0}]}]},
                {"key":"b","markets":[{"key":"h2h","outcomes":[
                    {"name":"Alpha","price":1.95},{"name":"Draw","price":3.6},{"name":"Beta","price":4.2}]}]},
            ],
        }],
    }
    rows = TheOddsAPIClient.consensus_1x2(payload)
    c=rows[0]
    assert c.bookmakers == 2
    assert abs(sum(c.fair_probabilities) - 1.0) < 1e-12
    assert c.best_home_odds == 2.0


def test_sportmonks_fixture_normalizer_xg():
    payload = {"data": [{
        "id":123,"name":"Alpha vs Beta","starting_at":"2026-03-11 20:00:00",
        "participants":[
            {"name":"Alpha","meta":{"location":"home"}},
            {"name":"Beta","meta":{"location":"away"}},
        ],
        "xgfixture":[
            {"type":{"name":"Expected Goals (xG)","code":"expected-goals"},"location":"home","data":{"value":1.8}},
            {"type":{"name":"Expected Goals (xG)","code":"expected-goals"},"location":"away","data":{"value":0.9}},
        ],
    }]}
    rows=SportmonksClient.normalize_fixtures(payload)
    assert rows[0].home_team=="Alpha"
    assert rows[0].away_team=="Beta"
    assert rows[0].home_xg==1.8
    assert rows[0].away_xg==0.9
