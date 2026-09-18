from __future__ import annotations

import csv
import io
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterable, List, Optional, Sequence, Tuple
from urllib.request import Request, urlopen

from ..backtest import Historical1X2Quote
from ..structural import MatchRecord

BASE_URL = "https://www.football-data.co.uk/mmz4281"

DIVISIONS = {
    "E0": "Premier League",
    "E1": "Championship",
    "D1": "Bundesliga",
    "I1": "Serie A",
    "SP1": "La Liga",
    "F1": "Ligue 1",
    "N1": "Eredivisie",
    "B1": "Belgian Pro League",
    "P1": "Primeira Liga",
}


def season_code(start_year: int) -> str:
    if start_year < 1993 or start_year > 2098:
        raise ValueError("start_year looks invalid")
    return f"{start_year % 100:02d}{(start_year + 1) % 100:02d}"


def _parse_date(value: str) -> datetime:
    value = value.strip()
    for fmt in ("%d/%m/%Y", "%d/%m/%y", "%Y-%m-%d"):
        try:
            return datetime.strptime(value, fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    raise ValueError(f"Unsupported Football-Data date: {value!r}")


def _odds_float(row: dict[str, str], key: str) -> Optional[float]:
    value = (row.get(key) or "").strip()
    if not value:
        return None
    try:
        x = float(value)
    except ValueError:
        return None
    return x if x > 1.0 else None


def _stat_float(row: dict[str, str], key: str) -> Optional[float]:
    value = (row.get(key) or "").strip()
    if not value:
        return None
    try:
        x = float(value)
    except ValueError:
        return None
    return x if x >= 0 else None


@dataclass(frozen=True)
class ProcessMatchRecord:
    date: datetime
    home_team: str
    away_team: str
    home_goals: float
    away_goals: float
    home_shots: float
    away_shots: float
    home_sot: float
    away_sot: float
    home_corners: float
    away_corners: float

    def __post_init__(self) -> None:
        values = (
            self.home_goals, self.away_goals, self.home_shots, self.away_shots,
            self.home_sot, self.away_sot, self.home_corners, self.away_corners,
        )
        if any(v < 0 for v in values):
            raise ValueError("Process statistics must be non-negative")


@dataclass(frozen=True)
class FootballDataQuality:
    rows: int
    matches: int
    quotes: int
    closing_quotes: int
    fallback_quotes: int
    skipped_rows: int
    duplicate_matches: int
    quote_source_counts: dict[str, int]
    process_matches: int = 0
    missing_process_rows: int = 0


@dataclass(frozen=True)
class FootballDataSeason:
    division: str
    start_year: int
    matches: List[MatchRecord]
    quotes: List[Historical1X2Quote]
    quality: FootballDataQuality
    process_matches: List[ProcessMatchRecord]


class FootballDataUKClient:
    """Free keyless historical bootstrap provider.

    Football-Data is used for historical backtesting. Match-process fields are
    taken only when the six required shot/corner columns are present and valid.
    """

    def __init__(self, *, timeout: float = 30.0, user_agent: str = "TRF-Sports-Lab-One/0.4") -> None:
        self.timeout = timeout
        self.user_agent = user_agent

    def url(self, division: str, start_year: int) -> str:
        return f"{BASE_URL}/{season_code(start_year)}/{division}.csv"

    def fetch_text(self, division: str, start_year: int) -> str:
        req = Request(self.url(division, start_year), headers={"User-Agent": self.user_agent})
        with urlopen(req, timeout=self.timeout) as response:
            return response.read().decode("utf-8-sig", errors="replace")

    def fetch_season(self, division: str, start_year: int) -> FootballDataSeason:
        return self.parse_season(self.fetch_text(division, start_year), division=division, start_year=start_year)

    def parse_season(self, text: str, *, division: str, start_year: int) -> FootballDataSeason:
        reader = csv.DictReader(io.StringIO(text.lstrip("\ufeff")))
        required = {"Date", "HomeTeam", "AwayTeam", "FTHG", "FTAG"}
        missing = required - set(reader.fieldnames or [])
        if missing:
            raise ValueError(f"Football-Data CSV missing required columns: {sorted(missing)}")

        matches: List[MatchRecord] = []
        process: List[ProcessMatchRecord] = []
        quotes: List[Historical1X2Quote] = []
        seen = set()
        duplicates = skipped = closing = fallback = missing_process = 0
        source_counts: dict[str, int] = {}

        for row in reader:
            if not any((v or "").strip() for v in row.values()):
                continue
            try:
                date = _parse_date(row["Date"])
                home = row["HomeTeam"].strip()
                away = row["AwayTeam"].strip()
                hg = int(float(row["FTHG"]))
                ag = int(float(row["FTAG"]))
                key = (date.date(), home, away)
                if key in seen:
                    duplicates += 1
                    continue
                seen.add(key)
                matches.append(MatchRecord(date, home, away, hg, ag))

                stats = [_stat_float(row, c) for c in ("HS", "AS", "HST", "AST", "HC", "AC")]
                if all(x is not None for x in stats):
                    process.append(ProcessMatchRecord(
                        date=date, home_team=home, away_team=away,
                        home_goals=hg, away_goals=ag,
                        home_shots=float(stats[0]), away_shots=float(stats[1]),
                        home_sot=float(stats[2]), away_sot=float(stats[3]),
                        home_corners=float(stats[4]), away_corners=float(stats[5]),
                    ))
                else:
                    missing_process += 1

                quote = self._select_quote(row, date, home, away)
                if quote is not None:
                    quotes.append(quote)
                    source_counts[quote.bookmaker] = source_counts.get(quote.bookmaker, 0) + 1
                    if quote.snapshot_type == "CLOSE":
                        closing += 1
                    else:
                        fallback += 1
            except Exception:
                skipped += 1

        quality = FootballDataQuality(
            rows=len(matches) + skipped + duplicates,
            matches=len(matches),
            quotes=len(quotes),
            closing_quotes=closing,
            fallback_quotes=fallback,
            skipped_rows=skipped,
            duplicate_matches=duplicates,
            quote_source_counts=source_counts,
            process_matches=len(process),
            missing_process_rows=missing_process,
        )
        return FootballDataSeason(division, start_year, matches, quotes, quality, process)

    @staticmethod
    def _select_quote(
        row: dict[str, str], date: datetime, home: str, away: str
    ) -> Optional[Historical1X2Quote]:
        candidates: Sequence[Tuple[str, Tuple[str, str, str], str]] = (
            ("FootballData Avg Close", ("AvgCH", "AvgCD", "AvgCA"), "CLOSE"),
            ("Bet365 Close", ("B365CH", "B365CD", "B365CA"), "CLOSE"),
            ("Pinnacle Close", ("PSCH", "PSCD", "PSCA"), "CLOSE"),
            ("FootballData Avg Snapshot", ("AvgH", "AvgD", "AvgA"), "CURRENT"),
            ("Bet365 Snapshot", ("B365H", "B365D", "B365A"), "CURRENT"),
            ("Pinnacle Snapshot", ("PSH", "PSD", "PSA"), "CURRENT"),
        )
        for source, cols, snapshot in candidates:
            odds = [_odds_float(row, c) for c in cols]
            if all(x is not None for x in odds):
                return Historical1X2Quote(
                    date=date, home_team=home, away_team=away,
                    home_odds=float(odds[0]), draw_odds=float(odds[1]), away_odds=float(odds[2]),
                    bookmaker=source, snapshot_type=snapshot,
                )
        return None

    def fetch_many(self, divisions: Iterable[str], start_years: Iterable[int]) -> List[FootballDataSeason]:
        return [self.fetch_season(d, y) for y in start_years for d in divisions]
