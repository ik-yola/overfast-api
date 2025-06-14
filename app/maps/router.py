"""Maps endpoints router : maps list, etc."""

from typing import Annotated

from fastapi import APIRouter, Query, Request, Response

from app.enums import RouteTag
from app.gamemodes.enums import MapGamemode
from app.helpers import success_responses

from .controllers.get_overwatch_maps_controller import GetOverwatchMapsController
from .controllers.list_maps_controller import ListMapsController
from .models import Map, OverwatchMap

router = APIRouter()


@router.get(
    "",
    responses=success_responses,
    tags=[RouteTag.MAPS],
    summary="Get a list of maps",
    description=(
        "Get a list of Overwatch maps : Hanamura, King's Row, Dorado, etc."
        f"<br />**Cache TTL : {ListMapsController.get_human_readable_timeout()}.**"
    ),
    operation_id="list_maps",
)
async def list_maps(
    request: Request,
    response: Response,
    gamemode: Annotated[
        MapGamemode | None,
        Query(
            title="Gamemode filter",
            description="Filter maps available for a specific gamemode",
        ),
    ] = None,
) -> list[Map]:
    return await ListMapsController(request, response).process_request(
        gamemode=gamemode
    )


@router.get(
    "/overwatch/maps",
    responses=success_responses,
    tags=[RouteTag.MAPS],
    summary="Get Overwatch maps (simplified)",
    description=(
        "Get a simplified list of Overwatch maps with only name and screenshot. "
        "This endpoint is optimized for overlay applications that need basic map "
        "information with CDN image URLs for display purposes. "
        "<br />**Note:** This endpoint is protected by API Gateway authentication. "
    ),
    response_model=list[OverwatchMap],
    operation_id="get_overwatch_maps",
)
async def get_overwatch_maps(
    request: Request,
    response: Response,
) -> list[OverwatchMap]:
    """Get simplified maps data for Overwolf overlay application."""
    return await GetOverwatchMapsController(request, response).process_request()
