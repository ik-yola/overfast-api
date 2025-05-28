import httpx
from fastapi import HTTPException, status

from .cache_manager import CacheManager
from .config import settings
from .helpers import send_discord_webhook_message
from .overfast_logger import logger

class OverFastClient:
    def __init__(self, httpx_client: httpx.AsyncClient):
        self.cache_manager = CacheManager()
        self.client = httpx_client  # <- Use the shared client

    async def get(self, url: str, **kwargs) -> httpx.Response:
        """Make an HTTP GET request with custom headers and retrieve the result"""

        # First, check if we're being rate limited
        self._check_rate_limit()

        # Make the API call
        try:
            response = await self.client.get(url, **kwargs)
        except httpx.TimeoutException as error:
            raise self._blizzard_response_error(
                status_code=0,
                error="Blizzard took more than 10 seconds to respond, resulting in a timeout",
            ) from error
        except httpx.RemoteProtocolError as error:
            raise self._blizzard_response_error(
                status_code=0,
                error="Blizzard closed the connection, no data could be retrieved",
            ) from error

        logger.debug("OverFast request done !")

        if response.status_code == status.HTTP_403_FORBIDDEN:
            raise self._blizzard_forbidden_error()

        return response

    # Remove aclose() method; it is not needed anymore, client is managed elsewhere

    def _check_rate_limit(self) -> None:
        if self.cache_manager.is_being_rate_limited():
            raise self._too_many_requests_response(
                retry_after=self.cache_manager.get_global_rate_limit_remaining_time()
            )

    def blizzard_response_error_from_response(
        self, response: httpx.Response
    ) -> HTTPException:
        return self._blizzard_response_error(response.status_code, response.text)

    @staticmethod
    def _blizzard_response_error(status_code: int, error: str) -> HTTPException:
        logger.error(
            "Received an error from Blizzard. HTTP {} : {}",
            status_code,
            error,
        )

        return HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail=f"Couldn't get Blizzard page (HTTP {status_code} error) : {error}",
        )

    def _blizzard_forbidden_error(self) -> HTTPException:
        self.cache_manager.set_global_rate_limit()
        if settings.discord_message_on_rate_limit:
            send_discord_webhook_message(
                "Blizzard Rate Limit reached ! Blocking further calls for "
                f"{settings.blizzard_rate_limit_retry_after} seconds..."
            )
        return self._too_many_requests_response(
            retry_after=settings.blizzard_rate_limit_retry_after
        )

    @staticmethod
    def _too_many_requests_response(retry_after: int) -> HTTPException:
        return HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=(
                "API has been rate limited by Blizzard, please wait for "
                f"{retry_after} seconds before retrying"
            ),
            headers={settings.retry_after_header: str(retry_after)},
        )
