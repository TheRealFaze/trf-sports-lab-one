# T.R.F SPORTS LAB ONE — Engine v0.1

A market-anchored football pricing engine. It is designed to detect potential pricing discrepancies, not to manufacture picks.

## Pipeline

`DATE LOCK → MARKET MAP → RADAR → STRUCTURAL MODEL → RESIDUAL EDGE → RED TEAM → UNCERTAINTY → EXECUTION PRICE → LEDGER`

## What v0.1 implements

- proportional, power and Shin de-vig utilities;
- Poisson / Dixon-Coles score matrix;
- 1X2, double-chance, totals, BTTS and team-to-score probabilities from a score matrix;
- market-vs-model edge evaluation;
- central and prudent EV;
- fair price / prudent fair price;
- robust / fragile / no-edge gate;
- Brier and log-loss components;
- conservative fractional Kelly helper.

## What v0.1 deliberately does **not** claim

- It does not yet estimate attacking/defensive strengths from a historical dataset.
- It does not yet calibrate model-market weights from walk-forward data.
- It does not yet ingest live bookmaker odds automatically.
- It does not yet contain specialist corner/card/player models.

Those are subsequent versions and must be validated out of sample.

## Quick start

```bash
python examples/demo.py
pytest -q
```

## Airtable

The persistent research ledger lives in the connected Airtable base **T.R.F SPORTS LAB ONE** with tables:

- `PICKS`
- `MARKET SNAPSHOTS`
- `MODEL VERSIONS`
- `RUNS`

## Governance

The current scientific protocol is in `MASTER_PROTOCOL.txt`. Material changes should receive a new model version and be evaluated walk-forward rather than retrofitted to past results.
