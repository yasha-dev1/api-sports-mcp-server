"""Team Statistics MCP tool implementation."""

import uuid
from datetime import datetime
from typing import Any

from ..logger import get_logger
from ..services import ApiSportsService, CacheService

logger = get_logger(__name__)


class TeamStatisticsTool:
    """MCP tool for retrieving team statistics."""

    def __init__(self, api_service: ApiSportsService, cache_service: CacheService):
        self.api_service = api_service
        self.cache_service = cache_service

    async def get_team_statistics(
        self,
        league: int,
        season: int,
        team: int,
        date: str | None = None,
    ) -> dict[str, Any]:
        """
        Get team statistics for a specific league and season.
        
        Args:
            league: League ID (required)
            season: Season year YYYY (required)
            team: Team ID (required)
            date: Optional date for statistics snapshot (YYYY-MM-DD)
        
        Returns:
            Dictionary containing team statistics
        """
        request_id = str(uuid.uuid4())

        # Validate date format if provided
        if date:
            try:
                datetime.strptime(date, "%Y-%m-%d")
            except ValueError:
                return {
                    "error": "Date must be in YYYY-MM-DD format",
                    "request_id": request_id,
                }

        # Build parameters
        params = {
            "league": league,
            "season": season,
            "team": team,
        }
        if date:
            params["date"] = date

        logger.info(
            "Retrieving team statistics",
            extra={"params": params, "request_id": request_id}
        )

        try:
            # Check cache first
            cached_result = await self.cache_service.get_statistics(params)
            if cached_result:
                logger.debug(
                    "Returning cached statistics result",
                    extra={"request_id": request_id}
                )
                return cached_result

            # Make API request
            response = await self.api_service.get_team_statistics(
                league=league,
                season=season,
                team=team,
                date=date,
            )

            # Process response
            if not response.response:
                return {
                    "error": "No statistics found for the specified parameters",
                    "request_id": request_id,
                }

            stats_data = response.response[0]

            # Extract and format statistics
            formatted_stats = {
                "league": {
                    "id": stats_data.get("league", {}).get("id"),
                    "name": stats_data.get("league", {}).get("name"),
                    "country": stats_data.get("league", {}).get("country"),
                    "logo": stats_data.get("league", {}).get("logo"),
                    "flag": stats_data.get("league", {}).get("flag"),
                    "season": stats_data.get("league", {}).get("season"),
                },
                "team": {
                    "id": stats_data.get("team", {}).get("id"),
                    "name": stats_data.get("team", {}).get("name"),
                    "logo": stats_data.get("team", {}).get("logo"),
                },
                "form": stats_data.get("form"),
                "fixtures": {
                    "played": {
                        "home": stats_data.get("fixtures", {}).get("played", {}).get("home"),
                        "away": stats_data.get("fixtures", {}).get("played", {}).get("away"),
                        "total": stats_data.get("fixtures", {}).get("played", {}).get("total"),
                    },
                    "wins": {
                        "home": stats_data.get("fixtures", {}).get("wins", {}).get("home"),
                        "away": stats_data.get("fixtures", {}).get("wins", {}).get("away"),
                        "total": stats_data.get("fixtures", {}).get("wins", {}).get("total"),
                    },
                    "draws": {
                        "home": stats_data.get("fixtures", {}).get("draws", {}).get("home"),
                        "away": stats_data.get("fixtures", {}).get("draws", {}).get("away"),
                        "total": stats_data.get("fixtures", {}).get("draws", {}).get("total"),
                    },
                    "loses": {
                        "home": stats_data.get("fixtures", {}).get("loses", {}).get("home"),
                        "away": stats_data.get("fixtures", {}).get("loses", {}).get("away"),
                        "total": stats_data.get("fixtures", {}).get("loses", {}).get("total"),
                    },
                },
                "goals": {
                    "for": {
                        "total": {
                            "home": stats_data.get("goals", {}).get("for", {}).get("total", {}).get("home"),
                            "away": stats_data.get("goals", {}).get("for", {}).get("total", {}).get("away"),
                            "total": stats_data.get("goals", {}).get("for", {}).get("total", {}).get("total"),
                        },
                        "average": {
                            "home": stats_data.get("goals", {}).get("for", {}).get("average", {}).get("home"),
                            "away": stats_data.get("goals", {}).get("for", {}).get("average", {}).get("away"),
                            "total": stats_data.get("goals", {}).get("for", {}).get("average", {}).get("total"),
                        },
                        "minute": stats_data.get("goals", {}).get("for", {}).get("minute", {}),
                    },
                    "against": {
                        "total": {
                            "home": stats_data.get("goals", {}).get("against", {}).get("total", {}).get("home"),
                            "away": stats_data.get("goals", {}).get("against", {}).get("total", {}).get("away"),
                            "total": stats_data.get("goals", {}).get("against", {}).get("total", {}).get("total"),
                        },
                        "average": {
                            "home": stats_data.get("goals", {}).get("against", {}).get("average", {}).get("home"),
                            "away": stats_data.get("goals", {}).get("against", {}).get("average", {}).get("away"),
                            "total": stats_data.get("goals", {}).get("against", {}).get("average", {}).get("total"),
                        },
                        "minute": stats_data.get("goals", {}).get("against", {}).get("minute", {}),
                    },
                },
                "biggest": {
                    "streak": {
                        "wins": stats_data.get("biggest", {}).get("streak", {}).get("wins"),
                        "draws": stats_data.get("biggest", {}).get("streak", {}).get("draws"),
                        "loses": stats_data.get("biggest", {}).get("streak", {}).get("loses"),
                    },
                    "wins": {
                        "home": stats_data.get("biggest", {}).get("wins", {}).get("home"),
                        "away": stats_data.get("biggest", {}).get("wins", {}).get("away"),
                    },
                    "loses": {
                        "home": stats_data.get("biggest", {}).get("loses", {}).get("home"),
                        "away": stats_data.get("biggest", {}).get("loses", {}).get("away"),
                    },
                    "goals": {
                        "for": {
                            "home": stats_data.get("biggest", {}).get("goals", {}).get("for", {}).get("home"),
                            "away": stats_data.get("biggest", {}).get("goals", {}).get("for", {}).get("away"),
                        },
                        "against": {
                            "home": stats_data.get("biggest", {}).get("goals", {}).get("against", {}).get("home"),
                            "away": stats_data.get("biggest", {}).get("goals", {}).get("against", {}).get("away"),
                        },
                    },
                },
                "clean_sheet": {
                    "home": stats_data.get("clean_sheet", {}).get("home"),
                    "away": stats_data.get("clean_sheet", {}).get("away"),
                    "total": stats_data.get("clean_sheet", {}).get("total"),
                },
                "failed_to_score": {
                    "home": stats_data.get("failed_to_score", {}).get("home"),
                    "away": stats_data.get("failed_to_score", {}).get("away"),
                    "total": stats_data.get("failed_to_score", {}).get("total"),
                },
                "penalty": {
                    "scored": {
                        "total": stats_data.get("penalty", {}).get("scored", {}).get("total"),
                        "percentage": stats_data.get("penalty", {}).get("scored", {}).get("percentage"),
                    },
                    "missed": {
                        "total": stats_data.get("penalty", {}).get("missed", {}).get("total"),
                        "percentage": stats_data.get("penalty", {}).get("missed", {}).get("percentage"),
                    },
                    "total": stats_data.get("penalty", {}).get("total"),
                },
                "lineups": stats_data.get("lineups", []),
                "cards": {
                    "yellow": {
                        "0-15": stats_data.get("cards", {}).get("yellow", {}).get("0-15", {}),
                        "16-30": stats_data.get("cards", {}).get("yellow", {}).get("16-30", {}),
                        "31-45": stats_data.get("cards", {}).get("yellow", {}).get("31-45", {}),
                        "46-60": stats_data.get("cards", {}).get("yellow", {}).get("46-60", {}),
                        "61-75": stats_data.get("cards", {}).get("yellow", {}).get("61-75", {}),
                        "76-90": stats_data.get("cards", {}).get("yellow", {}).get("76-90", {}),
                        "91-105": stats_data.get("cards", {}).get("yellow", {}).get("91-105", {}),
                        "106-120": stats_data.get("cards", {}).get("yellow", {}).get("106-120", {}),
                    },
                    "red": {
                        "0-15": stats_data.get("cards", {}).get("red", {}).get("0-15", {}),
                        "16-30": stats_data.get("cards", {}).get("red", {}).get("16-30", {}),
                        "31-45": stats_data.get("cards", {}).get("red", {}).get("31-45", {}),
                        "46-60": stats_data.get("cards", {}).get("red", {}).get("46-60", {}),
                        "61-75": stats_data.get("cards", {}).get("red", {}).get("61-75", {}),
                        "76-90": stats_data.get("cards", {}).get("red", {}).get("76-90", {}),
                        "91-105": stats_data.get("cards", {}).get("red", {}).get("91-105", {}),
                        "106-120": stats_data.get("cards", {}).get("red", {}).get("106-120", {}),
                    },
                },
            }

            result = {
                "statistics": formatted_stats,
                "request_id": request_id,
            }

            # Cache result
            await self.cache_service.set_statistics(params, result)

            logger.success(
                "Retrieved team statistics successfully",
                extra={"request_id": request_id}
            )

            return result

        except Exception as e:
            logger.error(
                f"Error retrieving team statistics: {str(e)}",
                extra={"error": str(e), "request_id": request_id}
            )
            return {
                "error": f"Failed to retrieve team statistics: {str(e)}",
                "request_id": request_id,
            }

    def get_tool_definition(self) -> dict[str, Any]:
        """Get MCP tool definition for team statistics."""
        return {
            "name": "team_statistics",
            "description": "Get comprehensive statistics for a team in a specific league and season",
            "inputSchema": {
                "type": "object",
                "required": ["league", "season", "team"],
                "properties": {
                    "league": {
                        "type": "integer",
                        "description": "League ID (required)"
                    },
                    "season": {
                        "type": "integer",
                        "description": "Season year YYYY (required)"
                    },
                    "team": {
                        "type": "integer",
                        "description": "Team ID (required)"
                    },
                    "date": {
                        "type": "string",
                        "description": "Optional date for statistics snapshot (YYYY-MM-DD)"
                    }
                }
            }
        }
