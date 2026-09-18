# ONE LAUNCH MODE — SHADOW-EXECUTION

This is the first operational pronostic scanner.

It is deliberately market-first because the current TRF structural models have
not yet beaten the closing market out of sample.

## What it does

For each mutually exclusive market group:

1. ingest independent consensus/sharp odds;
2. remove the bookmaker margin;
3. obtain market fair probabilities;
4. compare the execution price (e.g. Napoleon) with market fair price;
5. optionally read an experimental model probability;
6. use the model as a Red-Team veto by default, not as an unearned probability boost;
7. qualify only execution prices clearing the configured prudent EV threshold.

Default model weight is **0**. That is intentional and follows the real OOS
evidence collected by ONE.

## Supported immediately

Any mutually exclusive quoted group:
- 1X2;
- BTTS YES/NO;
- Over/Under at one line;
- cards/corners yes-no or over-under markets;
- other complete two-way or three-way groups.

Double chance fair probabilities can be derived from a de-vigged 1X2 group with
`derive_double_chance_probabilities()`.

## Input CSV

Required:
- fixture_id
- market_group
- selection
- consensus_odds
- execution_odds

Recommended:
- kickoff
- competition
- home_team
- away_team
- consensus_source
- execution_source
- model_probability

**Consensus and execution must be genuinely independent sources.** Using the
same bookmaker as both benchmark and execution is rejected by default.

## Run

```bash
python scripts/launch_one.py examples/launch_market_sample.csv --output one_scan.json
```

A normal launch should keep:

```
--model-weight 0
```

until walk-forward calibration proves a non-zero weight deserves to exist.

## Status labels

- `SHADOW VALUE`: execution price is above de-vigged consensus fair price by
  the configured threshold and no model-veto is triggered.
- `PASS`: insufficient price, same-source benchmark, or strong model conflict.

SHADOW VALUE is a research/execution candidate, not a guarantee of profit.
