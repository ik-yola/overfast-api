"""Overwatch Maps Controller module"""

from typing import ClassVar

from fastapi import Request, Response

from app.config import settings
from app.exceptions import ParserBlizzardError, ParserParsingError
from app.helpers import overfast_internal_error
from app.overfast_logger import logger

from ..parsers.overwatch_maps_parser import OverwatchMapsParser


class GetOverwatchMapsController:
    """Overwatch Maps Controller used to retrieve a simplified list of
    Overwatch maps for overlay applications. Returns only name and screenshot
    data optimized for Overwolf apps.
    
    This controller bypasses caching to work without Redis setup.
    """

    parser_classes: ClassVar[list] = [OverwatchMapsParser]
    timeout = settings.csv_cache_timeout

    def __init__(self, request: Request, response: Response):
        self.request = request
        self.response = response
        # Grab the shared HTTPX AsyncClient from app.state (not needed for CSV but consistent)
        self.httpx_client = request.app.state.httpx_client

    @classmethod
    def get_human_readable_timeout(cls) -> str:
        """Return human readable timeout for documentation"""
        return f"{cls.timeout} seconds"

    async def process_request(self, **kwargs) -> list[dict]:
        """
        Main method to process request and return data.
        
        This version bypasses caching and directly processes the request.
        """
        logger.info("Processing Overwatch maps request...")
        
        # Instantiate the parser
        parser = OverwatchMapsParser(**kwargs)

        try:
            # Parse the data
            await parser.parse()
        except ParserBlizzardError as error:
            raise error  # Let the router handle HTTPException
        except ParserParsingError as error:
            raise overfast_internal_error("overwatch maps", error) from error

        # Filter parser data if needed
        logger.info("Filtering the data using query...")
        computed_data = parser.filter_request_using_query(**kwargs)

        logger.info("Done ! Returning filtered data...")
        return computed_data
