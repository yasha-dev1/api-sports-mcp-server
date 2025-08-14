"""API-Sports service for making API calls."""

import asyncio
import time
from typing import Any

import httpx
from pydantic import ValidationError

from ..config import get_settings
from ..logger import get_logger, log_performance
from ..models import ApiResponse

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

    def __init__(self):
        self.settings = get_settings()
        self.base_url = self.settings.api_sports_base_url
        self.api_key = self.settings.api_sports_api_key

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

                if response.status_code >= 500:
                    # Server error, retry with backoff
                    if attempt < max_retries - 1:
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

                response.raise_for_status()

                # Parse response
                data = response.json()
                api_response = ApiResponse(**data)

                # Check for API errors
                if api_response.errors:
                    logger.error(
                        "API returned errors",
                        extra={
                            "errors": api_response.errors,
                            "endpoint": endpoint,
                            "request_id": request_id,
                        }
                    )

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

        return await self.make_request("/teams", params)

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

        return await self.make_request("/fixtures", params)

    async def get_team_statistics(
        self,
        league: int,
        season: int,
        team: int,
        date: str | None = None,
    ) -> ApiResponse:
        """Get team statistics."""
        params = {
            "league": league,
            "season": season,
            "team": team,
        }
        if date:
            params["date"] = date

        return await self.make_request("/teams/statistics", params)

    async def get_standings(
        self,
        league: int,
        season: int,
        team: int | None = None,
    ) -> ApiResponse:
        """Get league standings."""
        params = {
            "league": league,
            "season": season,
        }
        if team is not None:
            params["team"] = team

        return await self.make_request("/standings", params)

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
        params = {"h2h": h2h}

        if date:
            params["date"] = date
        if league is not None:
            params["league"] = league
        if season is not None:
            params["season"] = season
        if last is not None:
            params["last"] = last
        if next is not None:
            params["next"] = next
        if from_date:
            params["from"] = from_date
        if to_date:
            params["to"] = to_date
        if status:
            params["status"] = status
        if venue is not None:
            params["venue"] = venue
        if timezone:
            params["timezone"] = timezone

        return await self.make_request("/fixtures/headtohead", params)

    async def get_fixture_statistics(self, fixture: int) -> ApiResponse:
        """Get fixture statistics."""
        return await self.make_request("/fixtures/statistics", {"fixture": fixture})

    async def get_fixture_events(self, fixture: int) -> ApiResponse:
        """Get fixture events."""
        return await self.make_request("/fixtures/events", {"fixture": fixture})

    async def get_fixture_lineups(self, fixture: int) -> ApiResponse:
        """Get fixture lineups."""
        return await self.make_request("/fixtures/lineups", {"fixture": fixture})

    async def get_predictions(self, fixture: int) -> ApiResponse:
        """Get fixture predictions."""
        return await self.make_request("/predictions", {"fixture": fixture})
