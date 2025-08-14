"""HTTP server implementation for API-Sports using low-level MCP API."""

import asyncio
import json
from typing import Any

import uvicorn
from mcp.server import Server
from mcp.server.streamable_http import StreamableHTTPServerTransport
from mcp.types import TextContent, Tool
from starlette.applications import Starlette
from starlette.middleware.cors import CORSMiddleware
from starlette.responses import JSONResponse
from starlette.routing import Route

from .config import get_settings
from .logger import get_logger, setup_logging
from .services import ApiSportsService, CacheService

logger = get_logger(__name__)


class ApiSportsHTTPServer:
    """HTTP Server for API-Sports MCP integration."""

    def __init__(self) -> None:
        self.settings = get_settings()
        self.server: Server = Server(
            name=self.settings.mcp_server_name,
            version=self.settings.mcp_server_version
        )

        # Initialize services
        self.cache_service = CacheService()
        self.api_service = ApiSportsService(cache_service=self.cache_service)

        # Register handlers
        self._register_handlers()
        
        # Create HTTP transport
        self.transport = StreamableHTTPServerTransport(
            mcp_session_id=None,
            is_json_response_enabled=True
        )

        logger.info(
            f"Initialized HTTP {self.settings.mcp_server_name} v{self.settings.mcp_server_version}"
        )

    def _register_handlers(self) -> None:
        """Register MCP server handlers."""

        @self.server.list_tools()
        async def list_tools() -> list[Tool]:
            """List available tools."""
            tools = [
                Tool(
                    name="teams_search",
                    description="Search for football teams and retrieve their information",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "id": {"type": "integer", "description": "Team ID"},
                            "name": {"type": "string", "description": "Team name"},
                            "league": {"type": "integer", "description": "League ID"},
                            "season": {"type": "integer", "description": "Season year (YYYY)"},
                            "country": {"type": "string", "description": "Country name"},
                            "code": {"type": "string", "description": "3-letter team code"},
                            "venue": {"type": "integer", "description": "Venue ID"},
                            "search": {"type": "string", "description": "Search string (minimum 3 characters)"}
                        }
                    },
                ),
                Tool(
                    name="fixtures_get",
                    description="Retrieve football fixtures (matches) with comprehensive filtering. Note: When using 'league' parameter, 'season' is required.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "id": {"type": "integer", "description": "Fixture ID"},
                            "ids": {"type": "string", "description": "Multiple fixture IDs (delimiter '-', max 20)"},
                            "live": {"type": "string", "description": "'all' or league IDs for live fixtures"},
                            "date": {"type": "string", "description": "Date in YYYY-MM-DD format"},
                            "league": {"type": "integer", "description": "League ID (requires 'season' parameter)"},
                            "season": {"type": "integer", "description": "Season year (YYYY) - required when using 'league'"},
                            "team": {"type": "integer", "description": "Team ID"},
                            "last": {"type": "integer", "description": "Last N matches (max 99)"},
                            "next": {"type": "integer", "description": "Next N matches (max 99)"},
                            "from": {"type": "string", "description": "Start date (YYYY-MM-DD)"},
                            "to": {"type": "string", "description": "End date (YYYY-MM-DD)"},
                            "round": {"type": "string", "description": "Round name"},
                            "status": {"type": "string", "description": "Match status (NS, PST, FT, etc.)"},
                            "venue": {"type": "integer", "description": "Venue ID"},
                            "timezone": {"type": "string", "description": "Timezone for dates"}
                        }
                    },
                ),
                Tool(
                    name="team_statistics",
                    description="Get comprehensive statistics for a team in a specific league and season",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "league": {"type": "integer", "description": "League ID (required)"},
                            "season": {"type": "integer", "description": "Season year YYYY (required)"},
                            "team": {"type": "integer", "description": "Team ID (required)"},
                            "date": {"type": "string", "description": "Date up to which statistics are calculated (YYYY-MM-DD)"}
                        },
                        "required": ["league", "season", "team"]
                    },
                ),
                Tool(
                    name="standings",
                    description="Get current league standings/table",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "league": {"type": "integer", "description": "League ID (required)"},
                            "season": {"type": "integer", "description": "Season year YYYY (required)"},
                            "team": {"type": "integer", "description": "Optional team ID to get standings for a specific team"}
                        },
                        "required": ["league", "season"]
                    },
                ),
                Tool(
                    name="head2head",
                    description="Get head-to-head comparison between two teams",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "h2h": {"type": "string", "description": "Teams IDs separated by dash, e.g. '33-34' (required)"},
                            "date": {"type": "string", "description": "Date in YYYY-MM-DD format"},
                            "league": {"type": "integer", "description": "League ID"},
                            "season": {"type": "integer", "description": "Season year (YYYY)"},
                            "last": {"type": "integer", "description": "Last N matches"},
                            "next": {"type": "integer", "description": "Next N matches"},
                            "from": {"type": "string", "description": "Start date (YYYY-MM-DD)"},
                            "to": {"type": "string", "description": "End date (YYYY-MM-DD)"},
                            "status": {"type": "string", "description": "Match status"},
                            "venue": {"type": "integer", "description": "Venue ID"},
                            "timezone": {"type": "string", "description": "Timezone for dates"}
                        },
                        "required": ["h2h"]
                    },
                ),
                Tool(
                    name="fixture_statistics",
                    description="Get detailed match statistics for a specific fixture",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "fixture": {"type": "integer", "description": "Fixture ID (required)"}
                        },
                        "required": ["fixture"]
                    },
                ),
                Tool(
                    name="fixture_events",
                    description="Get timeline of events (goals, cards, substitutions) for a fixture",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "fixture": {"type": "integer", "description": "Fixture ID (required)"}
                        },
                        "required": ["fixture"]
                    },
                ),
                Tool(
                    name="fixture_lineups",
                    description="Get team lineups and formations for a fixture",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "fixture": {"type": "integer", "description": "Fixture ID (required)"}
                        },
                        "required": ["fixture"]
                    },
                ),
                Tool(
                    name="predictions",
                    description="Get match predictions and betting advice for a fixture",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "fixture": {"type": "integer", "description": "Fixture ID (required)"}
                        },
                        "required": ["fixture"]
                    },
                ),
            ]

            logger.debug(f"Listed {len(tools)} tools")
            return tools

        @self.server.call_tool(validate_input=False)
        async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
            """Execute a tool with given arguments."""
            logger.info(
                f"Calling tool: {name}",
                extra={"tool": name, "arguments": arguments}
            )

            try:
                # Clean up arguments - remove empty strings and convert to proper types
                cleaned_args = {}
                for key, value in arguments.items():
                    if value == "":
                        # Skip empty strings - they should be treated as None/not provided
                        continue
                    elif isinstance(value, str) and value.isdigit():
                        # Convert numeric strings to integers
                        cleaned_args[key] = int(value)
                    else:
                        cleaned_args[key] = value
                
                logger.debug(
                    f"Cleaned arguments for {name}",
                    extra={"original": arguments, "cleaned": cleaned_args}
                )
                
                result = None
                
                # Validate required parameters for specific tools
                if name == "team_statistics":
                    required = ["league", "season", "team"]
                    missing = [p for p in required if p not in cleaned_args]
                    if missing:
                        error_msg = f"Missing required parameters: {', '.join(missing)}"
                        logger.error(error_msg)
                        return [TextContent(type="text", text=json.dumps({"error": error_msg}))]
                
                elif name == "standings":
                    required = ["league", "season"]
                    missing = [p for p in required if p not in cleaned_args]
                    if missing:
                        error_msg = f"Missing required parameters: {', '.join(missing)}"
                        logger.error(error_msg)
                        return [TextContent(type="text", text=json.dumps({"error": error_msg}))]
                
                elif name == "head2head":
                    if "h2h" not in cleaned_args:
                        error_msg = "Missing required parameter: h2h"
                        logger.error(error_msg)
                        return [TextContent(type="text", text=json.dumps({"error": error_msg}))]
                
                elif name in ["fixture_statistics", "fixture_events", "fixture_lineups", "predictions"]:
                    if "fixture" not in cleaned_args:
                        error_msg = "Missing required parameter: fixture"
                        logger.error(error_msg)
                        return [TextContent(type="text", text=json.dumps({"error": error_msg}))]

                if name == "teams_search":
                    result = await self.api_service.search_teams(**cleaned_args)

                elif name == "fixtures_get":
                    # Map 'from' and 'to' parameters to 'from_date' and 'to_date'
                    if "from" in cleaned_args:
                        cleaned_args["from_date"] = cleaned_args.pop("from")
                    if "to" in cleaned_args:
                        cleaned_args["to_date"] = cleaned_args.pop("to")
                    result = await self.api_service.search_fixtures(**cleaned_args)

                elif name == "team_statistics":
                    result = await self.api_service.get_team_statistics_formatted(**cleaned_args)

                elif name == "standings":
                    result = await self.api_service.get_standings_formatted(**cleaned_args)

                elif name == "head2head":
                    # Map 'from' and 'to' parameters to 'from_date' and 'to_date'
                    if "from" in cleaned_args:
                        cleaned_args["from_date"] = cleaned_args.pop("from")
                    if "to" in cleaned_args:
                        cleaned_args["to_date"] = cleaned_args.pop("to")
                    result = await self.api_service.get_head2head_formatted(**cleaned_args)

                elif name == "fixture_statistics":
                    result = await self.api_service.get_fixture_statistics_formatted(**cleaned_args)

                elif name == "fixture_events":
                    result = await self.api_service.get_fixture_events_formatted(**cleaned_args)

                elif name == "fixture_lineups":
                    result = await self.api_service.get_fixture_lineups_formatted(**cleaned_args)

                elif name == "predictions":
                    result = await self.api_service.get_predictions_formatted(**cleaned_args)

                else:
                    error_msg = f"Unknown tool: {name}"
                    logger.error(error_msg)
                    return [TextContent(type="text", text=json.dumps({"error": error_msg}))]

                # Format result as JSON string
                result_json = json.dumps(result, indent=2, default=str)

                logger.success(
                    f"Tool {name} executed successfully",
                    extra={"tool": name}
                )

                return [TextContent(type="text", text=result_json)]

            except Exception as e:
                error_msg = f"Error executing tool {name}: {str(e)}"
                logger.error(error_msg, extra={"tool": name, "error": str(e)})
                return [TextContent(
                    type="text",
                    text=json.dumps({"error": error_msg})
                )]

    async def cleanup(self) -> None:
        """Cleanup resources."""
        logger.info("Cleaning up resources...")
        await self.api_service.close()
        logger.info("Cleanup complete")

    def create_app(self) -> Starlette:
        """Create Starlette application with MCP transport."""
        
        async def health_check(request):
            """Health check endpoint."""
            return JSONResponse({
                "status": "healthy",
                "server": self.settings.mcp_server_name,
                "version": self.settings.mcp_server_version
            })
        
        async def mcp_handler(request):
            """Handle MCP requests."""
            return await self.transport.handle(request.scope, request.receive, request.send)
        
        # Create routes
        routes = [
            Route("/health", health_check, methods=["GET"]),
            Route("/mcp", mcp_handler, methods=["POST", "GET"]),
        ]
        
        # Create app
        app = Starlette(routes=routes)
        
        # Add CORS if enabled
        if self.settings.http_cors_enabled:
            app.add_middleware(
                CORSMiddleware,
                allow_origins=["*"],
                allow_credentials=True,
                allow_methods=["*"],
                allow_headers=["*"],
            )
        
        # Setup server with transport
        @app.on_event("startup")
        async def startup():
            """Initialize server on startup."""
            # Start cache cleanup task
            async def cache_cleanup_task():
                while True:
                    await asyncio.sleep(300)  # Every 5 minutes
                    cleaned = await self.cache_service.cleanup_expired()
                    if cleaned > 0:
                        logger.debug(f"Cleaned {cleaned} expired cache entries")
            
            self.cleanup_task = asyncio.create_task(cache_cleanup_task())
            
            # Initialize server with transport
            read_stream, write_stream = self.transport.get_streams()
            self.server_task = asyncio.create_task(
                self.server.run(
                    read_stream,
                    write_stream,
                    self.server.create_initialization_options()
                )
            )
            logger.info(f"HTTP server started on {self.settings.http_host}:{self.settings.http_port}")
        
        @app.on_event("shutdown")
        async def shutdown():
            """Cleanup on shutdown."""
            self.cleanup_task.cancel()
            self.server_task.cancel()
            await self.cleanup()
        
        return app
    
    def run(self) -> None:
        """Run the HTTP server."""
        app = self.create_app()
        uvicorn.run(
            app,
            host=self.settings.http_host,
            port=self.settings.http_port,
            log_level=self.settings.log_level.lower()
        )


def main() -> None:
    """Main entry point for HTTP server."""
    setup_logging()
    server = ApiSportsHTTPServer()
    server.run()


if __name__ == "__main__":
    main()