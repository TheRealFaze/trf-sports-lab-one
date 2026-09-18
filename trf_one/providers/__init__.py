"""External data adapters for T.R.F SPORTS LAB ONE.

Adapters expose raw/normalized data but never make betting decisions.
Secrets are read from environment variables and must not be committed.
"""

from .football_data_uk import (
    FootballDataUKClient,
    FootballDataSeason,
    FootballDataQuality,
    season_code,
)
from .the_odds_api import TheOddsAPIClient, OddsConsensus1X2
from .sportmonks import SportmonksClient, SportmonksFixture

__all__ = [
    "FootballDataUKClient",
    "FootballDataSeason",
    "FootballDataQuality",
    "season_code",
    "TheOddsAPIClient",
    "OddsConsensus1X2",
    "SportmonksClient",
    "SportmonksFixture",
]
