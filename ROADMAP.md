# T.R.F SPORTS LAB ONE — Roadmap

## v0.1 — Pricing core ✅
- de-vig: proportional / power / Shin
- Poisson + Dixon-Coles score matrix
- market probabilities
- central/prudent EV and fair odds
- Brier/log-loss components
- conservative Kelly helper
- Airtable scientific ledger

## v0.2 — Structural model ✅ on branch
- historical match ingestion
- strict chronological cutoff
- time-decayed attack/defence strengths
- home advantage
- Dixon-Coles rho fitting
- optional xG-based target
- low-sample uncertainty
- deterministic model snapshots
- reproducibility tests

## v0.3 — Walk-forward laboratory
- chronological train/validation windows
- fixture-by-fixture out-of-sample predictions
- calibration curves
- Brier / log loss / RPS where applicable
- CLV tracking
- ROI / yield / drawdown
- market-vs-model blend learned out of sample
- SHADOW promotion gates
- parameter search performed only inside past training windows

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
