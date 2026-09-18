"""T.R.F SPORTS LAB ONE — market-anchored edge engine."""

from .devig import devig, proportional_devig, power_devig, shin_devig
from .poisson import score_matrix, market_probs_from_matrix
from .edge import evaluate_edge, PickEvaluation
from .structural import (
    DixonColesStructuralModel,
    MatchRecord,
    StructuralConfig,
    LambdaPrediction,
    StructuralForecast,
)
from .backtest import (
    WalkForwardConfig,
    WalkForwardPrediction,
    Historical1X2Quote,
    walk_forward_predict,
    walk_forward_market_blend,
    summarize_predictions,
    calibration_bins,
    betting_summary,
)

__all__ = [
    "devig",
    "proportional_devig",
    "power_devig",
    "shin_devig",
    "score_matrix",
    "market_probs_from_matrix",
    "evaluate_edge",
    "PickEvaluation",
    "DixonColesStructuralModel",
    "MatchRecord",
    "StructuralConfig",
    "LambdaPrediction",
    "StructuralForecast",
    "WalkForwardConfig",
    "WalkForwardPrediction",
    "Historical1X2Quote",
    "walk_forward_predict",
    "walk_forward_market_blend",
    "summarize_predictions",
    "calibration_bins",
    "betting_summary",
]
