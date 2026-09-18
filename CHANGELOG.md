# Changelog

## 0.7.0 — Real-time market map + Napoleon soft gate
- Added current The Odds API sport/odds endpoints.
- Added per-book de-vig then multi-book fair consensus.
- Added live 1X2 and exact-line totals market maps.
- Added minimum execution-price thresholds for configured EV.
- Added three-row Napoleon soft-gate queue by default.
- Added execution-price assessment and SHADOW VALUE/PASS output.
- Added offline payload fallback, tests and smoke workflow.
- Added manual GitHub Action for live scans once THE_ODDS_API_KEY is configured.

## 0.6.0 — Operational market-first scanner
- Added generic scanner for mutually exclusive market groups.
- Added consensus de-vig vs execution-price comparison.
- Added SHADOW VALUE / PASS gate from prudent execution EV.
- Default model weight remains zero after failed OOS model validation.
- Experimental model probabilities can trigger a Red-Team veto.
- Added double-chance probability derivation from fair 1X2 probabilities.
- Added CSV/JSON launch CLI, example input and tests.

## 0.5.0 — Real xG research layer
- Added keyless Understat match-level xG adapter for EPL, Bundesliga, Serie A, La Liga and Ligue 1.
- Added deterministic cross-provider team/date/score alignment against Football-Data closing markets.
- Added real-xG structural model walk-forward audit.
- Added chronological market+xG blend learning.
- Kept Understat forecast fields out of the model.

## 0.4.0 — Process proxy experiment
- Added shots/SOT/corners process ingestion.
- Added process-derived xG-like proxy for research.
- Real OOS audit showed the proxy was worse than goals-only and closing market.
- Process proxy is retired as an edge source.

## 0.3.1 — Data-provider layer
- Added Football-Data, Sportmonks and The Odds API adapters.

## 0.3.0 — Walk-forward laboratory
- Added strictly chronological OOS forecasts, calibration, historical odds comparison, blend learning and CLV/ROI helpers.

## 0.2.0 — Structural model
- Added time-decayed attack/defence strengths, home advantage and Dixon-Coles fitting.

## 0.1.0 — Initial engine
- Added de-vig, Poisson/Dixon-Coles pricing core, EV gates and tests.
