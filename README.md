# T.R.F SPORTS LAB ONE — Engine v0.3.1

A market-anchored football pricing engine designed to detect potential pricing discrepancies rather than manufacture picks.

## Pipeline

`DATE LOCK → MARKET MAP → RADAR → STRUCTURAL MODEL → RESIDUAL EDGE → RED TEAM → UNCERTAINTY → EXECUTION PRICE → LEDGER`

## v0.1 — pricing core

- proportional, power and Shin de-vig;
- Poisson / Dixon-Coles score matrix;
- market-vs-model edge evaluation;
- central/prudent EV and fair prices;
- Brier/log-loss helpers;
- conservative fractional Kelly.

## v0.2 — structural model

- historical match ingestion;
- strict `as_of` cutoff;
- time-decayed attack/defence strengths;
- learned home advantage and scoring intercept;
- Dixon-Coles low-score rho;
- optional goals / xG / blended target;
- low-sample lambda uncertainty;
- deterministic model snapshots.

## v0.3 — walk-forward laboratory

- expanding or rolling chronological walk-forward predictions;
- same-timestamp batching to prevent within-round leakage;
- out-of-sample 1X2 Brier score, log loss and accuracy;
- binary calibration bins;
- historical 1X2 quote ingestion;
- de-vigged market-vs-model comparison;
- geometric market/model probability blending;
- blend weight learned only from earlier out-of-sample observations;
- cold-start rule: market-only until enough history exists;
- ROI / yield / max-drawdown / price-CLV helpers;
- explicit tests that future results cannot change earlier forecasts.

## v0.3.1 — data-provider layer

Selected stack:

- **Football-Data.co.uk** — free historical bootstrap / first real backtest;
- **Sportmonks** — production structural/process feed (fixtures, stats, xG, lineups);
- **The Odds API** — production multi-book market map and historical snapshots.

The paid providers are optional for bootstrapping. Start with the free historical dataset:

```bash
python scripts/bootstrap_football_data.py
```

The default bootstrap covers E0, D1, I1, SP1, F1, N1, B1 and P1 from 2019/20 through 2025/26 and writes normalized match, 1X2-odds and quality CSV files.

Provider details and secret setup: `docs/DATA_PROVIDERS.md`.

## Historical data contracts

Match CSV:

```
date,home_team,away_team,home_goals,away_goals[,home_xg,away_xg]
```

Historical 1X2 quote CSV:

```
date,home_team,away_team,home_odds,draw_odds,away_odds[,bookmaker,snapshot_type]
```

## Quick start

```bash
pip install -e .
pytest -q
python scripts/bootstrap_football_data.py
```

## Scientific status

**SHADOW.**

The engine now has the code path from raw historical results/odds to a real walk-forward lab. That still does not prove an edge. Promotion to EDGE LAB depends on out-of-sample calibration, market-relative Brier/log loss, CLV, ROI and drawdown evidence.

## Airtable

The connected **T.R.F SPORTS LAB ONE** base contains:

- `PICKS`
- `MARKET SNAPSHOTS`
- `MODEL VERSIONS`
- `RUNS`

## Governance

Material changes receive a new model version. No tuning is allowed on final evaluation windows, and market/model blend weights must be learned using only information available before each evaluated fixture.
