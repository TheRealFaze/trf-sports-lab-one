# T.R.F SPORTS LAB ONE — Engine v0.7

A market-anchored football pricing engine designed to detect potential pricing discrepancies rather than manufacture picks.

## Pipeline

`DATE LOCK → MARKET MAP → RADAR → STRUCTURAL MODEL → RESIDUAL EDGE → RED TEAM → UNCERTAINTY → EXECUTION PRICE → LEDGER`

## Real-time launch mode

ONE can now build a live multi-book market map and generate a tiny Napoleon execution queue.

```bash
export THE_ODDS_API_KEY="..."
python scripts/live_one.py \
  --sports soccer_epl soccer_germany_bundesliga \
  --markets h2h,totals \
  --queue-top 3
```

Outputs:
- `live_output/live_scan.json`
- `live_output/execution_queue.csv`

Each queue row contains the fair probability, fair price and the exact minimum
Napoleon price required to clear the configured EV threshold.

Fill the Napoleon price in the queue CSV, then rerun with `--execution`.
Only then can a row become `SHADOW VALUE`.

See `docs/LIVE_PIPELINE.md`.

## Why market-first

Real walk-forward tests showed that the current goals-only structural model and a
shots/SOT/corners proxy did not beat the closing 1X2 market globally. ONE therefore
keeps the market consensus as the strong prior. Experimental models are not allowed
to receive probability weight merely because they disagree with the market.

## Research layers

- v0.1 pricing core.
- v0.2 structural model.
- v0.3 walk-forward lab.
- v0.4 process proxy — **retired after failed OOS validation**.
- v0.5 real-xG research.
- v0.6 operational market-first scanner.
- v0.7 live multi-book market map + Napoleon soft gate.

## Provider stack

- Football-Data.co.uk — historical results/process/closing-odds bootstrap.
- Understat — real-xG research feed.
- Sportmonks — planned production football/xG/lineup feed.
- The Odds API — current/historical multi-book market feed.
- Napoleon Sports Belgique — preferred execution venue, never the source of market truth.

## Scientific status

**SHADOW-EXECUTION.**

The live machine can identify prices worth checking and can qualify execution-price
discrepancies. It is not labelled a proven profitable system. Prospective CLV,
calibration and realized performance are still required before EDGE LAB promotion.
