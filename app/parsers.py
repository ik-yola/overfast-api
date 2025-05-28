from abc import ABC, abstractmethod
from typing import ClassVar

import httpx
from fastapi import status
from selectolax.lexbor import LexborHTMLParser

from .cache_manager import CacheManager
from .config import settings
from .enums import Locale
from .exceptions import ParserParsingError
from .helpers import read_csv_data_file
from .overfast_client import OverFastClient
from .overfast_logger import logger

# Abstract base parser for all parsers (CSV, HTML, API, etc.)
class AbstractParser(ABC):
    """Abstract Parser class to define generic parser behavior.

    A parser converts input data to structured dict/list data.
    This base handles the parse cache system.
    """
    cache_manager = CacheManager()

    def __init__(self, **_):
        self.data: dict | list | None = None

    @abstractmethod
    async def parse(self) -> None:
        """Parse data and store in self.data."""

    def filter_request_using_query(self, **_) -> dict | list:
        """Filter parsed data if subroutes use GET queries.

        Override in subclasses if needed. Default: return all data.
        """
        return self.data


class CSVParser(AbstractParser):
    """Parser for extracting data from local CSV files."""

    filename: str  # CSV file (without extension), also used for static file folder

    async def parse(self) -> None:
        """Read and parse CSV data into self.data."""
        self.csv_data = read_csv_data_file(self.filename)
        self.data = self.parse_data()

    @abstractmethod
    def parse_data(self) -> dict | list[dict]:
        """Implement this to parse self.csv_data."""

    def get_static_url(self, key: str, extension: str = "jpg") -> str:
        """Return URL of a local static file."""
        return f"{settings.app_base_url}/static/{self.filename}/{key}.{extension}"


class APIParser(AbstractParser):
    """Abstract API Parser for scraping Blizzard HTML pages.

    Requires an httpx.AsyncClient (shared by FastAPI app).
    """
    valid_http_codes: ClassVar[list] = [status.HTTP_200_OK]
    request_headers: ClassVar[dict] = {}

    def __init__(self, httpx_client: httpx.AsyncClient, **kwargs):
        self.blizzard_url = self.get_blizzard_url(**kwargs)
        self.overfast_client = OverFastClient(httpx_client)
        super().__init__(**kwargs)

    @property
    @abstractmethod
    def root_path(self) -> str:
        """Root path of the Blizzard URL (/en-us/career/, etc.)."""

    @abstractmethod
    def store_response_data(self, response: httpx.Response) -> None:
        """Save raw response data to instance variables."""

    @abstractmethod
    async def parse_data(self) -> dict | list[dict]:
        """Parse raw input data and return result."""

    async def parse(self) -> None:
        """Fetch from Blizzard, parse, and store data in self.data."""
        response = await self.overfast_client.get(
            url=self.blizzard_url,
            headers=self.request_headers,
        )
        if response.status_code not in self.valid_http_codes:
            raise self.overfast_client.blizzard_response_error_from_response(response)

        # Store and parse response data
        self.store_response_data(response)
        await self.parse_response_data()

    def get_blizzard_url(self, **kwargs) -> str:
        """Compose Blizzard URL with locale and root path."""
        locale = kwargs.get("locale") or Locale.ENGLISH_US
        return f"{settings.blizzard_host}/{locale}{self.root_path}"

    async def parse_response_data(self) -> None:
        logger.info("Parsing data...")
        try:
            self.data = await self.parse_data()
        except (AttributeError, KeyError, IndexError, TypeError) as error:
            raise ParserParsingError(repr(error)) from error


class HTMLParser(APIParser):
    """Parser for Blizzard HTML responses (using selectolax)."""
    request_headers: ClassVar[dict] = {"Accept": "text/html"}

    def store_response_data(self, response: httpx.Response) -> None:
        """Save main HTML tag for further parsing."""
        self.create_parser_tag(response.text)

    def create_parser_tag(self, html_content: str) -> None:
        self.root_tag = LexborHTMLParser(html_content).css_first(
            "div.main-content,main"
        )


class JSONParser(APIParser):
    """Parser for Blizzard JSON API responses."""
    request_headers: ClassVar[dict] = {"Accept": "application/json"}

    def store_response_data(self, response: httpx.Response) -> None:
        """Save JSON data for further parsing."""
        self.json_data = response.json()
