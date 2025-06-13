"""Multiple Profiles Controller module"""

from typing import ClassVar

from fastapi import Request, Response

from app.config import settings
from app.exceptions import ParserBlizzardError, ParserParsingError
from app.helpers import overfast_internal_error
from app.overfast_logger import logger

from ..parsers.multiple_profiles_parser import MultipleProfilesParser


class GetMultipleProfilesController:
    """Multiple Profiles Controller used to retrieve condensed data for multiple
    Overwatch player profiles efficiently. Returns endorsement level and season
    data for multiple players in a single request.
    
    This controller bypasses caching to work without Redis setup.
    """

    parser_classes: ClassVar[list] = [MultipleProfilesParser]
    timeout = settings.career_path_cache_timeout

    def __init__(self, request: Request, response: Response):
        self.request = request
        self.response = response
        # Grab the shared HTTPX AsyncClient from app.state
        self.httpx_client = request.app.state.httpx_client

    @classmethod
    def get_human_readable_timeout(cls) -> str:
        """Return human readable timeout for documentation"""
        return f"{cls.timeout} seconds"

    async def process_request(self, **kwargs) -> dict:
        """
        Main method to process request and return data.
        
        This version bypasses caching and directly processes the request.
        """
        logger.info("Processing multiple profiles request...")
        
        # Instantiate the parser
        parser = MultipleProfilesParser(
            httpx_client=self.httpx_client,
            request=self.request,
            response=self.response,
            **kwargs
        )

        try:
            # Parse the data
            await parser.parse()
        except ParserBlizzardError as error:
            raise error  # Let the router handle HTTPException
        except ParserParsingError as error:
            raise overfast_internal_error("multiple profiles", error) from error

        # Filter parser data if needed
        logger.info("Filtering the data using query...")
        computed_data = parser.filter_request_using_query(**kwargs)

        logger.info("Done ! Returning filtered data...")
        return computed_data
