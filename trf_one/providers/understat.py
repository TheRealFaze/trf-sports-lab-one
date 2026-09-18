from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterable, List
from urllib.request import Request, urlopen

BASE_URL = "https://understat.com/league/{league}/{season}"

FOOTBALL_DATA_TO_UNDERSTAT = {
    "E0": "EPL",
    "D1": "Bundesliga",
    "I1": "Serie_A",
    "SP1": "La_liga",
    "F1": "Ligue_1",
}


@dataclass(frozen=True)
class UnderstatXGMatch:
    league: str
    season: int
    match_id: str
    date: datetime
    home_team: str
    away_team: str
    home_goals: int
    away_goals: int
    home_xg: float
    away_xg: float


def normalize_team_name(value: str) -> str:
    value = unicodedata.normalize("NFKD", value)
    value = "".join(ch for ch in value if not unicodedata.combining(ch)).lower()
    value = value.replace("&", " and ")
    value = re.sub(r"[^a-z0-9]+", " ", value).strip()
    aliases = {
        "man city": "manchester city",
        "man united": "manchester united",
        "wolves": "wolverhampton wanderers",
        "nott m forest": "nottingham forest",
        "newcastle": "newcastle united",
        "leicester": "leicester city",
        "ath madrid": "atletico madrid",
        "ath bilbao": "athletic club",
        "sociedad": "real sociedad",
        "betis": "real betis",
        "vallecano": "rayo vallecano",
        "alaves": "deportivo alaves",
        "m gladbach": "borussia monchengladbach",
        "leverkusen": "bayer leverkusen",
        "ein frankfurt": "eintracht frankfurt",
        "paris sg": "paris saint germain",
        "verona": "hellas verona",
        "milan": "ac milan",
    }
    return aliases.get(value, value)


class UnderstatClient:
    """Keyless public Understat match-level xG adapter.

    Current Understat league endpoints return JSON for XMLHttpRequest requests.
    A legacy HTML datesData parser is retained as a fallback so historical page
    responses remain usable. Only completed match xG is consumed.
    """

    def __init__(self, *, timeout: float = 30.0, user_agent: str = "TRF-Sports-Lab-One/0.5") -> None:
        self.timeout = timeout
        self.user_agent = user_agent

    def url(self, league: str, season: int) -> str:
        return BASE_URL.format(league=league, season=season)

    def fetch_text(self, league: str, season: int) -> str:
        req = Request(
            self.url(league, season),
            headers={
                "User-Agent": self.user_agent,
                "X-Requested-With": "XMLHttpRequest",
                "Accept": "application/json,text/plain,*/*",
            },
        )
        with urlopen(req, timeout=self.timeout) as response:
            return response.read().decode("utf-8", errors="replace")

    @staticmethod
    def _legacy_html_dates_data(text: str) -> list:
        match = re.search(r"datesData\s*=\s*JSON\.parse\('(.*?)'\)", text, flags=re.S)
        if not match:
            raise ValueError("Understat datesData payload not found")
        encoded = match.group(1)
        decoded = re.sub(
            r"\\x([0-9A-Fa-f]{2})",
            lambda m: chr(int(m.group(1), 16)),
            encoded,
        )
        decoded = decoded.replace("\\'", "'").replace("\\\\", "\\")
        payload = json.loads(decoded)
        if not isinstance(payload, list):
            raise ValueError("Legacy Understat datesData is not a list")
        return payload

    @classmethod
    def _decode_dates_data(cls, text: str) -> list:
        stripped = text.lstrip()
        if stripped:
            try:
                payload = json.loads(stripped)
            except json.JSONDecodeError:
                payload = None

            if isinstance(payload, list):
                return payload
            if isinstance(payload, dict):
                candidates = (
                    payload.get("dates"),
                    payload.get("datesData"),
                    (payload.get("data") or {}).get("dates")
                    if isinstance(payload.get("data"), dict)
                    else None,
                )
                for candidate in candidates:
                    if isinstance(candidate, list):
                        return candidate
                    if isinstance(candidate, dict) and isinstance(candidate.get("dates"), list):
                        return candidate["dates"]

        return cls._legacy_html_dates_data(text)

    @staticmethod
    def _parse_datetime(value: str) -> datetime:
        raw = str(value).strip()
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%SZ"):
            try:
                parsed = datetime.strptime(raw, fmt)
                if parsed.tzinfo is None:
                    parsed = parsed.replace(tzinfo=timezone.utc)
                return parsed.astimezone(timezone.utc)
            except ValueError:
                continue
        try:
            parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            return parsed.astimezone(timezone.utc)
        except ValueError as exc:
            raise ValueError(f"Unsupported Understat datetime: {value}") from exc

    def parse_league(self, text: str, *, league: str, season: int) -> List[UnderstatXGMatch]:
        data = self._decode_dates_data(text)
        out: List[UnderstatXGMatch] = []
        for item in data:
            if not isinstance(item, dict) or not item.get("isResult"):
                continue
            try:
                out.append(
                    UnderstatXGMatch(
                        league=league,
                        season=season,
                        match_id=str(item["id"]),
                        date=self._parse_datetime(item["datetime"]),
                        home_team=str(item["h"]["title"]),
                        away_team=str(item["a"]["title"]),
                        home_goals=int(item["goals"]["h"]),
                        away_goals=int(item["goals"]["a"]),
                        home_xg=float(item["xG"]["h"]),
                        away_xg=float(item["xG"]["a"]),
                    )
                )
            except (KeyError, TypeError, ValueError):
                continue
        return out

    def fetch_league(self, league: str, season: int) -> List[UnderstatXGMatch]:
        return self.parse_league(self.fetch_text(league, season), league=league, season=season)

    def fetch_many(self, leagues: Iterable[str], seasons: Iterable[int]) -> List[UnderstatXGMatch]:
        out: List[UnderstatXGMatch] = []
        for season in seasons:
            for league in leagues:
                out.extend(self.fetch_league(league, season))
        return out
