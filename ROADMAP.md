# T.R.F SPORTS LAB ONE — Roadmap

## v0.1 — Pricing core ✅
- de-vig: proportional / power / Shin
- Poisson + Dixon-Coles score matrix
- market probabilities
- central/prudent EV and fair odds
- Brier/log-loss components
- conservative Kelly helper
- Airtable scientific ledger

## v0.2 — Structural model ✅
- historical match ingestion
- strict chronological cutoff
- time-decayed attack/defence strengths
- home advantage
- Dixon-Coles rho fitting
- optional xG-based target
- low-sample uncertainty
- deterministic model snapshots

## v0.3 — Walk-forward laboratory ✅ code / ⏳ real-data validation
- chronological train/validation windows
- fixture-level out-of-sample predictions
- same-timestamp anti-leakage batching
- calibration bins
- Brier / log loss
- historical 1X2 odds ingestion
- market/model residual comparison
- chronological market/model blend learning
- CLV / ROI / yield / drawdown helpers

### Remaining before promotion
- choose historical football dataset
- choose historical odds / closing-line source
- run large real-data walk-forward
- validate by competition and odds band
- define promotion criteria from observed distributions, not arbitrary guesses

## v0.4+ — Specialist engines
- corners
- cards
- penalties
- scorers / shots / shots on target
- correlation-aware combo builder

## Non-negotiables
- no look-ahead leakage
- no backfitting after one bad run
- price and probability remain separate
- prediction/tipster sites are not primary evidence
- PASS is a valid result
