"""Fixtures MCP tool implementation."""

from typing import Any, Dict, List, Optional
from datetime import datetime
import uuid

from ..services import ApiSportsService, CacheService
from ..logger import get_logger

logger = get_logger(__name__)


class FixturesTool:
    """MCP tool for retrieving fixture (match) information."""
    
    def __init__(self, api_service: ApiSportsService, cache_service: CacheService):
        self.api_service = api_service
        self.cache_service = cache_service
    
    def _is_fixture_completed(self, status: str) -> bool:
        """Check if fixture status indicates a completed match."""
        completed_statuses = ["FT", "AET", "PEN", "PST", "CANC", "ABD", "AWD", "WO"]
        return status in completed_statuses
    
    async def get_fixtures(
        self,
        id: Optional[int] = None,
        ids: Optional[str] = None,
        live: Optional[str] = None,
        date: Optional[str] = None,
        league: Optional[int] = None,
        season: Optional[int] = None,
        team: Optional[int] = None,
        last: Optional[int] = None,
        next: Optional[int] = None,
        from_date: Optional[str] = None,
        to_date: Optional[str] = None,
        round: Optional[str] = None,
        status: Optional[str] = None,
        venue: Optional[int] = None,
        timezone: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Retrieve fixtures with comprehensive filtering options.
        
        Args:
            id: Fixture ID
            ids: Multiple fixture IDs (delimiter "-", max 20)
            live: "all" or league IDs
            date: Date in YYYY-MM-DD format
            league: League ID
            season: Season year (YYYY)
            team: Team ID
            last: Last N matches (max 2 digits)
            next: Next N matches (max 2 digits)
            from_date: Start date (YYYY-MM-DD)
            to_date: End date (YYYY-MM-DD)
            round: Round name
            status: Match status (NS, PST, FT, etc.)
            venue: Venue ID
            timezone: Timezone for dates
        
        Returns:
            Dictionary containing fixture information
        """
        request_id = str(uuid.uuid4())
        
        # Validate parameters
        if last and last > 99:
            return {
                "error": "Last parameter must be 2 digits or less",
                "request_id": request_id,
            }
        
        if next and next > 99:
            return {
                "error": "Next parameter must be 2 digits or less",
                "request_id": request_id,
            }
        
        if date:
            try:
                datetime.strptime(date, "%Y-%m-%d")
            except ValueError:
                return {
                    "error": "Date must be in YYYY-MM-DD format",
                    "request_id": request_id,
                }
        
        if from_date:
            try:
                datetime.strptime(from_date, "%Y-%m-%d")
            except ValueError:
                return {
                    "error": "From date must be in YYYY-MM-DD format",
                    "request_id": request_id,
                }
        
        if to_date:
            try:
                datetime.strptime(to_date, "%Y-%m-%d")
            except ValueError:
                return {
                    "error": "To date must be in YYYY-MM-DD format",
                    "request_id": request_id,
                }
        
        # Build parameters
        params = {}
        if id is not None:
            params["id"] = id
        if ids:
            params["ids"] = ids
        if live:
            params["live"] = live
        if date:
            params["date"] = date
        if league is not None:
            params["league"] = league
        if season is not None:
            params["season"] = season
        if team is not None:
            params["team"] = team
        if last is not None:
            params["last"] = last
        if next is not None:
            params["next"] = next
        if from_date:
            params["from"] = from_date
        if to_date:
            params["to"] = to_date
        if round:
            params["round"] = round
        if status:
            params["status"] = status
        if venue is not None:
            params["venue"] = venue
        if timezone:
            params["timezone"] = timezone
        
        logger.info(
            "Retrieving fixtures",
            extra={"params": params, "request_id": request_id}
        )
        
        try:
            # Don't cache live fixtures
            if not live:
                # Check cache first
                cached_result = await self.cache_service.get_fixtures(params)
                if cached_result:
                    logger.debug(
                        "Returning cached fixtures result",
                        extra={"request_id": request_id}
                    )
                    return cached_result
            
            # Make API request
            response = await self.api_service.get_fixtures(
                id=id,
                ids=ids,
                live=live,
                date=date,
                league=league,
                season=season,
                team=team,
                last=last,
                next=next,
                from_date=from_date,
                to_date=to_date,
                round=round,
                status=status,
                venue=venue,
                timezone=timezone,
            )
            
            # Process response
            fixtures_data = []
            for item in response.response:
                fixture_info = item.get("fixture", {})
                league_info = item.get("league", {})
                teams_info = item.get("teams", {})
                goals_info = item.get("goals", {})
                score_info = item.get("score", {})
                
                fixture_data = {
                    "id": fixture_info.get("id"),
                    "referee": fixture_info.get("referee"),
                    "timezone": fixture_info.get("timezone"),
                    "date": fixture_info.get("date"),
                    "timestamp": fixture_info.get("timestamp"),
                    "venue": {
                        "id": fixture_info.get("venue", {}).get("id"),
                        "name": fixture_info.get("venue", {}).get("name"),
                        "city": fixture_info.get("venue", {}).get("city"),
                    } if fixture_info.get("venue") else None,
                    "status": {
                        "long": fixture_info.get("status", {}).get("long"),
                        "short": fixture_info.get("status", {}).get("short"),
                        "elapsed": fixture_info.get("status", {}).get("elapsed"),
                    },
                    "league": {
                        "id": league_info.get("id"),
                        "name": league_info.get("name"),
                        "country": league_info.get("country"),
                        "logo": league_info.get("logo"),
                        "flag": league_info.get("flag"),
                        "season": league_info.get("season"),
                        "round": league_info.get("round"),
                    },
                    "teams": {
                        "home": {
                            "id": teams_info.get("home", {}).get("id"),
                            "name": teams_info.get("home", {}).get("name"),
                            "logo": teams_info.get("home", {}).get("logo"),
                            "winner": teams_info.get("home", {}).get("winner"),
                        },
                        "away": {
                            "id": teams_info.get("away", {}).get("id"),
                            "name": teams_info.get("away", {}).get("name"),
                            "logo": teams_info.get("away", {}).get("logo"),
                            "winner": teams_info.get("away", {}).get("winner"),
                        },
                    },
                    "goals": {
                        "home": goals_info.get("home"),
                        "away": goals_info.get("away"),
                    },
                    "score": {
                        "halftime": {
                            "home": score_info.get("halftime", {}).get("home"),
                            "away": score_info.get("halftime", {}).get("away"),
                        },
                        "fulltime": {
                            "home": score_info.get("fulltime", {}).get("home"),
                            "away": score_info.get("fulltime", {}).get("away"),
                        },
                        "extratime": {
                            "home": score_info.get("extratime", {}).get("home"),
                            "away": score_info.get("extratime", {}).get("away"),
                        } if score_info.get("extratime") else None,
                        "penalty": {
                            "home": score_info.get("penalty", {}).get("home"),
                            "away": score_info.get("penalty", {}).get("away"),
                        } if score_info.get("penalty") else None,
                    },
                }
                fixtures_data.append(fixture_data)
            
            result = {
                "fixtures": fixtures_data,
                "count": len(fixtures_data),
                "request_id": request_id,
            }
            
            # Cache result if not live
            if not live and fixtures_data:
                # Check if all fixtures are completed to determine cache type
                all_completed = all(
                    self._is_fixture_completed(f["status"]["short"])
                    for f in fixtures_data
                )
                await self.cache_service.set_fixtures(params, result, is_completed=all_completed)
            
            logger.success(
                f"Found {len(fixtures_data)} fixtures",
                extra={"count": len(fixtures_data), "request_id": request_id}
            )
            
            return result
            
        except Exception as e:
            logger.error(
                f"Error retrieving fixtures: {str(e)}",
                extra={"error": str(e), "request_id": request_id}
            )
            return {
                "error": f"Failed to retrieve fixtures: {str(e)}",
                "request_id": request_id,
            }
    
    def get_tool_definition(self) -> Dict[str, Any]:
        """Get MCP tool definition for fixtures retrieval."""
        return {
            "name": "fixtures_get",
            "description": "Retrieve football fixtures (matches) with comprehensive filtering options",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "id": {
                        "type": "integer",
                        "description": "Fixture ID"
                    },
                    "ids": {
                        "type": "string",
                        "description": "Multiple fixture IDs (delimiter '-', max 20)"
                    },
                    "live": {
                        "type": "string",
                        "description": "'all' or league IDs for live fixtures"
                    },
                    "date": {
                        "type": "string",
                        "description": "Date in YYYY-MM-DD format"
                    },
                    "league": {
                        "type": "integer",
                        "description": "League ID"
                    },
                    "season": {
                        "type": "integer",
                        "description": "Season year (YYYY)"
                    },
                    "team": {
                        "type": "integer",
                        "description": "Team ID"
                    },
                    "last": {
                        "type": "integer",
                        "description": "Last N matches (max 99)"
                    },
                    "next": {
                        "type": "integer",
                        "description": "Next N matches (max 99)"
                    },
                    "from": {
                        "type": "string",
                        "description": "Start date (YYYY-MM-DD)"
                    },
                    "to": {
                        "type": "string",
                        "description": "End date (YYYY-MM-DD)"
                    },
                    "round": {
                        "type": "string",
                        "description": "Round name"
                    },
                    "status": {
                        "type": "string",
                        "description": "Match status (NS, PST, FT, etc.)"
                    },
                    "venue": {
                        "type": "integer",
                        "description": "Venue ID"
                    },
                    "timezone": {
                        "type": "string",
                        "description": "Timezone for dates"
                    }
                }
            }
        }