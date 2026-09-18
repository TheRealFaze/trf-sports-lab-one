# LIVE-001 — Real-time market pipeline

ONE can now build the MARKET MAP directly from a multi-book odds feed.

## Architecture

```
The Odds API
   ↓
per-book de-vig
   ↓
multi-book fair consensus
   ↓
execution threshold
   ↓
TOP-3 Napoleon soft gate
   ↓
Napoleon price entered
   ↓
SHADOW VALUE / PASS
   ↓
ledger / prospective CLV
```

The market feed is **not** the execution bookmaker. This separation is mandatory.

## Why the queue exists

Napoleon does not expose a supported connector/API in this project. ONE therefore
does not scrape it endlessly.

Instead, the live scan creates at most three **CHECK PRICE** rows by default.
Each row already contains:

- fair probability;
- fair odds;
- number of contributing bookmakers;
- best observed market price;
- exact minimum Napoleon price required to clear the EV threshold.

Example:

```
Napoleon threshold >= 1.91
```

If Napoleon is below 1.91, PASS immediately.
If Napoleon is at/above 1.91, enter the price in the same CSV and rerun the
assessment.

A CHECK PRICE row is **not a prediction or bet**. Edge exists only after the
execution price has been compared.

## Secret

Create an API key with The Odds API and set:

```bash
export THE_ODDS_API_KEY="..."
```

Never commit it.

For GitHub Actions add repository secret:

`THE_ODDS_API_KEY`

## Discover currently supported football keys

```bash
python scripts/live_one.py --list-sports
```

## Run a live market map

```bash
python scripts/live_one.py \
  --sports soccer_epl soccer_germany_bundesliga \
  --markets h2h,totals \
  --regions eu,uk \
  --min-books 3 \
  --min-ev 0.02 \
  --queue-top 3
```

Outputs:

- `live_output/live_scan.json`
- `live_output/execution_queue.csv`

## Napoleon soft gate

Open `execution_queue.csv`, check only the requested rows at Napoleon, and fill:

- `execution_source` = `Napoleon`
- `execution_odds` = the observed decimal price

Then rerun:

```bash
python scripts/live_one.py \
  --sports soccer_epl soccer_germany_bundesliga \
  --execution live_output/execution_queue.csv
```

Only `QUALIFY / SHADOW VALUE` rows have cleared the configured execution-price
threshold.

## Current markets

The live consensus layer currently supports:

- 1X2 / h2h;
- match totals at exact lines exposed by the provider.

BTTS, corners, cards and player markets remain specialist extensions. They
should be added only when the market feed exposes complete mutually-exclusive
price groups and the source quality is acceptable.

## Scientific status

This is **SHADOW-EXECUTION**.

The current structural model has not earned positive probability weight in live
pricing. The market consensus supplies the central/prudent probability for now.
Future independent models can gain weight only through chronological OOS
calibration.

The machine is designed to start collecting prospective price/CLV evidence now
instead of waiting for a hypothetical perfect model.
