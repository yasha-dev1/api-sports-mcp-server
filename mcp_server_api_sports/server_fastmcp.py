"""FastMCP HTTP server implementation for API-Sports."""

import os
from typing import Any

from mcp.server.fastmcp import FastMCP

from .config import get_settings
from .logger import get_logger, setup_logging
from .services import ApiSportsService, CacheService

# Lazy initialization - will be set up when the module is run
logger = None
settings = None
cache_service = None
api_service = None
mcp = None

def _initialize():
    """Initialize the module-level variables."""
    global logger, settings, cache_service, api_service, mcp
    
    # Setup logging first
    setup_logging()
    logger = get_logger(__name__)
    
    # Initialize settings and services
    settings = get_settings()
    cache_service = CacheService()
    api_service = ApiSportsService(cache_service=cache_service)
    
    # Create FastMCP server instance
    mcp = FastMCP(
        name=settings.mcp_server_name
    )
    
    # Add health check endpoint for Docker
    from starlette.responses import JSONResponse
    @mcp.custom_route("/health", methods=["GET"])
    async def health_check():
        """Health check endpoint for monitoring."""
        return JSONResponse({
            "status": "healthy",
            "service": settings.mcp_server_name,
            "version": settings.mcp_server_version
        })
    
    # Register all the tools after mcp is initialized
    _register_tools()


