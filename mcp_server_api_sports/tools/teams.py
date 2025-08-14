"""Teams MCP tool implementation."""

import uuid
from typing import Any

from ..logger import get_logger
from ..services import ApiSportsService, CacheService

logger = get_logger(__name__)


class TeamsTool:
    """MCP tool for searching and retrieving team information."""

    def __init__(self, api_service: ApiSportsService, cache_service: CacheService):
        self.api_service = api_service
        self.cache_service = cache_service

    async def search_teams(
        self,
        id: int | None = None,
        name: str | None = None,
        league: int | None = None,
        season: int | None = None,
        country: str | None = None,
        code: str | None = None,
        venue: int | None = None,
        search: str | None = None,
    ) -> dict[str, Any]:
        """
        Search for teams with various filters.
        
        Args:
            id: Team ID
            name: Team name
            league: League ID
            season: Season year (YYYY)
            country: Country name
            code: 3-letter team code
            venue: Venue ID
            search: Search string (min 3 chars)
        
        Returns:
            Dictionary containing team information
        """
        request_id = str(uuid.uuid4())

        # Validate search parameter
        if search and len(search) < 3:
            return {
                "error": "Search parameter must be at least 3 characters long",
                "request_id": request_id,
            }

        # Build parameters
        params = {}
        if id is not None:
            params["id"] = id
        if name:
            params["name"] = name
        if league is not None:
            params["league"] = league
        if season is not None:
            params["season"] = season
        if country:
            params["country"] = country
        if code:
            params["code"] = code
        if venue is not None:
            params["venue"] = venue
        if search:
            params["search"] = search

        logger.info(
            "Searching teams",
            extra={"params": params, "request_id": request_id}
        )

        try:
            # Check cache first
            cached_result = await self.cache_service.get_teams(params)
            if cached_result:
                logger.debug(
                    "Returning cached teams result",
                    extra={"request_id": request_id}
                )
                return cached_result

            # Make API request
            response = await self.api_service.get_teams(
                id=id,
                name=name,
                league=league,
                season=season,
                country=country,
                code=code,
                venue=venue,
                search=search,
            )

            # Process response
            teams_data = []
            for item in response.response:
                team_info = item.get("team", {})
                venue_info = item.get("venue", {})

                team_data = {
                    "id": team_info.get("id"),
                    "name": team_info.get("name"),
                    "code": team_info.get("code"),
                    "country": team_info.get("country"),
                    "founded": team_info.get("founded"),
                    "national": team_info.get("national", False),
                    "logo": team_info.get("logo"),
                    "venue": {
                        "id": venue_info.get("id"),
                        "name": venue_info.get("name"),
                        "address": venue_info.get("address"),
                        "city": venue_info.get("city"),
                        "capacity": venue_info.get("capacity"),
                        "surface": venue_info.get("surface"),
                        "image": venue_info.get("image"),
                    } if venue_info else None,
                }
                teams_data.append(team_data)

            result = {
                "teams": teams_data,
                "count": len(teams_data),
                "request_id": request_id,
            }

            # Cache result
            await self.cache_service.set_teams(params, result)

            logger.success(
                f"Found {len(teams_data)} teams",
                extra={"count": len(teams_data), "request_id": request_id}
            )

            return result

        except Exception as e:
            logger.error(
                f"Error searching teams: {str(e)}",
                extra={"error": str(e), "request_id": request_id}
            )
            return {
                "error": f"Failed to search teams: {str(e)}",
                "request_id": request_id,
            }

    def get_tool_definition(self) -> dict[str, Any]:
        """Get MCP tool definition for teams search."""
        return {
            "name": "teams_search",
            "description": "Search for football teams and retrieve their information",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "id": {
                        "type": "integer",
                        "description": "Team ID"
                    },
                    "name": {
                        "type": "string",
                        "description": "Team name"
                    },
                    "league": {
                        "type": "integer",
                        "description": "League ID"
                    },
                    "season": {
                        "type": "integer",
                        "description": "Season year (YYYY)"
                    },
                    "country": {
                        "type": "string",
                        "description": "Country name"
                    },
                    "code": {
                        "type": "string",
                        "description": "3-letter team code"
                    },
                    "venue": {
                        "type": "integer",
                        "description": "Venue ID"
                    },
                    "search": {
                        "type": "string",
                        "description": "Search string (minimum 3 characters)"
                    }
                }
            }
        }
