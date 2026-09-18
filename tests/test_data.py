from datetime import datetime, timezone
from pathlib import Path

from trf_one.data import load_matches_csv, validate_match_records
from trf_one.structural import DixonColesStructuralModel, MatchRecord, StructuralConfig


def test_csv_loader_and_quality(tmp_path: Path):
    p = tmp_path / "matches.csv"
    p.write_text(
        "date,home_team,away_team,home_goals,away_goals,home_xg,away_xg\n"
        "2026-01-01,Alpha,Beta,2,1,1.8,0.9\n"
        "2026-01-08,Beta,Alpha,0,1,0.7,1.3\n",
        encoding="utf-8",
    )
    rows = load_matches_csv(p)
    q = validate_match_records(rows)
    assert q.rows == 2
    assert q.teams == 2
    assert q.duplicate_rows == 0
    assert q.missing_xg_rows == 0


def test_snapshot_roundtrip_is_reproducible():
    rows = [
        MatchRecord(datetime(2026, 1, 1, tzinfo=timezone.utc), "A", "B", 2, 0),
        MatchRecord(datetime(2026, 1, 8, tzinfo=timezone.utc), "B", "A", 1, 1),
        MatchRecord(datetime(2026, 1, 15, tzinfo=timezone.utc), "A", "B", 3, 1),
        MatchRecord(datetime(2026, 1, 22, tzinfo=timezone.utc), "B", "A", 0, 2),
    ]
    model = DixonColesStructuralModel(StructuralConfig(max_iter=700)).fit(rows)
    p1 = model.predict_lambdas("A", "B")
    restored = DixonColesStructuralModel.from_snapshot(model.snapshot())
    p2 = restored.predict_lambdas("A", "B")
    assert abs(p1.lambda_home - p2.lambda_home) < 1e-12
    assert abs(p1.lambda_away - p2.lambda_away) < 1e-12
    assert p1.rho == p2.rho
