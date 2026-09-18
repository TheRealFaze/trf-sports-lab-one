from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

from .devig import devig


@dataclass(frozen=True)
class ConsensusQuote:
    fixture_id: str
    sport: str
    commence_time: datetime
    home_team: str
    away_team: str
    market_group: str
    selection: str
    line: Optional[float]
    fair_probability: float
    fair_odds: float
    bookmakers: int
    best_market_odds: float
    snapshot_time: datetime

    def to_dict(self) -> Dict[str, object]:
        data = asdict(self)
        data["commence_time"] = self.commence_time.isoformat()
        data["snapshot_time"] = self.snapshot_time.isoformat()
        return data


@dataclass(frozen=True)
class ExecutionQueueItem:
    fixture_id: str
    sport: str
    commence_time: datetime
    home_team: str
    away_team: str
    market_group: str
    selection: str
    line: Optional[float]
    fair_probability: float
    fair_odds: float
    required_execution_odds: float
    best_market_odds: float
    bookmakers: int
    priority_ratio: float
    status: str = "CHECK PRICE"

    def to_dict(self) -> Dict[str, object]:
        data = asdict(self)
        data["commence_time"] = self.commence_time.isoformat()
        return data


@dataclass(frozen=True)
class ExecutionPrice:
    fixture_id: str
    market_group: str
    selection: str
    execution_odds: float
    execution_source: str = "Napoleon"
    line: Optional[float] = None

    def __post_init__(self) -> None:
        if self.execution_odds <= 1:
            raise ValueError("execution_odds must be > 1")


@dataclass(frozen=True)
class LiveAssessment:
    fixture_id: str
    sport: str
    commence_time: datetime
    home_team: str
    away_team: str
    market_group: str
    selection: str
    line: Optional[float]
    fair_probability: float
    fair_odds: float
    execution_odds: float
    execution_source: str
    ev: float
    threshold_odds: float
    bookmakers: int
    decision: str
    tier: str

    def to_dict(self) -> Dict[str, object]:
        data = asdict(self)
        data["commence_time"] = self.commence_time.isoformat()
        return data


def _canonical_h2h_selection(name: str, home: str, away: str) -> Optional[str]:
    if name == home:
        return "H"
    if name == away:
        return "A"
    if name.strip().lower() == "draw":
        return "D"
    return None


def _parse_time(value: str) -> datetime:
    dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _consensus_from_complete_books(
    book_rows: Sequence[Dict[str, float]],
    ordered_selections: Sequence[str],
    *,
    devig_method: str,
) -> Tuple[Dict[str, float], Dict[str, float]]:
    if not book_rows:
        raise ValueError("No complete bookmaker rows")

    fair_rows: List[Dict[str, float]] = []
    for row in book_rows:
        odds = [row[s] for s in ordered_selections]
        fair = devig(odds, method=devig_method)
        fair_rows.append({s: p for s, p in zip(ordered_selections, fair)})

    n = len(fair_rows)
    consensus = {
        s: sum(r[s] for r in fair_rows) / n
        for s in ordered_selections
    }
    best = {
        s: max(r[s] for r in book_rows)
        for s in ordered_selections
    }
    return consensus, best


def build_consensus_quotes(
    events: Iterable[dict],
    *,
    sport: str,
    fetched_at: Optional[datetime] = None,
    devig_method: str = "shin",
    min_books: int = 3,
    market_keys: Sequence[str] = ("h2h", "totals"),
) -> List[ConsensusQuote]:
    """Build fair multi-book football quotes by de-vigging each bookmaker first.

    Supported market keys:
    - h2h -> H/D/A
    - totals -> OVER/UNDER at each exact point

    Books missing one side of a complete market group are excluded from that group.
    """
    if min_books < 1:
        raise ValueError("min_books must be >= 1")
    snapshot = fetched_at or datetime.now(timezone.utc)
    if snapshot.tzinfo is None:
        snapshot = snapshot.replace(tzinfo=timezone.utc)

    quotes: List[ConsensusQuote] = []

    for event in events:
        fixture_id = str(event.get("id") or "")
        home = str(event.get("home_team") or "")
        away = str(event.get("away_team") or "")
        commence_raw = event.get("commence_time")
        if not fixture_id or not home or not away or not commence_raw:
            continue
        commence = _parse_time(str(commence_raw))

        books = [b for b in event.get("bookmakers", []) if isinstance(b, dict)]

        if "h2h" in market_keys:
            complete_books: List[Dict[str, float]] = []
            for book in books:
                market = next(
                    (m for m in book.get("markets", []) if m.get("key") == "h2h"),
                    None,
                )
                if not market:
                    continue
                row: Dict[str, float] = {}
                for outcome in market.get("outcomes", []):
                    name = str(outcome.get("name") or "")
                    price = outcome.get("price")
                    selection = _canonical_h2h_selection(name, home, away)
                    if selection and isinstance(price, (int, float)) and price > 1:
                        row[selection] = float(price)
                if all(s in row for s in ("H", "D", "A")):
                    complete_books.append(row)

            if len(complete_books) >= min_books:
                fair, best = _consensus_from_complete_books(
                    complete_books, ("H", "D", "A"), devig_method=devig_method
                )
                for selection in ("H", "D", "A"):
                    p = fair[selection]
                    quotes.append(
                        ConsensusQuote(
                            fixture_id=fixture_id,
                            sport=sport,
                            commence_time=commence,
                            home_team=home,
                            away_team=away,
                            market_group="1X2",
                            selection=selection,
                            line=None,
                            fair_probability=p,
                            fair_odds=1.0 / p,
                            bookmakers=len(complete_books),
                            best_market_odds=best[selection],
                            snapshot_time=snapshot,
                        )
                    )

        if "totals" in market_keys:
            # Each bookmaker can expose one or more points. Build one consensus
            # only when OVER and UNDER exist at exactly the same line.
            by_line: Dict[float, List[Dict[str, float]]] = {}
            for book in books:
                market = next(
                    (m for m in book.get("markets", []) if m.get("key") == "totals"),
                    None,
                )
                if not market:
                    continue
                per_line: Dict[float, Dict[str, float]] = {}
                for outcome in market.get("outcomes", []):
                    name = str(outcome.get("name") or "").strip().upper()
                    price = outcome.get("price")
                    point = outcome.get("point")
                    if (
                        name in {"OVER", "UNDER"}
                        and isinstance(price, (int, float))
                        and price > 1
                        and isinstance(point, (int, float))
                    ):
                        line = float(point)
                        per_line.setdefault(line, {})[name] = float(price)
                for line, row in per_line.items():
                    if "OVER" in row and "UNDER" in row:
                        by_line.setdefault(line, []).append(row)

            for line, complete_books in sorted(by_line.items()):
                if len(complete_books) < min_books:
                    continue
                fair, best = _consensus_from_complete_books(
                    complete_books, ("OVER", "UNDER"), devig_method=devig_method
                )
                for selection in ("OVER", "UNDER"):
                    p = fair[selection]
                    quotes.append(
                        ConsensusQuote(
                            fixture_id=fixture_id,
                            sport=sport,
                            commence_time=commence,
                            home_team=home,
                            away_team=away,
                            market_group=f"TOTALS_{line:g}",
                            selection=selection,
                            line=line,
                            fair_probability=p,
                            fair_odds=1.0 / p,
                            bookmakers=len(complete_books),
                            best_market_odds=best[selection],
                            snapshot_time=snapshot,
                        )
                    )

    return sorted(
        quotes,
        key=lambda q: (
            q.commence_time,
            q.home_team,
            q.away_team,
            q.market_group,
            q.selection,
        ),
    )


