# T.R.F SPORTS LAB ONE — Engine v0.5

A market-anchored football pricing engine designed to detect potential pricing discrepancies rather than manufacture picks.

## Pipeline

`DATE LOCK → MARKET MAP → RADAR → STRUCTURAL MODEL → RESIDUAL EDGE → RED TEAM → UNCERTAINTY → EXECUTION PRICE → LEDGER`

## Current layers

- v0.1 pricing core: de-vig, Poisson/Dixon-Coles, fair odds, EV.
- v0.2 structural model: time-decayed attack/defence + home advantage.
- v0.3 walk-forward lab: chronological OOS evaluation, calibration, market blending.
- v0.4 process proxy: shots/SOT/corners experiment; **retired after failed OOS validation**.
- v0.5 real xG research: keyless Understat match xG for EPL/Bundesliga/Serie A/La Liga/Ligue 1, aligned to Football-Data closing markets.

## Real xG audit

```bash
python scripts/bootstrap_football_data.py --output data/xg --divisions E0 D1 I1 SP1 F1 --years 2019 2020 2021 2022 2023 2024 2025
python scripts/bootstrap_understat_xg.py --output data/xg/understat_xg.csv
python scripts/run_real_xg_audit.py
```

The audit compares:
1. closing market,
2. goals-only structural model,
3. real-xG structural model,
4. chronological market + real-xG blend.

## Provider stack

- Football-Data.co.uk — free historical results/process/closing-odds bootstrap.
- Understat — free match-level xG research feed for five major European leagues.
- Sportmonks — planned broader production football/xG/lineup feed.
- The Odds API — planned timestamped market-history / movement feed.

## Scientific status

**SHADOW.** No betting rule is promoted because of a positive in-sample or discovery result. Market/model weights are learned only from earlier OOS observations.
