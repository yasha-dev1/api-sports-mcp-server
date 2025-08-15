"""API-Sports service for making API calls."""

from __future__ import annotations

import asyncio
import time
import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

import httpx
from pydantic import ValidationError

from ..config import get_settings
from ..logger import get_logger, log_performance
from ..models import ApiResponse

if TYPE_CHECKING:
    from .cache_service import CacheService

logger = get_logger(__name__)


class RateLimiter:
    """Rate limiter for API calls."""

    def __init__(self, calls_per_minute: int, calls_per_day: int, burst_size: int):
        self.calls_per_minute = calls_per_minute
        self.calls_per_day = calls_per_day
        self.burst_size = burst_size

        self.minute_calls: list[float] = []
        self.day_calls: list[float] = []
        self.lock = asyncio.Lock()

    async def acquire(self) -> None:
        """Acquire permission to make an API call."""
        async with self.lock:
            now = time.time()

            # Clean up old calls
            minute_ago = now - 60
            day_ago = now - 86400

            self.minute_calls = [t for t in self.minute_calls if t > minute_ago]
            self.day_calls = [t for t in self.day_calls if t > day_ago]

            # Check limits
            if len(self.minute_calls) >= self.calls_per_minute:
                sleep_time = 60 - (now - self.minute_calls[0])
                logger.warning(f"Rate limit reached, sleeping for {sleep_time:.2f}s")
                await asyncio.sleep(sleep_time)
                return await self.acquire()

            if len(self.day_calls) >= self.calls_per_day:
                sleep_time = 86400 - (now - self.day_calls[0])
                logger.error(f"Daily limit reached, sleeping for {sleep_time:.2f}s")
                await asyncio.sleep(sleep_time)
                return await self.acquire()

            # Record call
            self.minute_calls.append(now)
            self.day_calls.append(now)

    def get_remaining(self) -> dict[str, int]:
        """Get remaining API calls."""
        now = time.time()
        minute_ago = now - 60
        day_ago = now - 86400

        minute_calls = [t for t in self.minute_calls if t > minute_ago]
        day_calls = [t for t in self.day_calls if t > day_ago]

        return {
            "minute": max(0, self.calls_per_minute - len(minute_calls)),
            "day": max(0, self.calls_per_day - len(day_calls)),
        }


