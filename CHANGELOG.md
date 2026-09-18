# Changelog

## 0.3.1 — Data-provider layer
- Selected Football-Data.co.uk as the free historical bootstrap source.
- Added keyless Football-Data season download/parser.
- Prefer market-average closing 1X2 odds when available.
- Added explicit non-closing fallback classification.
- Added Sportmonks client for raw fixture/stat/xG retrieval.
- Added The Odds API client for historical/current multi-book market snapshots.
- Added per-book de-vig then fair-probability consensus aggregation.
- Added provider secret handling through environment variables only.
- Added bootstrap script for 8 European leagues, including Belgian Pro League.
- Added provider normalization/unit tests and data-provider documentation.

## 0.3.0 — Walk-forward laboratory
- Added strictly chronological walk-forward forecasts.
- Added same-timestamp batching to prevent within-round leakage.
- Added 1X2 Brier, log loss, accuracy and calibration helpers.
- Added historical 1X2 quote ingestion.
- Added de-vigged market-vs-model comparison.
- Added geometric probability blending.
- Added chronological blend-weight learning from prior out-of-sample observations only.
- Added cold-start market-only behavior until calibration history is sufficient.
- Added ROI, yield, max drawdown and price-CLV helpers.
- Added explicit future-leakage tests.

## 0.2.0 — Structural model
- Added CSV historical-match ingestion and data-quality summary.
- Added strict `as_of` filtering to prevent future-match leakage.
- Added time-decayed attack and defence team strengths.
- Added learned home advantage and global scoring intercept.
- Added deterministic Adam optimisation with L2 regularisation.
- Added bounded Dixon-Coles rho fitting for low-score dependence.
- Added optional goals, xG and goals/xG-blend targets.
- Added approximate low-sample lambda uncertainty.
- Added deterministic model snapshots and restoration.
- Added structural and data tests.

## 0.1.0 — Initial engine
- Added proportional, power and Shin de-vig methods.
- Added Poisson / Dixon-Coles score matrix.
- Added derived 1X2, double-chance, totals, BTTS and team-to-score probabilities.
- Added market-vs-model edge evaluation with central and prudent EV.
- Added Brier and log-loss components.
- Added conservative fractional Kelly helper.
- Added automated tests and GitHub Actions CI.
- Added Airtable ledger integration design.
