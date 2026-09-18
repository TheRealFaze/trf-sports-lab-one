# T.R.F SPORTS LAB ONE — Engine v0.2

A market-anchored football pricing engine designed to detect potential pricing discrepancies rather than manufacture picks.

## Pipeline

`DATE LOCK → MARKET MAP → RADAR → STRUCTURAL MODEL → RESIDUAL EDGE → RED TEAM → UNCERTAINTY → EXECUTION PRICE → LEDGER`

## v0.1 — pricing core

- proportional, power and Shin de-vig;
- Poisson / Dixon-Coles score matrix;
- 1X2, double-chance, totals, BTTS and team-to-score probabilities;
- market-vs-model edge evaluation;
- central and prudent EV;
- fair price / prudent fair price;
- robust / fragile / no-edge gate;
- Brier and log-loss components;
- conservative fractional Kelly helper.

## v0.2 — structural model

- historical match ingestion from a simple CSV contract;
- strict `as_of` cutoff for walk-forward-safe fitting;
- exponentially time-decayed matches;
- learned attack and defence strengths;
- learned global scoring level and home advantage;
- deterministic Adam optimisation with L2 regularisation;
- Dixon-Coles low-score rho fitted on a bounded deterministic grid;
- optional goals, xG, or goals/xG-blend target;
- approximate lambda uncertainty that widens for low-sample or unseen teams;
- deterministic model snapshots and restoration;
- synthetic tests for strength ordering, cutoff integrity and reproducibility.

## Data contract

Minimum CSV columns:

```
date,home_team,away_team,home_goals,away_goals
```

Optional:

```
home_xg,away_xg
```

## Quick start

```bash
pip install -e .
python examples/demo.py
python examples/structural_demo.py
pytest -q
```

## Current limitations

v0.2 is a structural baseline, not a proven betting edge. In particular:

- model-market blend weights are not calibrated yet;
- uncertainty is approximate, not posterior uncertainty;
- no automatic bookmaker-odds ingestion exists yet;
- no walk-forward performance lab exists yet;
- corners, cards and player markets still require specialist engines.

Those belong to v0.3+ and must be validated out of sample.

## Airtable

The research ledger lives in the connected Airtable base **T.R.F SPORTS LAB ONE**:

- `PICKS`
- `MARKET SNAPSHOTS`
- `MODEL VERSIONS`
- `RUNS`

## Governance

Material changes receive a new model version. No model is promoted from SHADOW to EDGE LAB because of a few winning bets. Promotion depends on walk-forward calibration, CLV, ROI and drawdown evidence.
