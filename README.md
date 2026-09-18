# T.R.F SPORTS LAB ONE — Engine v0.6

A market-anchored football pricing engine designed to detect potential pricing discrepancies rather than manufacture picks.

## Pipeline

`DATE LOCK → MARKET MAP → RADAR → STRUCTURAL MODEL → RESIDUAL EDGE → RED TEAM → UNCERTAINTY → EXECUTION PRICE → LEDGER`

## Launchable now: SHADOW-EXECUTION

ONE now includes an operational pre-match scanner that can compare an independent
market consensus with an execution bookmaker price.

```bash
python scripts/launch_one.py examples/launch_market_sample.csv --output one_scan.json
```

Default launch logic:
- de-vig the consensus/sharp market;
- treat that fair market probability as the strong prior;
- compare Napoleon/other execution odds with fair price;
- require positive prudent EV;
- use the experimental structural model as a veto by default;
- do **not** give the structural model probability weight until OOS evidence earns it.

See `docs/LAUNCH_MODE.md`.

## Research layers

- v0.1 pricing core: de-vig, Poisson/Dixon-Coles, fair odds, EV.
- v0.2 structural model: time-decayed attack/defence + home advantage.
- v0.3 walk-forward lab: chronological OOS evaluation, calibration, market blending.
- v0.4 process proxy: shots/SOT/corners experiment; **retired after failed OOS validation**.
- v0.5 real xG research: independent real-xG experiment.
- v0.6 operational market-first scanner: **launchable in SHADOW-EXECUTION**.

## Provider stack

- Football-Data.co.uk — historical results/process/closing-odds bootstrap.
- Understat — real-xG research feed; connector remains experimental.
- Sportmonks — planned production football/xG/lineup feed.
- The Odds API — planned timestamped multi-book market-history/movement feed.
- Napoleon Sports Belgique — preferred execution venue, never the source of market truth.

## Scientific status

**SHADOW-EXECUTION.**

The machine can produce operational price-qualified candidates now, but its own
structural model has not demonstrated global superiority to the closing market.
That distinction is preserved deliberately.
