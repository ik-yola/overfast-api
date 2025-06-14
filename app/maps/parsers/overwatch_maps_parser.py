"""Overwatch Maps Parser module"""

from app.overfast_logger import logger
from app.parsers import CSVParser


class OverwatchMapsParser(CSVParser):
    """Overwatch maps parser for simplified map data.
    
    Returns only name and screenshot for overlay applications,
    optimized for Overwolf integration.
    """

    filename = "maps"

    def parse_data(self) -> list[dict]:
        """Parse CSV data and return simplified map structure."""
        logger.info("Parsing maps data for Overwolf...")
        
        simplified_maps = []
        for map_dict in self.csv_data:
            simplified_maps.append({
                "name": map_dict["name"],
                "screenshot": self.get_static_url(map_dict["key"]),
            })
        
        logger.info(f"Parsed {len(simplified_maps)} maps")
        return simplified_maps

    def filter_request_using_query(self, **kwargs) -> list[dict]:
        """Return all maps data as-is since no filtering is needed for this endpoint."""
        return self.data
