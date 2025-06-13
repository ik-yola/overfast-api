"""Multiple Profiles Parser module"""

from fastapi import HTTPException, status

from app.overfast_logger import logger
from app.parsers import AbstractParser

from ..controllers.get_player_career_controller import GetPlayerCareerController


class MultipleProfilesParser(AbstractParser):
    """Parser for retrieving multiple Overwatch player profiles in condensed format.
    
    This parser orchestrates multiple calls to the existing player career system
    to efficiently gather endorsement level and PC season data for multiple players.
    Bypasses caching for AWS Lambda deployment.
    """

    def __init__(self, httpx_client, **kwargs):
        super().__init__(**kwargs)
        self.httpx_client = httpx_client
        self.request = kwargs.get("request")
        self.response = kwargs.get("response")
        self.player_ids = kwargs.get("player_ids", [])

    async def parse(self) -> None:
        """Parse multiple player profiles and extract condensed data."""
        logger.info(f"Retrieving profiles for {len(self.player_ids)} players...")
        
        results = {}
        missing_players = []

        for player_id in self.player_ids:
            try:
                logger.debug(f"Processing player: {player_id}")
                
                # Use the existing GetPlayerCareerController to get player summary
                controller = GetPlayerCareerController(self.request, self.response)
                player_data = await controller.process_request(
                    summary=True,
                    player_id=player_id,
                )

                # Extract endorsement level
                endorsement_level = self._extract_endorsement_level(player_data)
                if endorsement_level is None:
                    logger.warning(f"Could not extract endorsement level for {player_id}")
                    missing_players.append(player_id)
                    continue

                # Extract PC season information only
                season = self._extract_pc_season(player_data)

                results[player_id] = {
                    "endorsementLevel": endorsement_level,
                    "season": season,
                }

            except HTTPException as e:
                if e.status_code == status.HTTP_404_NOT_FOUND:
                    logger.warning(f"Player not found: {player_id}")
                    missing_players.append(player_id)
                else:
                    # Re-raise other HTTP exceptions
                    raise

        # If any players are missing, raise 404 with details
        if missing_players:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error": f"Profiles not found: {', '.join(missing_players)}"},
            )

        self.data = results
        logger.info(f"Successfully retrieved {len(results)} profiles")

    def _extract_endorsement_level(self, player_data: dict) -> int | None:
        """Extract endorsement level from player data."""
        endorsement = player_data.get("endorsement")
        if not endorsement:
            return None
        
        level = endorsement.get("level")
        return level if level is not None else None

    def _extract_pc_season(self, player_data: dict) -> int:
        """Extract the PC competitive season from player data.
        
        Only checks PC platform as requested. Returns 0 if no competitive data.
        """
        competitive = player_data.get("competitive")
        if not competitive:
            return 0

        # Only check PC platform
        pc_data = competitive.get("pc")
        if pc_data and pc_data.get("season") is not None:
            return pc_data["season"]

        # Return 0 if no PC competitive data
        return 0

    def filter_request_using_query(self, **kwargs) -> dict:
        """Return the parsed data as-is since no filtering is needed."""
        return self.data
