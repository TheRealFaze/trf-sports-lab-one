"""External data adapters for T.R.F SPORTS LAB ONE."""

from .football_data_uk import FootballDataUKClient, FootballDataSeason, FootballDataQuality, ProcessMatchRecord, season_code
from .the_odds_api import TheOddsAPIClient, OddsConsensus1X2
from .sportmonks import SportmonksClient, SportmonksFixture
from .understat import UnderstatClient, UnderstatXGMatch, FOOTBALL_DATA_TO_UNDERSTAT, normalize_team_name

__all__ = [
    "FootballDataUKClient","FootballDataSeason","FootballDataQuality","ProcessMatchRecord","season_code",
    "TheOddsAPIClient","OddsConsensus1X2","SportmonksClient","SportmonksFixture",
    "UnderstatClient","UnderstatXGMatch","FOOTBALL_DATA_TO_UNDERSTAT","normalize_team_name",
]
