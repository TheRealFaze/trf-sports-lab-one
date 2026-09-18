import json
from trf_one.providers.understat import UnderstatClient, normalize_team_name


def encode_hex(s: str) -> str:
    return "".join(f"\\x{ord(c):02X}" for c in s)


def test_understat_parser():
    payload=[{
        "id":"1","isResult":True,
        "h":{"title":"Manchester City"},"a":{"title":"Wolves"},
        "goals":{"h":"2","a":"1"},"xG":{"h":"1.75","a":"0.88"},
        "datetime":"2025-08-10 15:00:00"
    }]
    html="<script>var datesData = JSON.parse('" + encode_hex(json.dumps(payload,separators=(',',':'))) + "')</script>"
    rows=UnderstatClient().parse_league(html,league="EPL",season=2025)
    assert len(rows)==1
    assert rows[0].home_xg==1.75
    assert rows[0].away_goals==1


def test_team_normalizer_aliases():
    assert normalize_team_name("Man City")==normalize_team_name("Manchester City")
    assert normalize_team_name("Wolves")==normalize_team_name("Wolverhampton Wanderers")
    assert normalize_team_name("Ath Madrid")==normalize_team_name("Atletico Madrid")
