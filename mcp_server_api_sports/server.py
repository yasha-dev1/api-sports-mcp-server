"""Main MCP server implementation for API-Sports."""

import asyncio
import json
from typing import Any

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

from .config import get_settings
from .logger import get_logger, setup_logging
from .services import ApiSportsService, CacheService

logger = get_logger(__name__)


class ApiSportsMCPServer:
    """MCP Server for API-Sports integration."""

    def __init__(self) -> None:
        self.settings = get_settings()
        self.server: Server = Server(self.settings.mcp_server_name)

        # Initialize services
        self.cache_service = CacheService()
        self.api_service = ApiSportsService(cache_service=self.cache_service)

        # Register handlers
        self._register_handlers()

        logger.info(
            f"Initialized {self.settings.mcp_server_name} v{self.settings.mcp_server_version}"
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
                    },
                ),
                Tool(
                    name="fixtures_get",
                    description="Retrieve football fixtures (matches) with comprehensive filtering",
                    inputSchema={
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
                    },
                ),
                Tool(
                    name="team_statistics",
                    description="Get comprehensive statistics for a team in a specific league and season",
                    inputSchema={
                        "type": "object",
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
                                "description": "Date up to which statistics are calculated (YYYY-MM-DD)"
                            }
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
                                "description": "Optional team ID to get standings for a specific team"
                            }
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
                            "h2h": {
                                "type": "string",
                                "description": "Teams IDs separated by dash, e.g. '33-34' (required)"
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
                            "last": {
                                "type": "integer",
                                "description": "Last N matches"
                            },
                            "next": {
                                "type": "integer",
                                "description": "Next N matches"
                            },
                            "from": {
                                "type": "string",
                                "description": "Start date (YYYY-MM-DD)"
                            },
                            "to": {
                                "type": "string",
                                "description": "End date (YYYY-MM-DD)"
                            },
                            "status": {
                                "type": "string",
                                "description": "Match status"
                            },
                            "venue": {
                                "type": "integer",
                                "description": "Venue ID"
                            },
                            "timezone": {
                                "type": "string",
                                "description": "Timezone for dates"
                            }
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
                            "fixture": {
                                "type": "integer",
                                "description": "Fixture ID (required)"
                            }
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
                            "fixture": {
                                "type": "integer",
                                "description": "Fixture ID (required)"
                            }
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
                            "fixture": {
                                "type": "integer",
                                "description": "Fixture ID (required)"
                            }
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
                            "fixture": {
                                "type": "integer",
                                "description": "Fixture ID (required)"
                            }
                        },
                        "required": ["fixture"]
                    },
                ),
            ]

            logger.debug(f"Listed {len(tools)} tools")
            return tools

        @self.server.call_tool()
        async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
            """Execute a tool with given arguments."""
            logger.info(
                f"Calling tool: {name}",
                extra={"tool": name, "arguments": arguments}
            )

            try:
                result = None

                if name == "teams_search":
                    result = await self.api_service.search_teams(**arguments)

                elif name == "fixtures_get":
                    # Map 'from' and 'to' parameters to 'from_date' and 'to_date'
                    if "from" in arguments:
                        arguments["from_date"] = arguments.pop("from")
                    if "to" in arguments:
                        arguments["to_date"] = arguments.pop("to")
                    result = await self.api_service.search_fixtures(**arguments)

                elif name == "team_statistics":
                    result = await self.api_service.get_team_statistics_formatted(**arguments)

                elif name == "standings":
                    result = await self.api_service.get_standings_formatted(**arguments)

                elif name == "head2head":
                    # Map 'from' and 'to' parameters to 'from_date' and 'to_date'
                    if "from" in arguments:
                        arguments["from_date"] = arguments.pop("from")
                    if "to" in arguments:
                        arguments["to_date"] = arguments.pop("to")
                    result = await self.api_service.get_head2head_formatted(**arguments)

                elif name == "fixture_statistics":
                    result = await self.api_service.get_fixture_statistics_formatted(**arguments)

                elif name == "fixture_events":
                    result = await self.api_service.get_fixture_events_formatted(**arguments)

                elif name == "fixture_lineups":
                    result = await self.api_service.get_fixture_lineups_formatted(**arguments)

                elif name == "predictions":
                    result = await self.api_service.get_predictions_formatted(**arguments)

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

    async def run(self) -> None:
        """Run the MCP server."""
        logger.info(f"Starting {self.settings.mcp_server_name}...")

        try:
            # Start periodic cache cleanup task
            async def cache_cleanup_task() -> None:
                while True:
                    await asyncio.sleep(300)  # Every 5 minutes
                    cleaned = await self.cache_service.cleanup_expired()
                    if cleaned > 0:
                        logger.debug(f"Cleaned {cleaned} expired cache entries")

            # Start cache cleanup in background
            cleanup_task = asyncio.create_task(cache_cleanup_task())

            # Run the server
            async with stdio_server() as (read_stream, write_stream):
                logger.info("MCP server started successfully")
                await self.server.run(read_stream, write_stream, None)  # type: ignore[arg-type]

        except KeyboardInterrupt:
            logger.info("Server interrupted by user")
        except Exception as e:
            logger.error(f"Server error: {str(e)}")
            raise
        finally:
            cleanup_task.cancel()
            await self.cleanup()


async def main() -> None:
    """Main entry point."""
    # Setup logging first
    setup_logging()

    # Create and run server
    server = ApiSportsMCPServer()
    await server.run()


def run() -> None:
    """Synchronous entry point for the script."""
    asyncio.run(main())


if __name__ == "__main__":
    run()
