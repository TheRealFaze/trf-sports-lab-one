from trf_one import devig, score_matrix, market_probs_from_matrix, evaluate_edge

# 1X2 market, example only.
market = devig([1.80, 3.70, 4.60], method="shin")
print("De-vigged 1X2:", market, "sum=", sum(market))

# Structural goal model example.
matrix = score_matrix(lambda_home=1.65, lambda_away=0.95, rho=-0.08)
probs = market_probs_from_matrix(matrix)
print("Structural probabilities:", probs)

# Price test example.
assessment = evaluate_edge(
    market_probability=0.54,
    model_probability=0.61,
    prudent_low=0.57,
    prudent_high=0.65,
    available_odds=1.90,
)
print("Edge assessment:", assessment.to_dict())
