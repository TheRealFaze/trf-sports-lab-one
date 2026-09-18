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
    """Football-Data season path, e.g. 2025 -> '2526'."""
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


def _float(row: dict[str, str], key: str) -> Optional[float]:
    value = (row.get(key) or "").strip()
    if not value:
        return None
    try:
        x = float(value)
    except ValueError:
        return None
    return x if x > 1.0 else None


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


@dataclass(frozen=True)
class FootballDataSeason:
    division: str
    start_year: int
    matches: List[MatchRecord]
    quotes: List[Historical1X2Quote]
    quality: FootballDataQuality


class FootballDataUKClient:
    """Free keyless historical bootstrap provider.

    Football-Data is used as a bootstrap/backtest source, not as a live execution
    source. Closing-average odds are preferred when available. Unsuffixed odds are
    explicitly marked as non-closing fallback snapshots.
    """

    def __init__(self, *, timeout: float = 30.0, user_agent: str = "TRF-Sports-Lab-One/0.3") -> None:
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
        quotes: List[Historical1X2Quote] = []
        seen = set()
        duplicates = skipped = closing = fallback = 0
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
        )
        return FootballDataSeason(division, start_year, matches, quotes, quality)

    @staticmethod
    def _select_quote(
        row: dict[str, str],
        date: datetime,
        home: str,
        away: str,
    ) -> Optional[Historical1X2Quote]:
        # Prefer market-average closing odds: avoids stitching "Max" prices from
        # different books and is less dependent on a single bookmaker.
        candidates: Sequence[Tuple[str, Tuple[str, str, str], str]] = (
            ("FootballData Avg Close", ("AvgCH", "AvgCD", "AvgCA"), "CLOSE"),
            ("Bet365 Close", ("B365CH", "B365CD", "B365CA"), "CLOSE"),
            ("Pinnacle Close", ("PSCH", "PSCD", "PSCA"), "CLOSE"),
            ("FootballData Avg Snapshot", ("AvgH", "AvgD", "AvgA"), "CURRENT"),
            ("Bet365 Snapshot", ("B365H", "B365D", "B365A"), "CURRENT"),
            ("Pinnacle Snapshot", ("PSH", "PSD", "PSA"), "CURRENT"),
        )
        for source, cols, snapshot in candidates:
            odds = [_float(row, c) for c in cols]
            if all(x is not None for x in odds):
                return Historical1X2Quote(
                    date=date,
                    home_team=home,
                    away_team=away,
                    home_odds=float(odds[0]),
                    draw_odds=float(odds[1]),
                    away_odds=float(odds[2]),
                    bookmaker=source,
                    snapshot_type=snapshot,
                )
        return None

    def fetch_many(
        self,
        divisions: Iterable[str],
        start_years: Iterable[int],
    ) -> List[FootballDataSeason]:
        out = []
        for year in start_years:
            for division in divisions:
                out.append(self.fetch_season(division, year))
        return out