class ApiSportsService:
    """Service for interacting with API-Sports API."""

    def __init__(self, cache_service: CacheService | None = None) -> None:
        self.settings = get_settings()
        self.base_url = self.settings.api_sports_base_url
        self.api_key = self.settings.api_sports_api_key
        self.cache_service = cache_service

        self.rate_limiter = RateLimiter(
            calls_per_minute=self.settings.rate_limit_calls_per_minute,
            calls_per_day=self.settings.rate_limit_calls_per_day,
            burst_size=self.settings.rate_limit_burst_size,
        )

        self.client: httpx.AsyncClient | None = None
        self._client_lock = asyncio.Lock()

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self.client is None:
            async with self._client_lock:
                if self.client is None:
                    self.client = httpx.AsyncClient(
                        base_url=self.base_url,
                        headers={
                            "X-RapidAPI-Key": self.api_key,
                            "X-RapidAPI-Host": "v3.football.api-sports.io",
                        },
                        timeout=httpx.Timeout(30.0),
                    )
        return self.client

    async def close(self) -> None:
        """Close HTTP client."""
        if self.client:
            await self.client.aclose()
            self.client = None

    @log_performance
    async def make_request(
        self,
        endpoint: str,
        params: dict[str, Any] | None = None,
        request_id: str | None = None,
    ) -> ApiResponse:
        """Make API request with rate limiting and retries."""
        await self.rate_limiter.acquire()

        client = await self._get_client()

        max_retries = self.settings.rate_limit_max_retries
        backoff_factor = self.settings.rate_limit_backoff_factor

        for attempt in range(max_retries):
            try:
                logger.debug(
                    f"Making request to {endpoint}",
                    extra={
                        "endpoint": endpoint,
                        "params": params,
                        "attempt": attempt + 1,
                        "request_id": request_id,
                    }
                )

                response = await client.get(endpoint, params=params)

                # Log rate limit headers if present
                if "X-RateLimit-Remaining" in response.headers:
                    logger.debug(
                        "Rate limit status",
                        extra={
                            "remaining": response.headers.get("X-RateLimit-Remaining"),
                            "limit": response.headers.get("X-RateLimit-Limit"),
                            "request_id": request_id,
                        }
                    )

                if response.status_code == 429:
                    # Rate limited
                    retry_after = int(response.headers.get("Retry-After", 60))
                    logger.warning(
                        f"Rate limited, retrying after {retry_after}s",
                        extra={"retry_after": retry_after, "request_id": request_id}
                    )
                    await asyncio.sleep(retry_after)
                    continue

                if response.status_code >= 500 and attempt < max_retries - 1:
                    # Server error, retry with backoff
                    sleep_time = backoff_factor ** attempt
                    logger.warning(
                        f"Server error {response.status_code}, retrying in {sleep_time}s",
                        extra={
                            "status_code": response.status_code,
                            "sleep_time": sleep_time,
                            "request_id": request_id,
                        }
                    )
                    await asyncio.sleep(sleep_time)
                    continue

                # Only allow 200 and 429 status codes
                if response.status_code not in [200, 429]:
                    error_text = f"API returned status {response.status_code}"
                    try:
                        error_details = response.json()
                        if isinstance(error_details, dict) and error_details.get("message"):
                            error_text += f": {error_details['message']}"
                        else:
                            error_text += f": {response.text}"
                    except Exception:
                        error_text += f": {response.text}"
                    
                    logger.error(
                        f"HTTP error {response.status_code}",
                        extra={
                            "status_code": response.status_code,
                            "endpoint": endpoint,
                            "response_text": response.text[:500],
                            "request_id": request_id,
                        }
                    )
                    raise httpx.HTTPStatusError(error_text, request=response.request, response=response)

                # Parse response
                data = response.json()
                api_response = ApiResponse(**data)

                # Check for API errors in the response body
                if api_response.errors:
                    # Format error message from API errors
                    if isinstance(api_response.errors, list):
                        error_msg = "; ".join(str(err) for err in api_response.errors if err)
                    elif isinstance(api_response.errors, dict):
                        error_items = []
                        for key, value in api_response.errors.items():
                            if value:
                                error_items.append(f"{key}: {value}")
                        error_msg = "; ".join(error_items)
                    else:
                        error_msg = str(api_response.errors)
                    
                    if error_msg:  # Only raise if there are actual errors
                        logger.error(
                            "API returned errors in response",
                            extra={
                                "errors": api_response.errors,
                                "endpoint": endpoint,
                                "request_id": request_id,
                            }
                        )
                        raise ValueError(f"API Error: {error_msg}")

                logger.success(
                    f"Request successful: {api_response.results} results",
                    extra={
                        "endpoint": endpoint,
                        "results": api_response.results,
                        "request_id": request_id,
                    }
                )

                return api_response

            except httpx.HTTPStatusError as e:
                logger.error(
                    f"HTTP error on attempt {attempt + 1}: {e}",
                    extra={
                        "status_code": e.response.status_code,
                        "endpoint": endpoint,
                        "request_id": request_id,
                    }
                )
                if attempt == max_retries - 1:
                    raise

            except httpx.RequestError as e:
                logger.error(
                    f"Request error on attempt {attempt + 1}: {e}",
                    extra={"endpoint": endpoint, "request_id": request_id}
                )
                if attempt == max_retries - 1:
                    raise

            except ValidationError as e:
                logger.error(
                    f"Response validation error: {e}",
                    extra={"endpoint": endpoint, "request_id": request_id}
                )
                raise

            except Exception as e:
                logger.error(
                    f"Unexpected error on attempt {attempt + 1}: {e}",
                    extra={"endpoint": endpoint, "request_id": request_id}
                )
                if attempt == max_retries - 1:
                    raise

            # Exponential backoff between retries
            if attempt < max_retries - 1:
                sleep_time = backoff_factor ** attempt
                await asyncio.sleep(sleep_time)

        raise Exception(f"Failed to make request after {max_retries} attempts")

    # Convenience methods for specific endpoints

    async def get_teams(
        self,
        id: int | None = None,
        name: str | None = None,
        league: int | None = None,
        season: int | None = None,
        country: str | None = None,
        code: str | None = None,
        venue: int | None = None,
        search: str | None = None,
    ) -> ApiResponse:
        """Get teams information."""
        params: dict[str, Any] = {}
        if id is not None:
            params["id"] = str(id)
        if name:
            params["name"] = name
        if league is not None:
            params["league"] = str(league)
        if season is not None:
            params["season"] = str(season)
        if country:
            params["country"] = country
        if code:
            params["code"] = code
        if venue is not None:
            params["venue"] = str(venue)
        if search:
            params["search"] = search

        return await self.make_request("/teams", params)  # type: ignore[no-any-return]

    async def get_fixtures(
        self,
        id: int | None = None,
        ids: str | None = None,
        live: str | None = None,
        date: str | None = None,
        league: int | None = None,
        season: int | None = None,
        team: int | None = None,
        last: int | None = None,
        next: int | None = None,
        from_date: str | None = None,
        to_date: str | None = None,
        round: str | None = None,
        status: str | None = None,
        venue: int | None = None,
        timezone: str | None = None,
    ) -> ApiResponse:
        """Get fixtures information."""
        params: dict[str, Any] = {}
        if id is not None:
            params["id"] = str(id)
        if ids:
            params["ids"] = ids
        if live:
            params["live"] = live
        if date:
            params["date"] = date
        if league is not None:
            params["league"] = str(league)
        if season is not None:
            params["season"] = str(season)
        if team is not None:
            params["team"] = str(team)
        if last is not None:
            params["last"] = str(last)
        if next is not None:
            params["next"] = str(next)
        if from_date:
            params["from"] = from_date
        if to_date:
            params["to"] = to_date
        if round:
            params["round"] = round
        if status:
            params["status"] = status
        if venue is not None:
            params["venue"] = str(venue)
        if timezone:
            params["timezone"] = timezone

        return await self.make_request("/fixtures", params)  # type: ignore[no-any-return]

    async def get_team_statistics(
        self,
        league: int,
        season: int,
        team: int,
        date: str | None = None,
    ) -> ApiResponse:
        """Get team statistics."""
        params: dict[str, Any] = {
            "league": str(league),
            "season": str(season),
            "team": str(team),
        }
        if date:
            params["date"] = date

        return await self.make_request("/teams/statistics", params)  # type: ignore[no-any-return]

    async def get_standings(
        self,
        league: int,
        season: int,
        team: int | None = None,
    ) -> ApiResponse:
        """Get league standings."""
        params: dict[str, Any] = {
            "league": str(league),
            "season": str(season),
        }
        if team is not None:
            params["team"] = str(team)

        return await self.make_request("/standings", params)  # type: ignore[no-any-return]

    async def get_fixtures_head2head(
        self,
        h2h: str,
        date: str | None = None,
        league: int | None = None,
        season: int | None = None,
        last: int | None = None,
        next: int | None = None,
        from_date: str | None = None,
        to_date: str | None = None,
        status: str | None = None,
        venue: int | None = None,
        timezone: str | None = None,
    ) -> ApiResponse:
        """Get head to head fixtures."""
        params: dict[str, Any] = {"h2h": h2h}

        if date:
            params["date"] = date
        if league is not None:
            params["league"] = str(league)
        if season is not None:
            params["season"] = str(season)
        if last is not None:
            params["last"] = str(last)
        if next is not None:
            params["next"] = str(next)
        if from_date:
            params["from"] = from_date
        if to_date:
            params["to"] = to_date
        if status:
            params["status"] = status
        if venue is not None:
            params["venue"] = str(venue)
        if timezone:
            params["timezone"] = timezone

        return await self.make_request("/fixtures/headtohead", params)  # type: ignore[no-any-return]

    async def get_fixture_statistics(self, fixture: int) -> ApiResponse:
        """Get fixture statistics."""
        return await self.make_request("/fixtures/statistics", {"fixture": str(fixture)})  # type: ignore[no-any-return]

    async def get_fixture_events(self, fixture: int) -> ApiResponse:
        """Get fixture events."""
        return await self.make_request("/fixtures/events", {"fixture": str(fixture)})  # type: ignore[no-any-return]

    async def get_fixture_lineups(self, fixture: int) -> ApiResponse:
        """Get fixture lineups."""
        return await self.make_request("/fixtures/lineups", {"fixture": str(fixture)})  # type: ignore[no-any-return]

    async def get_predictions(self, fixture: int) -> ApiResponse:
        """Get fixture predictions."""
        return await self.make_request("/predictions", {"fixture": str(fixture)})  # type: ignore[no-any-return]

    async def get_leagues(
        self,
        id: int | None = None,
        name: str | None = None,
        country: str | None = None,
        code: str | None = None,
        season: int | None = None,
        team: int | None = None,
        type: str | None = None,
        current: str | None = None,
        search: str | None = None,
        last: int | None = None,
    ) -> ApiResponse:
        """Get leagues information."""
        params: dict[str, Any] = {}
        if id is not None:
            params["id"] = str(id)
        if name:
            params["name"] = name
        if country:
            params["country"] = country
        if code:
            params["code"] = code
        if season is not None:
            params["season"] = str(season)
        if team is not None:
            params["team"] = str(team)
        if type:
            params["type"] = type
        if current:
            params["current"] = current
        if search:
            params["search"] = search
        if last is not None:
            params["last"] = str(last)

        return await self.make_request("/leagues", params)  # type: ignore[no-any-return]

    async def get_seasons(self) -> ApiResponse:
        """Get available seasons."""
        return await self.make_request("/leagues/seasons")  # type: ignore[no-any-return]

    # Business logic methods with validation and formatting

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
        Search for teams with various filters and return formatted data.
        
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
            Dictionary containing formatted team information
        """
        request_id = str(uuid.uuid4())

        # Validate search parameter
        if search and len(search) < 3:
            return {
                "error": "Search parameter must be at least 3 characters long",
                "request_id": request_id,
            }

        # Build parameters for cache key
        params: dict[str, Any] = {}
        if id is not None:
            params["id"] = str(id)
        if name:
            params["name"] = name
        if league is not None:
            params["league"] = str(league)
        if season is not None:
            params["season"] = str(season)
        if country:
            params["country"] = country
        if code:
            params["code"] = code
        if venue is not None:
            params["venue"] = str(venue)
        if search:
            params["search"] = search

        logger.info(
            "Searching teams",
            extra={"params": params, "request_id": request_id}
        )

        try:
            # Check cache first if cache service is available
            if self.cache_service:
                cached_result = await self.cache_service.get_teams(params)
                if cached_result:
                    logger.debug(
                        "Returning cached teams result",
                        extra={"request_id": request_id}
                    )
                    return cached_result  # type: ignore[no-any-return]

            # Make API request
            response = await self.get_teams(
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

            # Cache result if cache service is available
            if self.cache_service:
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

    async def search_fixtures(
        self,
        id: int | None = None,
        ids: str | None = None,
        live: str | None = None,
        date: str | None = None,
        league: int | None = None,
        season: int | None = None,
        team: int | None = None,
        last: int | None = None,
        next: int | None = None,
        from_date: str | None = None,
        to_date: str | None = None,
        round: str | None = None,
        status: str | None = None,
        venue: int | None = None,
        timezone: str | None = None,
    ) -> dict[str, Any]:
        """
        Retrieve fixtures with comprehensive filtering options and return formatted data.
        
        Returns:
            Dictionary containing formatted fixture information
        """
        request_id = str(uuid.uuid4())

        # Validate parameters
        if league is not None and season is None:
            return {
                "error": "When using 'league' parameter, 'season' is required",
                "request_id": request_id,
            }
            
        if team is not None and season is None:
            return {
                "error": "When using 'team' parameter, 'season' is required",
                "request_id": request_id,
            }
            
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
        params: dict[str, Any] = {}
        if id is not None:
            params["id"] = str(id)
        if ids:
            params["ids"] = ids
        if live:
            params["live"] = live
        if date:
            params["date"] = date
        if league is not None:
            params["league"] = str(league)
        if season is not None:
            params["season"] = str(season)
        if team is not None:
            params["team"] = str(team)
            # If only team is provided without other filters, get next 10 fixtures
            # This ensures we get meaningful results
            if (season is None and not date and not from_date and
                not last and not next and not id and not ids and not live):
                params["next"] = "10"
                logger.info(
                    "Auto-adding next=10 for team-only query to get upcoming fixtures",
                    extra={"team": team, "request_id": request_id}
                )
        if last is not None:
            params["last"] = str(last)
        if next is not None:
            params["next"] = str(next)
        if from_date:
            params["from"] = from_date
        if to_date:
            params["to"] = to_date
        if round:
            params["round"] = round
        if status:
            params["status"] = status
        if venue is not None:
            params["venue"] = str(venue)
        if timezone:
            params["timezone"] = timezone

        logger.info(
            "Retrieving fixtures",
            extra={"params": params, "request_id": request_id}
        )

        try:
            # Don't cache live fixtures
            if not live and self.cache_service:
                cached_result = await self.cache_service.get_fixtures(params)
                if cached_result:
                    logger.debug(
                        "Returning cached fixtures result",
                        extra={"request_id": request_id}
                    )
                    return cached_result  # type: ignore[no-any-return]

            # Make API request
            response = await self.get_fixtures(
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

            # Cache result if not live and cache service is available
            if not live and fixtures_data and self.cache_service:
                # Check if all fixtures are completed to determine cache type
                completed_statuses = ["FT", "AET", "PEN", "PST", "CANC", "ABD", "AWD", "WO"]
                all_completed = all(
                    f["status"]["short"] in completed_statuses
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

    async def get_team_statistics_formatted(
        self,
        league: int,
        season: int,
        team: int,
        date: str | None = None,
    ) -> dict[str, Any]:
        """
        Get team statistics for a specific league and season with formatted output.
        
        Returns:
            Dictionary containing formatted team statistics
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
        params: dict[str, Any] = {
            "league": str(league),
            "season": str(season),
            "team": str(team),
        }
        if date:
            params["date"] = date

        logger.info(
            "Retrieving team statistics",
            extra={"params": params, "request_id": request_id}
        )

        try:
            # Check cache first if cache service is available
            if self.cache_service:
                cached_result = await self.cache_service.get_statistics(params)
                if cached_result:
                    logger.debug(
                        "Returning cached statistics result",
                        extra={"request_id": request_id}
                    )
                    return cached_result  # type: ignore[no-any-return]

            # Make API request
            response = await self.get_team_statistics(
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

            # Extract and format statistics (simplified version)
            formatted_stats = {
                "league": stats_data.get("league", {}),
                "team": stats_data.get("team", {}),
                "form": stats_data.get("form"),
                "fixtures": stats_data.get("fixtures", {}),
                "goals": stats_data.get("goals", {}),
                "biggest": stats_data.get("biggest", {}),
                "clean_sheet": stats_data.get("clean_sheet", {}),
                "failed_to_score": stats_data.get("failed_to_score", {}),
                "penalty": stats_data.get("penalty", {}),
                "lineups": stats_data.get("lineups", []),
                "cards": stats_data.get("cards", {}),
            }

            result = {
                "statistics": formatted_stats,
                "request_id": request_id,
            }

            # Cache result if cache service is available
            if self.cache_service:
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

    async def get_standings_formatted(
        self,
        league: int,
        season: int,
        team: int | None = None,
    ) -> dict[str, Any]:
        """
        Get league standings with formatted output.
        
        Returns:
            Dictionary containing formatted standings information
        """
        request_id = str(uuid.uuid4())

        logger.info(
            "Retrieving standings",
            extra={"league": league, "season": season, "team": team, "request_id": request_id}
        )

        try:
            # Check cache first if cache service is available
            cache_key = f"standings:{league}:{season}:{team or 'all'}"
            if self.cache_service:
                cached_result = await self.cache_service.get(cache_key)
                if cached_result:
                    logger.debug(
                        "Returning cached standings result",
                        extra={"request_id": request_id}
                    )
                    return cached_result  # type: ignore[no-any-return]

            # Make API request
            response = await self.get_standings(
                league=league,
                season=season,
                team=team
            )

            # Process response
            if not response.response or not response.response[0]:
                return {
                    "error": "No standings found for the specified parameters",
                    "request_id": request_id,
                }

            standings_data = []
            league_info = response.response[0].get("league", {})

            # Extract standings from the response
            standings_list = league_info.get("standings", [])
            if standings_list and isinstance(standings_list[0], list):
                # API returns nested array for standings
                standings_list = standings_list[0]

            for standing in standings_list:
                formatted_standing = {
                    "rank": standing.get("rank"),
                    "team": standing.get("team", {}),
                    "points": standing.get("points"),
                    "goalsDiff": standing.get("goalsDiff"),
                    "group": standing.get("group"),
                    "form": standing.get("form"),
                    "status": standing.get("status"),
                    "description": standing.get("description"),
                    "all": standing.get("all", {}),
                    "home": standing.get("home", {}),
                    "away": standing.get("away", {}),
                    "update": standing.get("update"),
                }
                standings_data.append(formatted_standing)

            result = {
                "league": {
                    "id": league_info.get("id"),
                    "name": league_info.get("name"),
                    "country": league_info.get("country"),
                    "logo": league_info.get("logo"),
                    "flag": league_info.get("flag"),
                    "season": league_info.get("season"),
                },
                "standings": standings_data,
                "count": len(standings_data),
                "request_id": request_id,
            }

            # Cache result if cache service is available (30 minutes TTL)
            if self.cache_service:
                await self.cache_service.set(cache_key, result, "standings")

            logger.success(
                f"Retrieved standings for {len(standings_data)} teams",
                extra={"count": len(standings_data), "request_id": request_id}
            )

            return result

        except Exception as e:
            logger.error(
                f"Error retrieving standings: {str(e)}",
                extra={"error": str(e), "request_id": request_id}
            )
            return {
                "error": f"Failed to retrieve standings: {str(e)}",
                "request_id": request_id,
            }

    async def get_head2head_formatted(
        self,
        h2h: str,
        date: str | None = None,
        league: int | None = None,
        season: int | None = None,
        last: int | None = None,
        next: int | None = None,
        from_date: str | None = None,
        to_date: str | None = None,
        status: str | None = None,
        venue: int | None = None,
        timezone: str | None = None,
    ) -> dict[str, Any]:
        """
        Get head-to-head fixtures between two teams with formatted output.
        
        Args:
            h2h: Teams IDs separated by a dash (e.g., "33-34")
            
        Returns:
            Dictionary containing formatted head-to-head fixtures
        """
        request_id = str(uuid.uuid4())

        # Validate h2h format
        if not h2h or '-' not in h2h:
            return {
                "error": "h2h parameter must be in format 'team1-team2' (e.g., '33-34')",
                "request_id": request_id,
            }

        # Validate dates if provided
        for date_param, date_value in [("date", date), ("from_date", from_date), ("to_date", to_date)]:
            if date_value:
                try:
                    datetime.strptime(date_value, "%Y-%m-%d")
                except ValueError:
                    return {
                        "error": f"{date_param} must be in YYYY-MM-DD format",
                        "request_id": request_id,
                    }

        logger.info(
            "Retrieving head-to-head fixtures",
            extra={"h2h": h2h, "request_id": request_id}
        )

        try:
            # Make API request
            response = await self.get_fixtures_head2head(
                h2h=h2h,
                date=date,
                league=league,
                season=season,
                last=last,
                next=next,
                from_date=from_date,
                to_date=to_date,
                status=status,
                venue=venue,
                timezone=timezone,
            )

            # Process response (similar to fixtures)
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
                    "venue": fixture_info.get("venue"),
                    "status": fixture_info.get("status", {}),
                    "league": league_info,
                    "teams": teams_info,
                    "goals": goals_info,
                    "score": score_info,
                }
                fixtures_data.append(fixture_data)

            # Calculate statistics
            team_ids = h2h.split('-')
            team1_wins = 0
            team2_wins = 0
            draws = 0

            for fixture in fixtures_data:
                if fixture.get("status", {}).get("short") in ["FT", "AET", "PEN"]:
                    home_id = str(fixture.get("teams", {}).get("home", {}).get("id"))
                    away_id = str(fixture.get("teams", {}).get("away", {}).get("id"))
                    home_goals = fixture.get("goals", {}).get("home")
                    away_goals = fixture.get("goals", {}).get("away")

                    if home_goals is not None and away_goals is not None:
                        if home_goals > away_goals:
                            if home_id == team_ids[0]:
                                team1_wins += 1
                            else:
                                team2_wins += 1
                        elif away_goals > home_goals:
                            if away_id == team_ids[0]:
                                team1_wins += 1
                            else:
                                team2_wins += 1
                        else:
                            draws += 1

            result = {
                "fixtures": fixtures_data,
                "count": len(fixtures_data),
                "statistics": {
                    "team1_wins": team1_wins,
                    "team2_wins": team2_wins,
                    "draws": draws,
                    "total_games": team1_wins + team2_wins + draws,
                },
                "request_id": request_id,
            }

            logger.success(
                f"Found {len(fixtures_data)} head-to-head fixtures",
                extra={"count": len(fixtures_data), "request_id": request_id}
            )

            return result

        except Exception as e:
            logger.error(
                f"Error retrieving head-to-head fixtures: {str(e)}",
                extra={"error": str(e), "request_id": request_id}
            )
            return {
                "error": f"Failed to retrieve head-to-head fixtures: {str(e)}",
                "request_id": request_id,
            }

    async def get_fixture_statistics_formatted(self, fixture: int) -> dict[str, Any]:
        """
        Get detailed statistics for a specific fixture with formatted output.
        
        Returns:
            Dictionary containing formatted fixture statistics
        """
        request_id = str(uuid.uuid4())

        logger.info(
            "Retrieving fixture statistics",
            extra={"fixture": fixture, "request_id": request_id}
        )

        try:
            # Check cache first if cache service is available
            cache_key = f"fixture_stats:{fixture}"
            if self.cache_service:
                cached_result = await self.cache_service.get(cache_key)
                if cached_result:
                    logger.debug(
                        "Returning cached fixture statistics",
                        extra={"request_id": request_id}
                    )
                    return cached_result  # type: ignore[no-any-return]

            # Make API request
            response = await self.get_fixture_statistics(fixture)

            # Process response
            if not response.response:
                return {
                    "error": "No statistics found for this fixture",
                    "request_id": request_id,
                }

            stats_data = []
            for team_stats in response.response:
                team_info = team_stats.get("team", {})
                statistics = team_stats.get("statistics", [])

                # Convert statistics array to dictionary for easier access
                stats_dict = {}
                for stat in statistics:
                    stat_type = stat.get("type")
                    stat_value = stat.get("value")
                    stats_dict[stat_type] = stat_value

                stats_data.append({
                    "team": team_info,
                    "statistics": stats_dict,
                })

            result = {
                "fixture_id": fixture,
                "teams": stats_data,
                "request_id": request_id,
            }

            # Cache result if cache service is available (completed fixtures cache forever)
            if self.cache_service:
                await self.cache_service.set(cache_key, result, "fixtures_completed")

            logger.success(
                "Retrieved fixture statistics successfully",
                extra={"fixture": fixture, "request_id": request_id}
            )

            return result

        except Exception as e:
            logger.error(
                f"Error retrieving fixture statistics: {str(e)}",
                extra={"error": str(e), "request_id": request_id}
            )
            return {
                "error": f"Failed to retrieve fixture statistics: {str(e)}",
                "request_id": request_id,
            }

    async def get_fixture_events_formatted(self, fixture: int) -> dict[str, Any]:
        """
        Get events timeline for a specific fixture with formatted output.
        
        Returns:
            Dictionary containing formatted fixture events
        """
        request_id = str(uuid.uuid4())

        logger.info(
            "Retrieving fixture events",
            extra={"fixture": fixture, "request_id": request_id}
        )

        try:
            # Check cache first if cache service is available
            cache_key = f"fixture_events:{fixture}"
            if self.cache_service:
                cached_result = await self.cache_service.get(cache_key)
                if cached_result:
                    logger.debug(
                        "Returning cached fixture events",
                        extra={"request_id": request_id}
                    )
                    return cached_result  # type: ignore[no-any-return]

            # Make API request
            response = await self.get_fixture_events(fixture)

            # Process response
            events_data = []
            for event in response.response:
                formatted_event = {
                    "time": event.get("time", {}),
                    "team": event.get("team", {}),
                    "player": event.get("player", {}),
                    "assist": event.get("assist", {}),
                    "type": event.get("type"),
                    "detail": event.get("detail"),
                    "comments": event.get("comments"),
                }
                events_data.append(formatted_event)

            # Sort events by time
            events_data.sort(key=lambda x: (x["time"].get("elapsed", 0), x["time"].get("extra", 0) or 0))

            result = {
                "fixture_id": fixture,
                "events": events_data,
                "count": len(events_data),
                "request_id": request_id,
            }

            # Cache result if cache service is available (completed fixtures cache forever)
            if self.cache_service:
                await self.cache_service.set(cache_key, result, "fixtures_completed")

            logger.success(
                f"Retrieved {len(events_data)} events for fixture",
                extra={"count": len(events_data), "request_id": request_id}
            )

            return result

        except Exception as e:
            logger.error(
                f"Error retrieving fixture events: {str(e)}",
                extra={"error": str(e), "request_id": request_id}
            )
            return {
                "error": f"Failed to retrieve fixture events: {str(e)}",
                "request_id": request_id,
            }

    async def get_fixture_lineups_formatted(self, fixture: int) -> dict[str, Any]:
        """
        Get lineups for a specific fixture with formatted output.
        
        Returns:
            Dictionary containing formatted fixture lineups
        """
        request_id = str(uuid.uuid4())

        logger.info(
            "Retrieving fixture lineups",
            extra={"fixture": fixture, "request_id": request_id}
        )

        try:
            # Check cache first if cache service is available
            cache_key = f"fixture_lineups:{fixture}"
            if self.cache_service:
                cached_result = await self.cache_service.get(cache_key)
                if cached_result:
                    logger.debug(
                        "Returning cached fixture lineups",
                        extra={"request_id": request_id}
                    )
                    return cached_result  # type: ignore[no-any-return]

            # Make API request
            response = await self.get_fixture_lineups(fixture)

            # Process response
            if not response.response:
                return {
                    "error": "No lineups found for this fixture",
                    "request_id": request_id,
                }

            lineups_data = []
            for team_lineup in response.response:
                team_info = team_lineup.get("team", {})
                formation = team_lineup.get("formation")
                starting_xi = team_lineup.get("startXI", [])
                substitutes = team_lineup.get("substitutes", [])
                coach = team_lineup.get("coach", {})

                lineup_data = {
                    "team": team_info,
                    "formation": formation,
                    "coach": coach,
                    "startingXI": [
                        {
                            "player": player.get("player", {}),
                        }
                        for player in starting_xi
                    ],
                    "substitutes": [
                        {
                            "player": player.get("player", {}),
                        }
                        for player in substitutes
                    ],
                }
                lineups_data.append(lineup_data)

            result = {
                "fixture_id": fixture,
                "lineups": lineups_data,
                "request_id": request_id,
            }

            # Cache result if cache service is available
            if self.cache_service:
                await self.cache_service.set(cache_key, result, "fixtures_upcoming")

            logger.success(
                "Retrieved fixture lineups successfully",
                extra={"fixture": fixture, "request_id": request_id}
            )

            return result

        except Exception as e:
            logger.error(
                f"Error retrieving fixture lineups: {str(e)}",
                extra={"error": str(e), "request_id": request_id}
            )
            return {
                "error": f"Failed to retrieve fixture lineups: {str(e)}",
                "request_id": request_id,
            }

    async def get_predictions_formatted(self, fixture: int) -> dict[str, Any]:
        """
        Get predictions for a specific fixture with formatted output.
        
        Returns:
            Dictionary containing formatted fixture predictions
        """
        request_id = str(uuid.uuid4())

        logger.info(
            "Retrieving fixture predictions",
            extra={"fixture": fixture, "request_id": request_id}
        )

        try:
            # Check cache first if cache service is available
            cache_key = f"predictions:{fixture}"
            if self.cache_service:
                cached_result = await self.cache_service.get(cache_key)
                if cached_result:
                    logger.debug(
                        "Returning cached predictions",
                        extra={"request_id": request_id}
                    )
                    return cached_result  # type: ignore[no-any-return]

            # Make API request
            response = await self.get_predictions(fixture)

            # Process response
            if not response.response or not response.response[0]:
                return {
                    "error": "No predictions found for this fixture",
                    "request_id": request_id,
                }

            prediction_data = response.response[0]

            # Extract and format prediction data
            formatted_prediction = {
                "winner": prediction_data.get("winner", {}),
                "win_or_draw": prediction_data.get("win_or_draw"),
                "under_over": prediction_data.get("under_over"),
                "goals": prediction_data.get("goals", {}),
                "advice": prediction_data.get("advice"),
                "percent": prediction_data.get("percent", {}),
                "league": prediction_data.get("league", {}),
                "teams": prediction_data.get("teams", {}),
                "comparison": prediction_data.get("comparison", {}),
                "h2h": prediction_data.get("h2h", []),
            }

            result = {
                "fixture_id": fixture,
                "predictions": formatted_prediction,
                "request_id": request_id,
            }

            # Cache result if cache service is available (1 hour TTL)
            if self.cache_service:
                await self.cache_service.set(cache_key, result, "predictions")

            logger.success(
                "Retrieved fixture predictions successfully",
                extra={"fixture": fixture, "request_id": request_id}
            )

            return result

        except Exception as e:
            logger.error(
                f"Error retrieving predictions: {str(e)}",
                extra={"error": str(e), "request_id": request_id}
            )
            return {
                "error": f"Failed to retrieve predictions: {str(e)}",
                "request_id": request_id,
            }

    async def search_leagues(
        self,
        id: int | None = None,
        name: str | None = None,
        country: str | None = None,
        code: str | None = None,
        season: int | None = None,
        team: int | None = None,
        type: str | None = None,
        current: str | None = None,
        search: str | None = None,
        last: int | None = None,
    ) -> dict[str, Any]:
        """
        Search for leagues with various filters and return formatted data.
        
        Args:
            id: League ID
            name: League name
            country: Country name
            code: Country code (2-6 characters, e.g. FR, GB-ENG, IT)
            season: Season year (YYYY)
            team: Team ID
            type: Type of league ("league" or "cup")
            current: Return active seasons or last completed ("true" or "false")
            search: Search string (min 3 chars) for league name or country
            last: Last N leagues/cups added to the API (max 99)
        
        Returns:
            Dictionary containing formatted league information
        """
        request_id = str(uuid.uuid4())

        # Validate search parameter
        if search and len(search) < 3:
            return {
                "error": "Search parameter must be at least 3 characters long",
                "request_id": request_id,
            }

        # Validate type parameter
        if type and type not in ["league", "cup"]:
            return {
                "error": "Type parameter must be 'league' or 'cup'",
                "request_id": request_id,
            }

        # Validate current parameter
        if current and current not in ["true", "false"]:
            return {
                "error": "Current parameter must be 'true' or 'false'",
                "request_id": request_id,
            }

        # Validate last parameter
        if last is not None and (last < 1 or last > 99):
            return {
                "error": "Last parameter must be between 1 and 99",
                "request_id": request_id,
            }

        # Build parameters for cache key
        params: dict[str, Any] = {}
        if id is not None:
            params["id"] = str(id)
        if name:
            params["name"] = name
        if country:
            params["country"] = country
        if code:
            params["code"] = code
        if season is not None:
            params["season"] = str(season)
        if team is not None:
            params["team"] = str(team)
        if type:
            params["type"] = type
        if current:
            params["current"] = current
        if search:
            params["search"] = search
        if last is not None:
            params["last"] = str(last)

        logger.info(
            "Searching leagues",
            extra={"params": params, "request_id": request_id}
        )

        try:
            # Make API request
            response = await self.get_leagues(
                id=id,
                name=name,
                country=country,
                code=code,
                season=season,
                team=team,
                type=type,
                current=current,
                search=search,
                last=last,
            )

            # Process response
            result = {
                "success": True,
                "leagues": response.response,
                "total_results": response.results,
                "request_id": request_id,
                "api_credits": {
                    "get": response.get,
                    "parameters": response.parameters,
                    "errors": response.errors,
                    "results": response.results,
                },
            }

            logger.success(
                "Retrieved leagues successfully",
                extra={"total_results": response.results, "request_id": request_id}
            )

            return result

        except Exception as e:
            logger.error(
                f"Error retrieving leagues: {str(e)}",
                extra={"error": str(e), "request_id": request_id}
            )
            return {
                "error": f"Failed to retrieve leagues: {str(e)}",
                "request_id": request_id,
            }

    async def get_seasons_formatted(self) -> dict[str, Any]:
        """Get available seasons with formatted output."""
        request_id = str(uuid.uuid4())
        
        logger.info(
            "Getting available seasons",
            extra={"request_id": request_id}
        )

        try:
            # Make API request
            response = await self.get_seasons()

            # Process response
            result = {
                "success": True,
                "seasons": response.response,
                "total_results": response.results,
                "request_id": request_id,
                "api_credits": {
                    "get": response.get,
                    "parameters": response.parameters,
                    "errors": response.errors,
                    "results": response.results,
                },
            }

            logger.success(
                "Retrieved seasons successfully",
                extra={"total_results": response.results, "request_id": request_id}
            )

            return result

        except Exception as e:
            logger.error(
                f"Error retrieving seasons: {str(e)}",
                extra={"error": str(e), "request_id": request_id}
            )
            return {
                "error": f"Failed to retrieve seasons: {str(e)}",
                "request_id": request_id,
            }