def required_execution_odds(fair_probability: float, min_ev: float = 0.02) -> float:
    if not 0 < fair_probability < 1:
        raise ValueError("fair_probability must be in (0,1)")
    if min_ev < 0:
        raise ValueError("min_ev must be >= 0")
    return (1.0 + min_ev) / fair_probability


def build_execution_queue(
    quotes: Sequence[ConsensusQuote],
    *,
    min_ev: float = 0.02,
    top: int = 3,
    min_fair_odds: float = 1.25,
    max_fair_odds: float = 6.0,
    one_per_fixture: bool = True,
) -> List[ExecutionQueueItem]:
    """Prioritize a tiny manual Napoleon check queue.

    This is NOT a pick ranking. Priority is based on market liquidity plus how
    close the best observed market price already is to the required execution
    threshold. Edge is not declared until Napoleon/execution price is supplied.
    """
    if top < 1:
        return []

    candidates: List[ExecutionQueueItem] = []
    for q in quotes:
        if not min_fair_odds <= q.fair_odds <= max_fair_odds:
            continue
        threshold = required_execution_odds(q.fair_probability, min_ev)
        ratio = q.best_market_odds / threshold
        candidates.append(
            ExecutionQueueItem(
                fixture_id=q.fixture_id,
                sport=q.sport,
                commence_time=q.commence_time,
                home_team=q.home_team,
                away_team=q.away_team,
                market_group=q.market_group,
                selection=q.selection,
                line=q.line,
                fair_probability=q.fair_probability,
                fair_odds=q.fair_odds,
                required_execution_odds=threshold,
                best_market_odds=q.best_market_odds,
                bookmakers=q.bookmakers,
                priority_ratio=ratio,
            )
        )

    candidates.sort(
        key=lambda x: (x.priority_ratio, x.bookmakers),
        reverse=True,
    )

    if not one_per_fixture:
        return candidates[:top]

    selected: List[ExecutionQueueItem] = []
    seen = set()
    for item in candidates:
        if item.fixture_id in seen:
            continue
        selected.append(item)
        seen.add(item.fixture_id)
        if len(selected) >= top:
            break
    return selected


def _line_key(line: Optional[float]) -> str:
    return "" if line is None else f"{line:g}"


def assess_execution_prices(
    quotes: Sequence[ConsensusQuote],
    prices: Sequence[ExecutionPrice],
    *,
    min_ev: float = 0.02,
) -> List[LiveAssessment]:
    quote_map = {
        (q.fixture_id, q.market_group, q.selection, _line_key(q.line)): q
        for q in quotes
    }
    out: List[LiveAssessment] = []

    for price in prices:
        q = quote_map.get(
            (
                price.fixture_id,
                price.market_group,
                price.selection,
                _line_key(price.line),
            )
        )
        if q is None:
            continue
        ev = q.fair_probability * price.execution_odds - 1.0
        threshold = required_execution_odds(q.fair_probability, min_ev)
        qualify = ev >= min_ev
        out.append(
            LiveAssessment(
                fixture_id=q.fixture_id,
                sport=q.sport,
                commence_time=q.commence_time,
                home_team=q.home_team,
                away_team=q.away_team,
                market_group=q.market_group,
                selection=q.selection,
                line=q.line,
                fair_probability=q.fair_probability,
                fair_odds=q.fair_odds,
                execution_odds=price.execution_odds,
                execution_source=price.execution_source,
                ev=ev,
                threshold_odds=threshold,
                bookmakers=q.bookmakers,
                decision="QUALIFY" if qualify else "PASS",
                tier="SHADOW VALUE" if qualify else "PASS",
            )
        )

    return sorted(out, key=lambda x: x.ev, reverse=True)
