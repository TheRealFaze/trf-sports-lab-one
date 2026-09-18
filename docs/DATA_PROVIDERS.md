# DATA PROVIDERS — DATA-001

## Decision

ONE uses a layered data strategy.

### 1. Bootstrap / free historical validation: Football-Data.co.uk

Purpose:
- get a real walk-forward laboratory running immediately without a paid API;
- historical results, match statistics and bookmaker odds;
- use closing-average 1X2 odds where available.

Rules:
- prefer `AvgCH / AvgCD / AvgCA`;
- next prefer Bet365 closing;
- Pinnacle closing is fallback only;
- never use market `Max` odds as a consensus probability because the three outcomes can come from different books;
- unsuffixed odds are snapshots, not closing prices;
- normalize team names before cross-provider joins.

ONE's default bootstrap range is **2019/20 through 2025/26**, because Football-Data documents a distinct closing-odds set from 2019/20 onward.

### 2. Production structural feed: Sportmonks

Purpose:
- fixture IDs and phases;
- historical/live scores;
- statistics;
- lineups/player context;
- xG fixture data;
- future specialist engines.

Environment variable:

`SPORTMONKS_API_TOKEN`

ONE deliberately does not use Sportmonks "predictions" as primary model evidence. We want the raw/process inputs.

### 3. Production market feed: The Odds API

Purpose:
- current multi-book market map;
- historical market snapshots;
- market movement;
- event-level historical odds;
- later CLV/closing-price reconstruction.

Environment variable:

`THE_ODDS_API_KEY`

Historical endpoints are paid. Provider docs state:
- featured historical markets from June 2020;
- 10-minute snapshots initially;
- 5-minute snapshots from September 2022;
- additional markets from May 2023.

## Secret handling

Do not paste tokens into source code.

Local:
```bash
export SPORTMONKS_API_TOKEN="..."
export THE_ODDS_API_KEY="..."
```

GitHub Actions:
- repository Settings
- Secrets and variables
- Actions
- create `SPORTMONKS_API_TOKEN`
- create `THE_ODDS_API_KEY`

## Free bootstrap command

```bash
python scripts/bootstrap_football_data.py
```

Default leagues:
- E0 Premier League
- D1 Bundesliga
- I1 Serie A
- SP1 La Liga
- F1 Ligue 1
- N1 Eredivisie
- B1 Belgian Pro League
- P1 Primeira Liga

Default seasons:
- 2019/20 through 2025/26

This gives ONE a real historical score + closing-market dataset before any paid integration is required.

## Scientific rule

Provider selection is not an edge.

Any data feed must pass:
- timestamp normalization;
- duplicate checks;
- missingness profile;
- team identity normalization;
- phase/competition validation;
- odds-column provenance;
- opening/current/closing classification;
- no post-kickoff leakage into pre-match backtests.