def _register_tools():
    """Register all MCP tools."""
    
    # Tool: teams_search
    @mcp.tool()
    async def teams_search(
        id: int | None = None,
        name: str | None = None,
        league: int | None = None,
        season: int | None = None,
        country: str | None = None,
        code: str | None = None,
        venue: int | None = None,
        search: str | None = None,
    ) -> dict[str, Any]:
        """Search for football teams and retrieve their information.
        
        Args:
            id: Team ID
            name: Team name
            league: League ID
            season: Season year (YYYY)
            country: Country name
            code: 3-letter team code
            venue: Venue ID
            search: Search string (minimum 3 characters)
        """
        logger.info(f"Searching teams with params: {locals()}")
        return await api_service.search_teams(
            id=id, name=name, league=league, season=season,
            country=country, code=code, venue=venue, search=search
        )

    # Tool: fixtures_get
    @mcp.tool()
    async def fixtures_get(
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
        """Retrieve football fixtures (matches) with comprehensive filtering.
        
        Note: When using 'league' or 'team' parameter, 'season' is required.
        
        Args:
            id: Fixture ID
            ids: Multiple fixture IDs (delimiter '-', max 20)
            live: 'all' or league IDs for live fixtures
            date: Date in YYYY-MM-DD format
            league: League ID (requires 'season' parameter)
            season: Season year (YYYY) - required when using 'league' or 'team'
            team: Team ID (requires 'season' parameter)
            last: Last N matches (max 99)
            next: Next N matches (max 99)
            from_date: Start date (YYYY-MM-DD)
            to_date: End date (YYYY-MM-DD)
            round: Round name
            status: Match status (NS, PST, FT, etc.)
            venue: Venue ID
            timezone: Timezone for dates
        """
        logger.info(f"Getting fixtures with params: {locals()}")
        return await api_service.search_fixtures(
            id=id, ids=ids, live=live, date=date, league=league,
            season=season, team=team, last=last, next=next,
            from_date=from_date, to_date=to_date, round=round,
            status=status, venue=venue, timezone=timezone
        )

    # Tool: team_statistics
    @mcp.tool()
    async def team_statistics(
        league: int,
        season: int,
        team: int,
        date: str | None = None,
    ) -> dict[str, Any]:
        """Get comprehensive statistics for a team in a specific league and season.
        
        Args:
            league: League ID (required)
            season: Season year YYYY (required)
            team: Team ID (required)
            date: Date up to which statistics are calculated (YYYY-MM-DD)
        """
        logger.info(f"Getting team statistics: league={league}, season={season}, team={team}, date={date}")
        return await api_service.get_team_statistics_formatted(
            league=league, season=season, team=team, date=date
        )

    # Tool: standings
    @mcp.tool()
    async def standings(
        league: int,
        season: int,
        team: int | None = None,
    ) -> dict[str, Any]:
        """Get current league standings/table.
        
        Args:
            league: League ID (required)
            season: Season year YYYY (required)
            team: Optional team ID to get standings for a specific team
        """
        logger.info(f"Getting standings: league={league}, season={season}, team={team}")
        return await api_service.get_standings_formatted(
            league=league, season=season, team=team
        )

    # Tool: head2head
    @mcp.tool()
    async def head2head(
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
        """Get head-to-head comparison between two teams.
        
        Args:
            h2h: Teams IDs separated by dash, e.g. '33-34' (required)
            date: Date in YYYY-MM-DD format
            league: League ID
            season: Season year (YYYY)
            last: Last N matches
            next: Next N matches
            from_date: Start date (YYYY-MM-DD)
            to_date: End date (YYYY-MM-DD)
            status: Match status
            venue: Venue ID
            timezone: Timezone for dates
        """
        logger.info(f"Getting head2head: h2h={h2h}, params={locals()}")
        return await api_service.get_head2head_formatted(
            h2h=h2h, date=date, league=league, season=season,
            last=last, next=next, from_date=from_date, to_date=to_date,
            status=status, venue=venue, timezone=timezone
        )

    # Tool: fixture_statistics
    @mcp.tool()
    async def fixture_statistics(fixture: int) -> dict[str, Any]:
        """Get detailed match statistics for a specific fixture.
        
        Args:
            fixture: Fixture ID (required)
        """
        logger.info(f"Getting fixture statistics: fixture={fixture}")
        return await api_service.get_fixture_statistics_formatted(fixture=fixture)

    # Tool: fixture_events
    @mcp.tool()
    async def fixture_events(fixture: int) -> dict[str, Any]:
        """Get timeline of events (goals, cards, substitutions) for a fixture.
        
        Args:
            fixture: Fixture ID (required)
        """
        logger.info(f"Getting fixture events: fixture={fixture}")
        return await api_service.get_fixture_events_formatted(fixture=fixture)

    # Tool: fixture_lineups
    @mcp.tool()
    async def fixture_lineups(fixture: int) -> dict[str, Any]:
        """Get team lineups and formations for a fixture.
        
        Args:
            fixture: Fixture ID (required)
        """
        logger.info(f"Getting fixture lineups: fixture={fixture}")
        return await api_service.get_fixture_lineups_formatted(fixture=fixture)

    # Tool: predictions
    @mcp.tool()
    async def predictions(fixture: int) -> dict[str, Any]:
        """Get match predictions and betting advice for a fixture.
        
        Args:
            fixture: Fixture ID (required)
        """
        logger.info(f"Getting predictions: fixture={fixture}")
        return await api_service.get_predictions_formatted(fixture=fixture)

    # Tool: leagues_search
    @mcp.tool()
    async def leagues_search(
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
        """Get the list of available leagues and cups with comprehensive filtering.
        
        Args:
            id: League ID
            name: League name
            country: Country name
            code: Country code (2-6 characters, e.g. FR, GB-ENG, IT)
            season: Season year (YYYY)
            team: Team ID
            type: Type of league ('league' or 'cup')
            current: Return active seasons or last completed ('true' or 'false')
            search: Search string for league name or country (minimum 3 characters)
            last: Last N leagues/cups added to the API (max 99)
        """
        logger.info(f"Searching leagues with params: {locals()}")
        return await api_service.search_leagues(
            id=id, name=name, country=country, code=code, season=season,
            team=team, type=type, current=current, search=search, last=last
        )

def run_http(host: str = "0.0.0.0", port: int = 8080) -> None:
    """Run the FastMCP server with HTTP transport.
    
    Args:
        host: Host to bind to (default: 0.0.0.0)
        port: Port to bind to (default: 8080)
    """
    if not mcp:
        _initialize()
    
    logger.info(f"Starting FastMCP HTTP server on {host}:{port}")
    logger.info(f"Server: {settings.mcp_server_name} v{settings.mcp_server_version}")
    logger.info("Note: FastMCP currently runs on port 8000 internally")
    
    # Run with streamable-http transport
    # Note: FastMCP currently doesn't respect port configuration and runs on 8000
    mcp.run(transport="streamable-http")


def run_stdio() -> None:
    """Run the FastMCP server with stdio transport."""
    if not mcp:
        _initialize()
    
    logger.info(f"Starting FastMCP stdio server")
    logger.info(f"Server: {settings.mcp_server_name} v{settings.mcp_server_version}")
    
    # Run with stdio transport
    mcp.run(transport="stdio")


if __name__ == "__main__":
    import sys
    
    # Initialize the module
    _initialize()
    
    # Check command line arguments
    if len(sys.argv) > 1 and sys.argv[1] == "--http":
        # Get host and port from environment variables
        host = os.environ.get("HTTP_HOST", "0.0.0.0")
        port = int(os.environ.get("HTTP_PORT", "8080"))
        run_http(host=host, port=port)
    else:
        run_stdio()