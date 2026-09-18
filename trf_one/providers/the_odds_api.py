from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Dict, Iterable, List, Mapping, Optional, Sequence, Tuple
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from ..devig import devig

BASE_URL = "https://api.the-odds-api.com/v4"


@dataclass(frozen=True)
class OddsConsensus1X2:
    event_id: str
    commence_time: datetime
    home_team: str
    away_team: str
    snapshot_time: datetime
    bookmakers: int
    fair_home: float
    fair_draw: float
    fair_away: float
    best_home_odds: Optional[float]
    best_draw_odds: Optional[float]
    best_away_odds: Optional[float]

    @property
    def fair_probabilities(self) -> Tuple[float, float, float]:
        return self.fair_home, self.fair_draw, self.fair_away


class TheOddsAPIClient:
    """Historical/current market adapter.

    API key is read from THE_ODDS_API_KEY by default. Historical endpoints require
    a paid plan according to the provider documentation.
    """

    def __init__(self, api_key: Optional[str] = None, *, timeout: float = 30.0) -> None:
        self.api_key = api_key or os.getenv("THE_ODDS_API_KEY")
        self.timeout = timeout

    def _key(self) -> str:
        if not self.api_key:
            raise RuntimeError(
                "THE_ODDS_API_KEY is not configured. Store it as an environment/GitHub secret; "
                "do not commit API keys."
            )
        return self.api_key

    def _get(self, path: str, params: Mapping[str, str]) -> dict:
        query = dict(params)
        query["apiKey"] = self._key()
        url = f"{BASE_URL}{path}?{urlencode(query)}"
        req = Request(url, headers={"User-Agent": "TRF-Sports-Lab-One/0.3"})
        with urlopen(req, timeout=self.timeout) as response:
            return json.loads(response.read().decode("utf-8"))

    def historical_odds(
        self,
        *,
        sport: str,
        at: datetime,
        regions: str = "eu,uk",
        markets: str = "h2h",
        odds_format: str = "decimal",
    ) -> dict:
        at_utc = at.astimezone(timezone.utc) if at.tzinfo else at.replace(tzinfo=timezone.utc)
        return self._get(
            f"/historical/sports/{sport}/odds",
            {
                "regions": regions,
                "markets": markets,
                "oddsFormat": odds_format,
                "date": at_utc.isoformat().replace("+00:00", "Z"),
            },
        )

    @staticmethod
    def _parse_time(value: str) -> datetime:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))

    @staticmethod
    def consensus_1x2(
        payload: dict,
        *,
        devig_method: str = "shin",
        bookmaker_keys: Optional[Iterable[str]] = None,
    ) -> List[OddsConsensus1X2]:
        snapshot_raw = payload.get("timestamp")
        if not snapshot_raw:
            raise ValueError("Historical payload missing timestamp")
        snapshot = TheOddsAPIClient._parse_time(snapshot_raw)
        allowed = set(bookmaker_keys) if bookmaker_keys is not None else None
        out: List[OddsConsensus1X2] = []

        for event in payload.get("data", []):
            home = event.get("home_team")
            away = event.get("away_team")
            if not home or not away:
                continue

            fair_books: List[Tuple[float, float, float]] = []
            raw_books: List[Tuple[float, float, float]] = []
            for book in event.get("bookmakers", []):
                if allowed is not None and book.get("key") not in allowed:
                    continue
                h2h = next((m for m in book.get("markets", []) if m.get("key") == "h2h"), None)
                if h2h is None:
                    continue
                prices: Dict[str, float] = {}
                for outcome in h2h.get("outcomes", []):
                    name = outcome.get("name")
                    price = outcome.get("price")
                    if name is not None and isinstance(price, (int, float)) and price > 1:
                        prices[str(name)] = float(price)
                if home not in prices or away not in prices or "Draw" not in prices:
                    continue
                raw = (prices[home], prices["Draw"], prices[away])
                fair = tuple(devig(raw, method=devig_method))
                raw_books.append(raw)
                fair_books.append(fair)

            if not fair_books:
                continue

            n = len(fair_books)
            fair = tuple(sum(p[i] for p in fair_books) / n for i in range(3))
            raw_best = tuple(max(p[i] for p in raw_books) for i in range(3))
            out.append(
                OddsConsensus1X2(
                    event_id=str(event.get("id", "")),
                    commence_time=TheOddsAPIClient._parse_time(event["commence_time"]),
                    home_team=str(home),
                    away_team=str(away),
                    snapshot_time=snapshot,
                    bookmakers=n,
                    fair_home=fair[0],
                    fair_draw=fair[1],
                    fair_away=fair[2],
                    best_home_odds=raw_best[0],
                    best_draw_odds=raw_best[1],
                    best_away_odds=raw_best[2],
                )
            )
        return out
