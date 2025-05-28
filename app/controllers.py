"""Abstract API Controller module"""

from abc import ABC, abstractmethod

from fastapi import HTTPException, Request, Response

from .cache_manager import CacheManager
from .config import settings
from .exceptions import ParserBlizzardError, ParserParsingError
from .helpers import get_human_readable_duration, overfast_internal_error
from .overfast_logger import logger

class AbstractController(ABC):
    """Generic Abstract API Controller.

    A controller can use several parsers (one parser = one Blizzard page).
    Handles API Cache logic.
    """

    # Redis cache manager
    cache_manager = CacheManager()

    def __init__(self, request: Request, response: Response):
        self.cache_key = CacheManager.get_cache_key_from_request(request)
        self.response = response
        self.request = request
        # Grab the shared HTTPX AsyncClient from app.state
        self.httpx_client = request.app.state.httpx_client

    @property
    @classmethod
    @abstractmethod
    def parser_classes(cls) -> list[type]:
        """Parser classes used for this controller"""

    @property
    @classmethod
    @abstractmethod
    def timeout(cls) -> int:
        """Cache TTL for this controller"""

    @classmethod
    def get_human_readable_timeout(cls) -> str:
        return get_human_readable_duration(cls.timeout)

    async def process_request(self, **kwargs) -> dict:
        """
        Main method to process request and return data.

        Steps:
        1. Instantiate all parser classes, passing shared httpx_client.
        2. For each parser: parse, filter, and gather data.
        3. Merge data (if multiple parsers).
        4. Update API cache and return result.
        """
        parsers_data = []
        for parser_class in self.parser_classes:
            # Always pass the shared httpx_client to the parser!
            parser = parser_class(httpx_client=self.httpx_client, **kwargs)

            try:
                await parser.parse()
            except ParserBlizzardError as error:
                raise HTTPException(
                    status_code=error.status_code,
                    detail=error.message,
                ) from error
            except ParserParsingError as error:
                raise overfast_internal_error(parser.blizzard_url, error) from error

            # Filter parser data if needed
            logger.info("Filtering the data using query...")
            parsers_data.append(parser.filter_request_using_query(**kwargs))

        # Merge data from all parsers if more than one
        computed_data = self.merge_parsers_data(parsers_data, **kwargs)

        # Update API Cache
        self.cache_manager.update_api_cache(self.cache_key, computed_data, self.timeout)

        # Set cache TTL header
        self.response.headers[settings.cache_ttl_header] = str(self.timeout)

        logger.info("Done ! Returning filtered data...")
        return computed_data

    def merge_parsers_data(self, parsers_data: list[dict | list], **_) -> dict | list:
        """
        Merge data from all parsers. Override for multi-parser controllers.
        """
        return parsers_data[0]
