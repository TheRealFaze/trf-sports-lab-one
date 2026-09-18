# Changelog

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
