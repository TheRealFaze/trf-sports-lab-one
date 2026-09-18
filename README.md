# T.R.F SPORTS LAB ONE — Engine v0.3

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
```

## Scientific status

**SHADOW.**

v0.3 gives us the machinery to test ONE correctly, but it does not itself prove an edge. Real historical match data plus contemporaneous and closing market prices are now required. Promotion to EDGE LAB depends on out-of-sample calibration, CLV, ROI and drawdown rather than a few winning bets.

## Airtable

The connected **T.R.F SPORTS LAB ONE** base contains:

- `PICKS`
- `MARKET SNAPSHOTS`
- `MODEL VERSIONS`
- `RUNS`

## Governance

Material changes receive a new model version. No tuning is allowed on final evaluation windows, and market/model blend weights must be learned using only information available before each evaluated fixture.
