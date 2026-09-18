from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Dict, List, Optional
from urllib.parse import urlencode
from urllib.request import Request, urlopen

BASE_URL = "https://api.sportmonks.com/v3/football"


@dataclass(frozen=True)
class SportmonksFixture:
    fixture_id: int
    name: str
    starting_at: datetime
    home_team: Optional[str]
    away_team: Optional[str]
    home_score: Optional[float]
    away_score: Optional[float]
    home_xg: Optional[float]
    away_xg: Optional[float]


class SportmonksClient:
    """Rich football process-data adapter.

    Token is read from SPORTMONKS_API_TOKEN. The adapter intentionally requests
    raw football process data; Sportmonks prediction/value fields are not used as
    primary evidence by ONE.
    """

    def __init__(self, api_token: Optional[str] = None, *, timeout: float = 30.0) -> None:
        self.api_token = api_token or os.getenv("SPORTMONKS_API_TOKEN")
        self.timeout = timeout

    def _token(self) -> str:
        if not self.api_token:
            raise RuntimeError(
                "SPORTMONKS_API_TOKEN is not configured. Store it as an environment/GitHub secret; "
                "do not commit API tokens."
            )
        return self.api_token

    def _get(self, path: str, params: Optional[Dict[str, str]] = None) -> dict:
        query = dict(params or {})
        query["api_token"] = self._token()
        url = f"{BASE_URL}{path}?{urlencode(query)}"
        req = Request(url, headers={"Accept": "application/json", "User-Agent": "TRF-Sports-Lab-One/0.3"})
        with urlopen(req, timeout=self.timeout) as response:
            return json.loads(response.read().decode("utf-8"))

    def fixtures_between(
        self,
        start: date,
        end: date,
        *,
        include: str = "participants;scores;statistics;xGFixture",
    ) -> dict:
        return self._get(
            f"/fixtures/between/{start.isoformat()}/{end.isoformat()}",
            {"include": include},
        )

    @staticmethod
    def _participant_name(fixture: dict, location: str) -> Optional[str]:
        for p in fixture.get("participants", []) or []:
            meta = p.get("meta") or {}
            if str(meta.get("location", "")).lower() == location:
                return p.get("name")
        return None

    @staticmethod
    def _score(fixture: dict, location: str) -> Optional[float]:
        # Sportmonks responses can contain several score descriptions. Prefer CURRENT
        # or FT-like entries and use participant/location if present.
        candidates = []
        for score in fixture.get("scores", []) or []:
            desc = str(score.get("description", "")).upper()
            participant = str(score.get("score", {}).get("participant", "")).lower()
            goals = score.get("score", {}).get("goals")
            if goals is None:
                continue
            score_participant = score.get("participant_id")
            candidates.append((desc, participant, score_participant, float(goals)))
        for desc, participant, _, goals in reversed(candidates):
            if location in participant and desc in {"CURRENT", "2ND_HALF", "FT", "FULLTIME"}:
                return goals
        return None

    @staticmethod
    def _xg(fixture: dict, location: str) -> Optional[float]:
        for item in fixture.get("xgfixture", []) or fixture.get("xGFixture", []) or []:
            if str(item.get("location", "")).lower() != location:
                continue
            t = item.get("type") or {}
            code = str(t.get("code", "")).lower()
            name = str(t.get("name", "")).lower()
            if code == "expected-goals" or name == "expected goals (xg)":
                data = item.get("data") or {}
                value = data.get("value")
                if isinstance(value, (int, float)):
                    return float(value)
        return None

    @staticmethod
    def normalize_fixtures(payload: dict) -> List[SportmonksFixture]:
        out: List[SportmonksFixture] = []
        for f in payload.get("data", []) or []:
            start_raw = f.get("starting_at")
            if not start_raw:
                continue
            try:
                dt = datetime.fromisoformat(str(start_raw).replace("Z", "+00:00"))
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
            except ValueError:
                continue
            out.append(
                SportmonksFixture(
                    fixture_id=int(f["id"]),
                    name=str(f.get("name", "")),
                    starting_at=dt,
                    home_team=SportmonksClient._participant_name(f, "home"),
                    away_team=SportmonksClient._participant_name(f, "away"),
                    home_score=SportmonksClient._score(f, "home"),
                    away_score=SportmonksClient._score(f, "away"),
                    home_xg=SportmonksClient._xg(f, "home"),
                    away_xg=SportmonksClient._xg(f, "away"),
                )
            )
        return out
