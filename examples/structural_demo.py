from datetime import datetime, timezone

from trf_one.structural import DixonColesStructuralModel, MatchRecord, StructuralConfig

rows = [
    MatchRecord(datetime(2026, 8, 1, tzinfo=timezone.utc), "Alpha", "Beta", 2, 0),
    MatchRecord(datetime(2026, 8, 8, tzinfo=timezone.utc), "Gamma", "Alpha", 1, 2),
    MatchRecord(datetime(2026, 8, 15, tzinfo=timezone.utc), "Beta", "Gamma", 1, 1),
    MatchRecord(datetime(2026, 8, 22, tzinfo=timezone.utc), "Alpha", "Gamma", 3, 1),
    MatchRecord(datetime(2026, 8, 29, tzinfo=timezone.utc), "Beta", "Alpha", 0, 1),
    MatchRecord(datetime(2026, 9, 5, tzinfo=timezone.utc), "Gamma", "Beta", 2, 1),
]

model = DixonColesStructuralModel(StructuralConfig(max_iter=1200)).fit(rows)
print(model.forecast("Alpha", "Beta").to_dict())
