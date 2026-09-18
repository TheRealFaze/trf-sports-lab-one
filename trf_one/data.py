from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable, List, Optional

from .structural import MatchRecord


@dataclass(frozen=True)
class DataQualityReport:
    rows: int
    teams: int
    earliest: datetime
    latest: datetime
    duplicate_rows: int
    missing_xg_rows: int


def _parse_datetime(value: str) -> datetime:
    value = value.strip()
    if not value:
        raise ValueError("Empty date")
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%Y/%m/%d"):
            try:
                return datetime.strptime(value, fmt)
            except ValueError:
                pass
    raise ValueError(f"Unsupported date format: {value}")


def load_matches_csv(
    path: str | Path,
    *,
    date_col: str = "date",
    home_team_col: str = "home_team",
    away_team_col: str = "away_team",
    home_goals_col: str = "home_goals",
    away_goals_col: str = "away_goals",
    home_xg_col: str = "home_xg",
    away_xg_col: str = "away_xg",
) -> List[MatchRecord]:
    rows: List[MatchRecord] = []
    with Path(path).open("r", encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(fh)
        required = {date_col, home_team_col, away_team_col, home_goals_col, away_goals_col}
        missing = required - set(reader.fieldnames or [])
        if missing:
            raise ValueError(f"CSV is missing required columns: {sorted(missing)}")

        has_xg = home_xg_col in (reader.fieldnames or []) and away_xg_col in (reader.fieldnames or [])
        for line_no, row in enumerate(reader, start=2):
            try:
                hxg: Optional[float] = None
                axg: Optional[float] = None
                if has_xg:
                    hxg = float(row[home_xg_col]) if row.get(home_xg_col, "").strip() else None
                    axg = float(row[away_xg_col]) if row.get(away_xg_col, "").strip() else None
                rows.append(
                    MatchRecord(
                        date=_parse_datetime(row[date_col]),
                        home_team=row[home_team_col].strip(),
                        away_team=row[away_team_col].strip(),
                        home_goals=float(row[home_goals_col]),
                        away_goals=float(row[away_goals_col]),
                        home_xg=hxg,
                        away_xg=axg,
                    )
                )
            except Exception as exc:
                raise ValueError(f"Invalid row at CSV line {line_no}: {exc}") from exc
    return rows


def validate_match_records(records: Iterable[MatchRecord]) -> DataQualityReport:
    rows = list(records)
    if not rows:
        raise ValueError("Dataset is empty")

    keys = set()
    duplicates = 0
    missing_xg = 0
    teams = set()
    for r in rows:
        key = (r.date, r.home_team, r.away_team, r.home_goals, r.away_goals)
        if key in keys:
            duplicates += 1
        keys.add(key)
        teams.update((r.home_team, r.away_team))
        if r.home_xg is None or r.away_xg is None:
            missing_xg += 1

    dates = [r.date for r in rows]
    return DataQualityReport(
        rows=len(rows),
        teams=len(teams),
        earliest=min(dates),
        latest=max(dates),
        duplicate_rows=duplicates,
        missing_xg_rows=missing_xg,
    )
